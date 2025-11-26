import os
import sys
import json
import sqlite3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Add web directory to path so we can import if needed, though we'll try to be standalone
sys.path.append(os.path.join(os.getcwd(), 'web'))

DB_PATH = 'web/mss_users.db'

def get_user_email():
    # Get the first user email from the database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT email FROM users LIMIT 1")
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_credentials(user_email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT credentials FROM platform_connections WHERE user_email = ? AND platform = 'youtube'", (user_email,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return json.loads(result[0])
    return None

def debug_sync():
    print("--- Starting YouTube Sync Debug ---")
    
    user_email = get_user_email()
    if not user_email:
        print("No user found in database.")
        return

    print(f"Debugging for user: {user_email}")
    
    creds_data = get_credentials(user_email)
    if not creds_data:
        print("No YouTube credentials found for this user.")
        return
        
    print("Credentials found.")
    
    try:
        credentials = Credentials(
            token=creds_data.get('token') or creds_data.get('access_token'),
            refresh_token=creds_data.get('refresh_token'),
            token_uri=creds_data.get('token_uri'),
            client_id=creds_data.get('client_id'),
            client_secret=creds_data.get('client_secret'),
            scopes=creds_data.get('scopes')
        )
        
        print("Building YouTube service...")
        youtube = build('youtube', 'v3', credentials=credentials)
        
        print("Fetching channel info (mine=True)...")
        channel_response = youtube.channels().list(
            part='snippet,contentDetails',
            mine=True
        ).execute()
        
        print(f"Channel Response Items: {len(channel_response.get('items', []))}")
        if not channel_response.get('items'):
            print("ERROR: No channel found!")
            print(json.dumps(channel_response, indent=2))
            return

        channel = channel_response['items'][0]
        print(f"Channel Title: {channel['snippet']['title']}")
        print(f"Channel ID: {channel['id']}")
        
        uploads_playlist = channel['contentDetails']['relatedPlaylists']['uploads']
        print(f"Uploads Playlist ID: {uploads_playlist}")
        
        print("Fetching playlist items...")
        playlist_request = youtube.playlistItems().list(
            part='snippet,contentDetails',
            playlistId=uploads_playlist,
            maxResults=10
        )
        playlist_response = playlist_request.execute()
        
        items = playlist_response.get('items', [])
        print(f"Found {len(items)} videos in uploads playlist.")
        
        for item in items:
            print(f" - {item['snippet']['title']} ({item['contentDetails']['videoId']})")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_sync()
