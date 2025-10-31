"""
Platform API Integration Module for MSS
Handles OAuth and uploads to YouTube, TikTok, Instagram, etc.
"""

import os
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

# Google API imports (install: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client)
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("[PLATFORM_API] WARNING: google-api-python-client not installed. YouTube integration disabled.")


class PlatformAPIManager:
    def __init__(self, db_path: str = None):
        # Auto-detect database path
        if db_path is None:
            possible_paths = [
                "mss_users.db",
                "web/mss_users.db",
                os.path.join(os.path.dirname(__file__), "mss_users.db")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = path
                    break
            else:
                db_path = os.path.join(os.path.dirname(__file__), "mss_users.db")

        self.db_path = db_path
        self.credentials_dir = Path(__file__).parent / "platform_credentials"
        self.credentials_dir.mkdir(exist_ok=True)
        print(f"[PLATFORM_API] Using database: {self.db_path}")
        print(f"[PLATFORM_API] Credentials dir: {self.credentials_dir}")

    # ======================
    # YouTube API Integration
    # ======================

    def get_youtube_auth_url(self, user_email: str, redirect_uri: str) -> Optional[str]:
        """Generate YouTube OAuth URL"""
        if not GOOGLE_AVAILABLE:
            return None

        # YouTube OAuth scopes + Calendar for content scheduling
        scopes = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube',
            'https://www.googleapis.com/auth/youtube.force-ssl',
            'https://www.googleapis.com/auth/calendar.events'  # Add calendar events
        ]

        # Load client secrets
        client_secrets_file = self.credentials_dir / "youtube_client_secrets.json"
        if not client_secrets_file.exists():
            print("[YOUTUBE] Client secrets file not found. Create youtube_client_secrets.json")
            return None

        try:
            flow = Flow.from_client_secrets_file(
                str(client_secrets_file),
                scopes=scopes,
                redirect_uri=redirect_uri
            )

            # Generate authorization URL
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )

            # Store state for verification
            self._store_oauth_state(user_email, 'youtube', state)
            print(f"[YOUTUBE] Stored OAuth state for user: {user_email}, state: {state[:10]}...")

            return auth_url

        except Exception as e:
            print(f"[YOUTUBE] Error generating auth URL: {e}")
            return None

    def handle_youtube_callback(self, user_email: str, code: str, state: str, redirect_uri: str) -> bool:
        """Handle YouTube OAuth callback"""
        print(f"[YOUTUBE] Callback handler called for user: {user_email}, state: {state[:10]}...")

        if not GOOGLE_AVAILABLE:
            print("[YOUTUBE] GOOGLE_AVAILABLE is False")
            return False

        # Verify state
        stored_state = self._get_oauth_state(user_email, 'youtube')
        if not stored_state:
            print(f"[YOUTUBE] No stored state found for user: {user_email}")
            return False
        if stored_state != state:
            print(f"[YOUTUBE] State mismatch - stored: {stored_state[:10]}..., received: {state[:10]}...")
            return False

        print(f"[YOUTUBE] State verified successfully for user: {user_email}")

        client_secrets_file = self.credentials_dir / "youtube_client_secrets.json"

        try:
            flow = Flow.from_client_secrets_file(
                str(client_secrets_file),
                scopes=[
                    'https://www.googleapis.com/auth/youtube.upload',
                    'https://www.googleapis.com/auth/youtube',
                    'https://www.googleapis.com/auth/youtube.force-ssl',
                    'https://www.googleapis.com/auth/calendar.events'
                ],
                redirect_uri=redirect_uri
            )

            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Store credentials
            self._store_platform_credentials(user_email, 'youtube', {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            })

            return True

        except Exception as e:
            print(f"[YOUTUBE] Error handling callback: {e}")
            return False

    def get_youtube_channel_info(self, user_email: str) -> Dict[str, Any]:
        """Get authenticated user's YouTube channel information"""
        if not GOOGLE_AVAILABLE:
            return {'success': False, 'error': 'YouTube API not available'}

        creds_data = self._get_platform_credentials(user_email, 'youtube')
        if not creds_data:
            return {'success': False, 'error': 'YouTube not connected'}

        try:
            credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )

            youtube = build('youtube', 'v3', credentials=credentials)

            # Get channel info
            request = youtube.channels().list(
                part='snippet,statistics,contentDetails',
                mine=True
            )
            response = request.execute()

            if not response.get('items'):
                return {'success': False, 'error': 'No channel found'}

            channel = response['items'][0]

            return {
                'success': True,
                'channel_id': channel['id'],
                'title': channel['snippet']['title'],
                'description': channel['snippet']['description'],
                'custom_url': channel['snippet'].get('customUrl', ''),
                'thumbnail': channel['snippet']['thumbnails']['default']['url'],
                'subscribers': int(channel['statistics'].get('subscriberCount', 0)),
                'video_count': int(channel['statistics'].get('videoCount', 0)),
                'view_count': int(channel['statistics'].get('viewCount', 0)),
                'uploads_playlist': channel['contentDetails']['relatedPlaylists']['uploads']
            }

        except Exception as e:
            print(f"[YOUTUBE] Error getting channel info: {e}")
            return {'success': False, 'error': str(e)}

    def get_youtube_video_stats(self, user_email: str, video_id: str) -> Dict[str, Any]:
        """Get statistics for a specific YouTube video"""
        if not GOOGLE_AVAILABLE:
            return {'success': False, 'error': 'YouTube API not available'}

        creds_data = self._get_platform_credentials(user_email, 'youtube')
        if not creds_data:
            return {'success': False, 'error': 'YouTube not connected'}

        try:
            credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )

            youtube = build('youtube', 'v3', credentials=credentials)

            # Get video statistics
            request = youtube.videos().list(
                part='statistics,snippet',
                id=video_id
            )
            response = request.execute()

            if not response.get('items'):
                return {'success': False, 'error': 'Video not found'}

            video = response['items'][0]
            stats = video['statistics']

            return {
                'success': True,
                'video_id': video_id,
                'title': video['snippet']['title'],
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'comments': int(stats.get('commentCount', 0)),
                'favorites': int(stats.get('favoriteCount', 0))
            }

        except Exception as e:
            print(f"[YOUTUBE] Error getting video stats: {e}")
            return {'success': False, 'error': str(e)}

    def get_youtube_channel_videos(self, user_email: str, max_results: int = 50) -> Dict[str, Any]:
        """Get all videos from authenticated user's YouTube channel"""
        if not GOOGLE_AVAILABLE:
            return {'success': False, 'error': 'YouTube API not available'}

        creds_data = self._get_platform_credentials(user_email, 'youtube')
        if not creds_data:
            return {'success': False, 'error': 'YouTube not connected'}

        try:
            credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )

            youtube = build('youtube', 'v3', credentials=credentials)

            # Get channel info first
            channel_response = youtube.channels().list(
                part='contentDetails',
                mine=True
            ).execute()

            if not channel_response.get('items'):
                return {'success': False, 'error': 'No channel found'}

            uploads_playlist = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # Get videos from uploads playlist
            videos = []
            next_page_token = None

            while len(videos) < max_results:
                playlist_request = youtube.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=uploads_playlist,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token
                )
                playlist_response = playlist_request.execute()

                for item in playlist_response.get('items', []):
                    video_id = item['contentDetails']['videoId']
                    videos.append({
                        'video_id': video_id,
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnail': item['snippet']['thumbnails']['default']['url']
                    })

                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break

            # Now get statistics for each video (batch request)
            if videos:
                video_ids = [v['video_id'] for v in videos]
                stats_request = youtube.videos().list(
                    part='statistics',
                    id=','.join(video_ids)
                )
                stats_response = stats_request.execute()

                # Map stats to videos
                stats_map = {}
                for item in stats_response.get('items', []):
                    stats = item['statistics']
                    stats_map[item['id']] = {
                        'views': int(stats.get('viewCount', 0)),
                        'likes': int(stats.get('likeCount', 0)),
                        'comments': int(stats.get('commentCount', 0)),
                        'favorites': int(stats.get('favoriteCount', 0))
                    }

                # Add stats to videos
                for video in videos:
                    video.update(stats_map.get(video['video_id'], {}))

            return {
                'success': True,
                'videos': videos,
                'total': len(videos)
            }

        except Exception as e:
            print(f"[YOUTUBE] Error getting channel videos: {e}")
            return {'success': False, 'error': str(e)}

    def upload_to_youtube(self, user_email: str, video_path: str, title: str,
                         description: str = '', tags: list = None,
                         category_id: str = '22', privacy: str = 'public',
                         thumbnail_path: str = None, publish_at: str = None) -> Dict[str, Any]:
        """Upload video to YouTube with optional thumbnail and scheduled publishing

        Args:
            publish_at: ISO 8601 datetime string (e.g., '2024-01-15T10:00:00Z') for scheduled publishing.
                       If provided, video will be set to 'private' and scheduled to publish at this time.
        """
        if not GOOGLE_AVAILABLE:
            return {'success': False, 'error': 'YouTube API not available'}

        if not os.path.exists(video_path):
            return {'success': False, 'error': f'Video file not found: {video_path}'}

        # Get stored credentials
        creds_data = self._get_platform_credentials(user_email, 'youtube')
        if not creds_data:
            return {'success': False, 'error': 'YouTube not connected. Please authenticate first.'}

        try:
            # Create credentials object
            credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )

            # Build YouTube service
            youtube = build('youtube', 'v3', credentials=credentials)

            # Video metadata
            body = {
                'snippet': {
                    'title': title[:100],  # Max 100 chars
                    'description': description[:5000],  # Max 5000 chars
                    'tags': (tags or [])[:500],  # Max 500 tags
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': privacy,
                    'selfDeclaredMadeForKids': False
                }
            }

            # Add scheduled publishing if publish_at is provided
            if publish_at:
                # For scheduled publishing, video must be private initially
                body['status']['privacyStatus'] = 'private'
                body['status']['publishAt'] = publish_at
                print(f"[YOUTUBE] Scheduling video to publish at: {publish_at}")

            # Upload video
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

            request = youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"[YOUTUBE] Upload progress: {int(status.progress() * 100)}%")

            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            print(f"[YOUTUBE] Upload successful: {video_url}")

            # Upload thumbnail if provided
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    print(f"[YOUTUBE] Uploading thumbnail: {thumbnail_path}")
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(thumbnail_path)
                    ).execute()
                    print("[YOUTUBE] Thumbnail uploaded successfully!")
                except Exception as e:
                    print(f"[YOUTUBE] Thumbnail upload failed: {e}")
                    # Don't fail the entire upload if thumbnail fails

            return {
                'success': True,
                'video_id': video_id,
                'url': video_url,
                'platform': 'youtube'
            }

        except Exception as e:
            print(f"[YOUTUBE] Upload error: {e}")
            return {'success': False, 'error': str(e)}

    # ======================
    # Google Calendar Integration
    # ======================

    def add_calendar_event(self, user_email: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add event to user's Google Calendar"""
        if not GOOGLE_AVAILABLE:
            return {'success': False, 'error': 'Google API not available'}

        # Use YouTube credentials (which now include calendar scope)
        creds_data = self._get_platform_credentials(user_email, 'youtube')
        if not creds_data:
            return {'success': False, 'error': 'Google Calendar not connected. Please connect your YouTube account first.'}

        try:
            credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )

            # Build Calendar service
            calendar = build('calendar', 'v3', credentials=credentials)

            # Parse event data
            from datetime import datetime as dt

            event_date = event_data.get('date', event_data.get('scheduled_date'))
            event_time = event_data.get('time', event_data.get('scheduled_time', '10:00'))

            # Combine date and time
            event_datetime = dt.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")

            # Format for Google Calendar (ISO 8601)
            start_time = event_datetime.isoformat()

            # Event duration: 1 hour
            from datetime import timedelta
            end_time = (event_datetime + timedelta(hours=1)).isoformat()

            title = event_data.get('title', 'Content Creation')
            description = event_data.get('description', event_data.get('topic', ''))
            if event_data.get('reason'):
                description += f"\n\n{event_data['reason']}"

            # Create event
            event = {
                'summary': title,
                'description': description,
                'location': 'MSS Studio',
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'America/New_York',  # TODO: Make this configurable
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'America/New_York',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
            }

            # Insert event
            result = calendar.events().insert(calendarId='primary', body=event).execute()

            print(f"[CALENDAR] Event created: {result.get('htmlLink')}")

            return {
                'success': True,
                'event_id': result['id'],
                'html_link': result.get('htmlLink'),
                'platform': 'google_calendar'
            }

        except Exception as e:
            print(f"[CALENDAR] Error adding event: {e}")
            return {'success': False, 'error': str(e)}

    # ======================
    # TikTok API Integration
    # ======================

    def get_tiktok_auth_url(self, user_email: str, redirect_uri: str) -> Optional[str]:
        """Generate TikTok OAuth URL"""
        # TikTok uses OAuth 2.0
        config_file = self.credentials_dir / "tiktok_config.json"
        if not config_file.exists():
            print("[TIKTOK] Config file not found. Create tiktok_config.json")
            return None

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            client_key = config['client_key']

            # TikTok OAuth scopes
            scope = 'user.info.basic,video.upload,video.publish'

            # Generate state
            import secrets
            state = secrets.token_urlsafe(32)
            self._store_oauth_state(user_email, 'tiktok', state)

            # Build auth URL
            auth_url = (
                f"https://www.tiktok.com/auth/authorize/"
                f"?client_key={client_key}"
                f"&response_type=code"
                f"&scope={scope}"
                f"&redirect_uri={redirect_uri}"
                f"&state={state}"
            )

            return auth_url

        except Exception as e:
            print(f"[TIKTOK] Error generating auth URL: {e}")
            return None

    def handle_tiktok_callback(self, user_email: str, code: str, state: str) -> bool:
        """Handle TikTok OAuth callback"""
        # Verify state
        stored_state = self._get_oauth_state(user_email, 'tiktok')
        if not stored_state or stored_state != state:
            return False

        config_file = self.credentials_dir / "tiktok_config.json"

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            # Exchange code for access token
            response = requests.post(
                'https://open-api.tiktok.com/oauth/access_token/',
                params={
                    'client_key': config['client_key'],
                    'client_secret': config['client_secret'],
                    'code': code,
                    'grant_type': 'authorization_code'
                }
            )

            data = response.json()

            if data.get('data', {}).get('access_token'):
                self._store_platform_credentials(user_email, 'tiktok', {
                    'access_token': data['data']['access_token'],
                    'refresh_token': data['data'].get('refresh_token'),
                    'expires_in': data['data'].get('expires_in'),
                    'open_id': data['data'].get('open_id')
                })
                return True

            return False

        except Exception as e:
            print(f"[TIKTOK] Error handling callback: {e}")
            return False

    def upload_to_tiktok(self, user_email: str, video_path: str, title: str,
                        description: str = '', privacy_level: str = 'PUBLIC_TO_EVERYONE') -> Dict[str, Any]:
        """Upload video to TikTok"""
        if not os.path.exists(video_path):
            return {'success': False, 'error': f'Video file not found: {video_path}'}

        creds = self._get_platform_credentials(user_email, 'tiktok')
        if not creds:
            return {'success': False, 'error': 'TikTok not connected'}

        try:
            # Step 1: Initialize upload
            init_response = requests.post(
                'https://open.tiktokapis.com/v2/post/publish/video/init/',
                headers={
                    'Authorization': f"Bearer {creds['access_token']}",
                    'Content-Type': 'application/json; charset=UTF-8'
                },
                json={
                    'post_info': {
                        'title': title[:150],  # Max 150 chars
                        'privacy_level': privacy_level,
                        'disable_duet': False,
                        'disable_comment': False,
                        'disable_stitch': False,
                        'video_cover_timestamp_ms': 1000
                    },
                    'source_info': {
                        'source': 'FILE_UPLOAD',
                        'video_size': os.path.getsize(video_path),
                        'chunk_size': 5242880,  # 5MB chunks
                        'total_chunk_count': 1
                    }
                }
            )

            init_data = init_response.json()

            if init_data.get('error'):
                return {'success': False, 'error': init_data['error']['message']}

            upload_url = init_data['data']['upload_url']
            publish_id = init_data['data']['publish_id']

            # Step 2: Upload video chunks
            with open(video_path, 'rb') as video_file:
                upload_response = requests.put(
                    upload_url,
                    headers={'Content-Type': 'video/mp4'},
                    data=video_file
                )

            if upload_response.status_code != 200:
                return {'success': False, 'error': 'Upload failed'}

            # Step 3: Check publish status
            status_response = requests.post(
                'https://open.tiktokapis.com/v2/post/publish/status/fetch/',
                headers={
                    'Authorization': f"Bearer {creds['access_token']}",
                    'Content-Type': 'application/json; charset=UTF-8'
                },
                json={'publish_id': publish_id}
            )

            status_data = status_response.json()

            return {
                'success': True,
                'video_id': publish_id,
                'status': status_data.get('data', {}).get('status'),
                'platform': 'tiktok'
            }

        except Exception as e:
            print(f"[TIKTOK] Upload error: {e}")
            return {'success': False, 'error': str(e)}

    # ======================
    # Instagram API Integration
    # ======================

    def get_instagram_auth_url(self, user_email: str, redirect_uri: str) -> Optional[str]:
        """Generate Instagram OAuth URL"""
        config_file = self.credentials_dir / "instagram_config.json"
        if not config_file.exists():
            print("[INSTAGRAM] Config file not found. Create instagram_config.json")
            return None

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            # Instagram uses Facebook OAuth
            app_id = config['app_id']

            # Generate state
            import secrets
            state = secrets.token_urlsafe(32)
            self._store_oauth_state(user_email, 'instagram', state)

            # Scopes for Instagram Content Publishing
            scope = 'instagram_basic,instagram_content_publish,pages_show_list'

            auth_url = (
                f"https://www.facebook.com/v18.0/dialog/oauth"
                f"?client_id={app_id}"
                f"&redirect_uri={redirect_uri}"
                f"&state={state}"
                f"&scope={scope}"
            )

            return auth_url

        except Exception as e:
            print(f"[INSTAGRAM] Error generating auth URL: {e}")
            return None

    def handle_instagram_callback(self, user_email: str, code: str, state: str, redirect_uri: str) -> bool:
        """Handle Instagram OAuth callback"""
        stored_state = self._get_oauth_state(user_email, 'instagram')
        if not stored_state or stored_state != state:
            return False

        config_file = self.credentials_dir / "instagram_config.json"

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            # Exchange code for access token
            response = requests.get(
                'https://graph.facebook.com/v18.0/oauth/access_token',
                params={
                    'client_id': config['app_id'],
                    'client_secret': config['app_secret'],
                    'redirect_uri': redirect_uri,
                    'code': code
                }
            )

            data = response.json()

            if 'access_token' in data:
                # Get Instagram account ID
                ig_response = requests.get(
                    'https://graph.facebook.com/v18.0/me/accounts',
                    params={'access_token': data['access_token']}
                )

                ig_data = ig_response.json()

                self._store_platform_credentials(user_email, 'instagram', {
                    'access_token': data['access_token'],
                    'token_type': data.get('token_type'),
                    'expires_in': data.get('expires_in'),
                    'accounts': ig_data.get('data', [])
                })
                return True

            return False

        except Exception as e:
            print(f"[INSTAGRAM] Error handling callback: {e}")
            return False

    # ======================
    # Facebook API Integration
    # ======================

    def get_facebook_auth_url(self, user_email: str, redirect_uri: str) -> Optional[str]:
        """Generate Facebook OAuth URL"""
        config_file = self.credentials_dir / "facebook_config.json"
        if not config_file.exists():
            print("[FACEBOOK] Config file not found. Create facebook_config.json with app_id and app_secret")
            return None

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            app_id = config['app_id']

            # Generate state
            import secrets
            state = secrets.token_urlsafe(32)
            self._store_oauth_state(user_email, 'facebook', state)

            # Scopes for Facebook Pages
            scope = 'pages_show_list,pages_read_engagement,pages_manage_posts,publish_video'

            auth_url = (
                f"https://www.facebook.com/v18.0/dialog/oauth"
                f"?client_id={app_id}"
                f"&redirect_uri={redirect_uri}"
                f"&state={state}"
                f"&scope={scope}"
            )

            return auth_url

        except Exception as e:
            print(f"[FACEBOOK] Error generating auth URL: {e}")
            return None

    def handle_facebook_callback(self, user_email: str, code: str, state: str, redirect_uri: str) -> bool:
        """Handle Facebook OAuth callback and store page info in channel_accounts"""
        stored_state = self._get_oauth_state(user_email, 'facebook')
        if not stored_state or stored_state != state:
            print("[FACEBOOK] State mismatch")
            return False

        config_file = self.credentials_dir / "facebook_config.json"

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            # Exchange code for access token
            response = requests.get(
                'https://graph.facebook.com/v18.0/oauth/access_token',
                params={
                    'client_id': config['app_id'],
                    'client_secret': config['app_secret'],
                    'redirect_uri': redirect_uri,
                    'code': code
                }
            )

            data = response.json()

            if 'access_token' not in data:
                print(f"[FACEBOOK] No access token in response: {data}")
                return False

            access_token = data['access_token']

            # Get Facebook pages
            pages_response = requests.get(
                'https://graph.facebook.com/v18.0/me/accounts',
                params={'access_token': access_token}
            )

            pages_data = pages_response.json()

            if 'data' not in pages_data or len(pages_data['data']) == 0:
                print("[FACEBOOK] No pages found for this account")
                return False

            # Store credentials
            self._store_platform_credentials(user_email, 'facebook', {
                'access_token': access_token,
                'token_type': data.get('token_type'),
                'expires_in': data.get('expires_in'),
                'pages': pages_data['data']
            })

            # Add each page to channel_accounts table
            if hasattr(self, 'analytics_manager') and self.analytics_manager:
                for page in pages_data['data']:
                    channel_data = {
                        'channel_id': page['id'],
                        'channel_name': page['name'],
                        'channel_handle': page.get('username', ''),
                        'thumbnail_url': f"https://graph.facebook.com/{page['id']}/picture?type=large",
                        'access_token': page.get('access_token', access_token)  # Page-specific token
                    }

                    try:
                        self.analytics_manager.add_channel_account(user_email, 'facebook', channel_data)
                        print(f"[FACEBOOK] Added page: {page['name']}")
                    except Exception as e:
                        print(f"[FACEBOOK] Error adding page {page['name']}: {e}")

            return True

        except Exception as e:
            print(f"[FACEBOOK] Error handling callback: {e}")
            import traceback
            traceback.print_exc()
            return False

    def upload_to_instagram_reel(self, user_email: str, video_url: str, caption: str,
                                 instagram_account_id: str) -> Dict[str, Any]:
        """Upload video to Instagram Reels"""
        creds = self._get_platform_credentials(user_email, 'instagram')
        if not creds:
            return {'success': False, 'error': 'Instagram not connected'}

        try:
            access_token = creds['access_token']

            # Step 1: Create media container
            container_response = requests.post(
                f'https://graph.facebook.com/v18.0/{instagram_account_id}/media',
                params={
                    'media_type': 'REELS',
                    'video_url': video_url,
                    'caption': caption[:2200],  # Max 2200 chars
                    'share_to_feed': True,
                    'access_token': access_token
                }
            )

            container_data = container_response.json()

            if 'id' not in container_data:
                return {'success': False, 'error': container_data.get('error', {}).get('message', 'Unknown error')}

            container_id = container_data['id']

            # Step 2: Publish media
            publish_response = requests.post(
                f'https://graph.facebook.com/v18.0/{instagram_account_id}/media_publish',
                params={
                    'creation_id': container_id,
                    'access_token': access_token
                }
            )

            publish_data = publish_response.json()

            if 'id' in publish_data:
                media_id = publish_data['id']
                return {
                    'success': True,
                    'video_id': media_id,
                    'url': f'https://www.instagram.com/reel/{media_id}',
                    'platform': 'instagram_reels'
                }

            return {'success': False, 'error': publish_data.get('error', {}).get('message', 'Publish failed')}

        except Exception as e:
            print(f"[INSTAGRAM] Upload error: {e}")
            return {'success': False, 'error': str(e)}

    # ======================
    # Helper Methods
    # ======================

    def _store_oauth_state(self, user_email: str, platform: str, state: str):
        """Store OAuth state for CSRF protection"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS oauth_states (
                user_email TEXT,
                platform TEXT,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_email, platform)
            )
        ''')

        c.execute('''
            INSERT OR REPLACE INTO oauth_states (user_email, platform, state)
            VALUES (?, ?, ?)
        ''', (user_email, platform, state))

        conn.commit()
        conn.close()

    def _get_oauth_state(self, user_email: str, platform: str) -> Optional[str]:
        """Retrieve OAuth state"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        c = conn.cursor()

        c.execute('''
            SELECT state FROM oauth_states
            WHERE user_email = ? AND platform = ?
        ''', (user_email, platform))

        result = c.fetchone()
        conn.close()

        return result[0] if result else None

    def _store_platform_credentials(self, user_email: str, platform: str, credentials: Dict[str, Any]):
        """Store platform OAuth credentials"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS platform_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                platform TEXT NOT NULL,
                credentials TEXT,
                access_token TEXT,
                refresh_token TEXT,
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                UNIQUE(user_email, platform)
            )
        ''')

        # Security: Encrypt sensitive tokens before storing
        try:
            from web.utils.encryption import encrypt_token
            access_token = credentials.get('access_token') or credentials.get('token')
            refresh_token = credentials.get('refresh_token')
            
            # Encrypt tokens
            encrypted_access = encrypt_token(access_token) if access_token else None
            encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None
            
            # Store encrypted credentials JSON (tokens already encrypted above, store separately)
            credentials_copy = credentials.copy()
            if encrypted_access:
                credentials_copy['access_token'] = encrypted_access
                credentials_copy['token'] = encrypted_access
            if encrypted_refresh:
                credentials_copy['refresh_token'] = encrypted_refresh
            
            encrypted_credentials_json = json.dumps(credentials_copy)
        except Exception as e:
            print(f"[PLATFORM_API] Encryption failed, storing unencrypted (INSECURE): {e}")
            encrypted_access = credentials.get('access_token') or credentials.get('token')
            encrypted_refresh = credentials.get('refresh_token')
            encrypted_credentials_json = json.dumps(credentials)

        # Calculate expiration
        expires_at = None
        if 'expires_in' in credentials:
            expires_at = (datetime.now() + timedelta(seconds=credentials['expires_in'])).isoformat()

        c.execute('''
            INSERT OR REPLACE INTO platform_connections
            (user_email, platform, credentials, access_token, refresh_token, connected_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'active')
        ''', (
            user_email,
            platform,
            encrypted_credentials_json,
            encrypted_access,
            encrypted_refresh,
            expires_at
        ))

        conn.commit()
        conn.close()

    def _get_platform_credentials(self, user_email: str, platform: str) -> Optional[Dict[str, Any]]:
        """Retrieve and decrypt platform credentials"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        c = conn.cursor()

        c.execute('''
            SELECT credentials FROM platform_connections
            WHERE user_email = ? AND platform = ? AND status = 'active'
        ''', (user_email, platform))

        result = c.fetchone()
        conn.close()

        if result:
            credentials_data = json.loads(result[0])
            
            # Security: Decrypt tokens
            try:
                from web.utils.encryption import decrypt_token
                
                # Decrypt access token
                if 'access_token' in credentials_data:
                    decrypted = decrypt_token(credentials_data['access_token'])
                    if decrypted:
                        credentials_data['access_token'] = decrypted
                        credentials_data['token'] = decrypted
                
                # Decrypt refresh token
                if 'refresh_token' in credentials_data:
                    decrypted = decrypt_token(credentials_data['refresh_token'])
                    if decrypted:
                        credentials_data['refresh_token'] = decrypted
            except Exception as e:
                print(f"[PLATFORM_API] Decryption failed, using stored value: {e}")
                # If decryption fails, assume token is plaintext (backward compatibility)
            
            return credentials_data
        return None

    def is_platform_connected(self, user_email: str, platform: str) -> bool:
        """Check if platform is connected"""
        return self._get_platform_credentials(user_email, platform) is not None

    def disconnect_platform(self, user_email: str, platform: str) -> bool:
        """Disconnect a platform"""
        import time

        max_retries = 5
        retry_delay = 0.1  # 100ms

        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=10.0)  # 10 second timeout
                c = conn.cursor()

                c.execute('''
                    UPDATE platform_connections
                    SET status = 'disconnected'
                    WHERE user_email = ? AND platform = ?
                ''', (user_email, platform))

                success = c.rowcount > 0
                conn.commit()
                conn.close()

                return success

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"[PLATFORM_API] Database locked, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"[PLATFORM_API] Error disconnecting platform: {e}")
                    raise
            except Exception as e:
                print(f"[PLATFORM_API] Unexpected error disconnecting platform: {e}")
                try:
                    conn.close()
                except:
                    pass
                raise

        return False

    def get_connected_platforms_list(self, user_email: str) -> list:
        """Get list of connected platforms"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT platform, connected_at, expires_at
            FROM platform_connections
            WHERE user_email = ? AND status = 'active'
        ''', (user_email,))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_and_store_youtube_channel(self, user_email: str, analytics_manager) -> Dict[str, Any]:
        """
        Get YouTube channel info and store it in channel_accounts table
        Returns the channel info
        """
        channel_info = self.get_youtube_channel_info(user_email)

        if not channel_info.get('success'):
            return channel_info

        # Store channel in database (or update if exists)
        try:
            existing_channel = analytics_manager.get_channel_by_id(
                channel_info['channel_id'],
                user_email,
                'youtube'
            )

            if not existing_channel:
                # Add new channel
                channel_account_id = analytics_manager.add_channel_account(user_email, 'youtube', {
                    'channel_id': channel_info['channel_id'],
                    'channel_name': channel_info['title'],
                    'channel_handle': channel_info.get('custom_url', ''),
                    'channel_custom_url': channel_info.get('custom_url', ''),
                    'channel_description': channel_info.get('description', ''),
                    'thumbnail_url': channel_info.get('thumbnail', '')
                })
                channel_info['channel_account_id'] = channel_account_id
                print(f"[YOUTUBE] Added new channel: {channel_info['title']} (ID: {channel_account_id})")
            else:
                # Reactivate existing channel if it was deactivated
                channel_account_id = existing_channel['id']
                conn = sqlite3.connect(analytics_manager.db_path, timeout=10.0)
                c = conn.cursor()
                c.execute('''
                    UPDATE channel_accounts
                    SET is_active = 1, is_default = 1
                    WHERE id = ? AND user_email = ?
                ''', (channel_account_id, user_email))
                conn.commit()
                conn.close()

                channel_info['channel_account_id'] = channel_account_id
                print(f"[YOUTUBE] Reactivated existing channel: {channel_info['title']} (ID: {channel_account_id})")

            return channel_info

        except Exception as e:
            print(f"[YOUTUBE] Error storing channel: {e}")
            return channel_info  # Return info even if storage fails

    # ==================== GOOGLE CALENDAR OAUTH ====================

    def get_google_calendar_auth_url(self, user_email: str, redirect_uri: str) -> Optional[str]:
        """Generate Google Calendar OAuth URL (reuses YouTube client secrets)"""
        if not GOOGLE_AVAILABLE:
            return None

        # Use same client secrets as YouTube (already has calendar scope)
        client_secrets_file = self.credentials_dir / "youtube_client_secrets.json"
        if not client_secrets_file.exists():
            print("[GOOGLE-CAL] Client secrets file not found. YouTube connection required.")
            return None

        try:
            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_secrets_file(
                str(client_secrets_file),
                scopes=['https://www.googleapis.com/auth/calendar.events'],
                redirect_uri=redirect_uri
            )

            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )

            self._store_oauth_state(user_email, 'google_calendar', state)
            print(f"[GOOGLE-CAL] Generated auth URL for user: {user_email}")

            return auth_url

        except Exception as e:
            print(f"[GOOGLE-CAL] Error generating auth URL: {e}")
            return None

    def handle_google_calendar_callback(self, user_email: str, code: str, state: str, redirect_uri: str) -> bool:
        """Handle Google Calendar OAuth callback"""
        print(f"[GOOGLE-CAL] Callback handler called for user: {user_email}")

        if not GOOGLE_AVAILABLE:
            return False

        # Verify state
        stored_state = self._get_oauth_state(user_email, 'google_calendar')
        if not stored_state or stored_state != state:
            print(f"[GOOGLE-CAL] State verification failed")
            return False

        client_secrets_file = self.credentials_dir / "youtube_client_secrets.json"

        try:
            from google_auth_oauthlib.flow import Flow

            # Use all scopes since Google may return all previously granted scopes
            flow = Flow.from_client_secrets_file(
                str(client_secrets_file),
                scopes=[
                    'https://www.googleapis.com/auth/calendar.events',
                    'https://www.googleapis.com/auth/youtube.upload',
                    'https://www.googleapis.com/auth/youtube',
                    'https://www.googleapis.com/auth/youtube.force-ssl'
                ],
                redirect_uri=redirect_uri
            )

            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Store credentials in platform_connections
            self._store_platform_credentials(
                user_email,
                'google_calendar',
                {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                }
            )

            print(f"[GOOGLE-CAL] Successfully stored credentials for user: {user_email}")
            return True

        except Exception as e:
            print(f"[GOOGLE-CAL] Error handling callback: {e}")
            import traceback
            traceback.print_exc()
            return False
