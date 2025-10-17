"""
YouTube Credentials Setup Helper
Run this script to set up your YouTube API credentials for MSS
"""

import os
import json
from pathlib import Path

def main():
    print("=" * 60)
    print("YouTube API Credentials Setup for MSS")
    print("=" * 60)
    print()

    # Check if credentials directory exists
    creds_dir = Path("web/platform_credentials")
    creds_dir.mkdir(exist_ok=True)

    youtube_secrets_file = creds_dir / "youtube_client_secrets.json"

    if youtube_secrets_file.exists():
        print("✓ youtube_client_secrets.json already exists!")
        print(f"  Location: {youtube_secrets_file}")

        overwrite = input("\nDo you want to overwrite it? (yes/no): ").strip().lower()
        if overwrite != 'yes':
            print("Exiting without changes.")
            return

    print()
    print("To get YouTube API credentials, you need to:")
    print()
    print("1. Go to Google Cloud Console:")
    print("   https://console.cloud.google.com/")
    print()
    print("2. Create a new project (or select existing)")
    print()
    print("3. Enable YouTube Data API v3:")
    print("   - Go to 'APIs & Services' > 'Library'")
    print("   - Search for 'YouTube Data API v3'")
    print("   - Click 'Enable'")
    print()
    print("4. Create OAuth 2.0 Credentials:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Click '+ CREATE CREDENTIALS' > 'OAuth client ID'")
    print("   - Application type: 'Web application'")
    print("   - Name: 'MSS YouTube Integration'")
    print("   - Authorized redirect URIs:")
    print("     - http://localhost:5000/api/oauth/youtube/callback")
    print("     - http://127.0.0.1:5000/api/oauth/youtube/callback")
    print("   - Click 'Create'")
    print()
    print("5. Download the JSON file")
    print()
    print("=" * 60)
    print()

    choice = input("Do you have the credentials JSON downloaded? (yes/no): ").strip().lower()

    if choice == 'yes':
        print()
        print("Please provide the path to your downloaded JSON file:")
        json_path = input("Path: ").strip().strip('"').strip("'")

        if not os.path.exists(json_path):
            print(f"✗ Error: File not found: {json_path}")
            return

        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            # Validate structure
            if 'web' not in data and 'installed' not in data:
                print("✗ Error: Invalid JSON structure. Expected 'web' or 'installed' key.")
                return

            # Copy to credentials directory
            with open(youtube_secrets_file, 'w') as f:
                json.dump(data, f, indent=2)

            print()
            print("✓ Success! YouTube credentials saved!")
            print(f"  Location: {youtube_secrets_file}")
            print()
            print("You can now:")
            print("1. Start your MSS server: python web/api_server.py")
            print("2. Go to Channel Manager")
            print("3. Click 'Add YouTube Channel'")
            print()

        except json.JSONDecodeError:
            print("✗ Error: Invalid JSON file")
        except Exception as e:
            print(f"✗ Error: {e}")

    else:
        print()
        print("Manual Setup:")
        print()
        print("You need to enter your credentials manually.")
        print()

        print("Enter your Client ID (from Google Cloud Console):")
        client_id = input("Client ID: ").strip()

        print("Enter your Client Secret (from Google Cloud Console):")
        client_secret = input("Client Secret: ").strip()

        if not client_id or not client_secret:
            print("✗ Error: Client ID and Client Secret are required")
            return

        # Create the credentials JSON
        credentials = {
            "web": {
                "client_id": client_id,
                "project_id": "mss-youtube-integration",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret,
                "redirect_uris": [
                    "http://localhost:5000/api/oauth/youtube/callback",
                    "http://127.0.0.1:5000/api/oauth/youtube/callback"
                ]
            }
        }

        with open(youtube_secrets_file, 'w') as f:
            json.dump(credentials, f, indent=2)

        print()
        print("✓ Success! YouTube credentials saved!")
        print(f"  Location: {youtube_secrets_file}")
        print()
        print("You can now:")
        print("1. Start your MSS server: python web/api_server.py")
        print("2. Go to Channel Manager")
        print("3. Click 'Add YouTube Channel'")
        print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
