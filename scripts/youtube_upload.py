"""
YouTube Upload Utility for MSS
Handles video uploads to YouTube with OAuth authentication
"""

import os
import pickle
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# YouTube API scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service():
    """
    Authenticate and return YouTube API service
    Uses stored credentials or initiates OAuth flow
    """
    creds = None
    token_path = Path(__file__).parent.parent / 'youtube_token.pickle'
    client_secrets_path = Path(__file__).parent.parent / 'client_secrets.json'

    # Check if we have stored credentials
    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If credentials are invalid or don't exist, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("[YOUTUBE] Refreshing expired credentials...")
                creds.refresh(Request())
            except Exception as e:
                print(f"[YOUTUBE] Error refreshing credentials: {e}")
                creds = None

        if not creds:
            if not client_secrets_path.exists():
                raise FileNotFoundError(
                    f"client_secrets.json not found at {client_secrets_path}\n"
                    "Please download OAuth credentials from Google Cloud Console:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Enable YouTube Data API v3\n"
                    "3. Create OAuth 2.0 credentials\n"
                    "4. Download as client_secrets.json"
                )

            print("[YOUTUBE] Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), SCOPES
            )
            creds = flow.run_local_server(port=0, prompt='consent')

            # Save credentials for future use
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            print(f"[YOUTUBE] Credentials saved to {token_path}")

    return build('youtube', 'v3', credentials=creds)


def upload_video(
    video_path,
    title,
    description="",
    tags=None,
    category="22",  # 22 = People & Blogs
    privacy_status="private",
    thumbnail_path=None
):
    """
    Upload a video to YouTube

    Args:
        video_path: Path to video file
        title: Video title
        description: Video description
        tags: List of tags
        category: YouTube category ID (default: 22 = People & Blogs)
        privacy_status: 'public', 'private', or 'unlisted'
        thumbnail_path: Optional path to thumbnail image

    Returns:
        dict: {'success': bool, 'video_id': str, 'url': str, 'error': str}
    """
    try:
        print(f"[YOUTUBE] Starting upload: {video_path}")
        print(f"[YOUTUBE] Title: {title}")
        print(f"[YOUTUBE] Privacy: {privacy_status}")

        youtube = get_authenticated_service()

        # Prepare video metadata
        body = {
            'snippet': {
                'title': title[:100],  # YouTube max title length
                'description': description[:5000],  # YouTube max description length
                'tags': tags or [],
                'categoryId': category
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }

        # Create upload request
        media = MediaFileUpload(
            str(video_path),
            chunksize=1024*1024,  # 1MB chunks
            resumable=True
        )

        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )

        # Execute upload with progress tracking
        response = None
        print("[YOUTUBE] Uploading video...")
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"[YOUTUBE] Upload progress: {progress}%")

        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YOUTUBE] ✅ Upload successful!")
        print(f"[YOUTUBE] Video ID: {video_id}")
        print(f"[YOUTUBE] URL: {video_url}")

        # Upload thumbnail if provided
        if thumbnail_path and Path(thumbnail_path).exists():
            try:
                print(f"[YOUTUBE] Uploading thumbnail: {thumbnail_path}")
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_path))
                ).execute()
                print("[YOUTUBE] ✅ Thumbnail uploaded!")
            except Exception as e:
                print(f"[YOUTUBE] ⚠️ Thumbnail upload failed: {e}")

        return {
            'success': True,
            'video_id': video_id,
            'url': video_url,
            'title': title
        }

    except HttpError as e:
        error_msg = f"YouTube API error: {e.resp.status} - {e.content.decode()}"
        print(f"[YOUTUBE] ❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
    except FileNotFoundError as e:
        print(f"[YOUTUBE] ❌ {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}"
        print(f"[YOUTUBE] ❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }


def get_video_categories():
    """Get list of YouTube video categories"""
    try:
        youtube = get_authenticated_service()
        response = youtube.videoCategories().list(
            part='snippet',
            regionCode='US'
        ).execute()

        categories = {
            item['id']: item['snippet']['title']
            for item in response.get('items', [])
        }
        return categories
    except Exception as e:
        print(f"[YOUTUBE] Error fetching categories: {e}")
        return {
            '22': 'People & Blogs',
            '24': 'Entertainment',
            '27': 'Education',
            '28': 'Science & Technology'
        }


if __name__ == '__main__':
    # Test upload
    print("Testing YouTube upload...")
    result = upload_video(
        video_path='test_video.mp4',
        title='Test Upload from MSS',
        description='This is a test upload',
        tags=['test', 'mss'],
        privacy_status='private'
    )
    print(json.dumps(result, indent=2))
