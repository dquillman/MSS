"""
Test D-ID Talking Avatar Integration
Tests the full pipeline: TTS -> D-ID -> Talking Avatar Video
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.make_video import (
    google_tts,
    drive_upload_public,
    generate_did_talking_avatar,
    get_active_avatar_voice
)

def test_did_api():
    """Test D-ID API connectivity"""
    import requests

    api_key = os.getenv("DID_API_KEY")

    if not api_key or api_key == "your_d_id_api_key_here":
        print("[X] D-ID API key not configured in .env")
        return False

    print(f"[OK] D-ID API key found: {api_key[:20]}...")

    # Test API connection
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get("https://api.d-id.com/credits", headers=headers, timeout=10)
        if response.status_code == 200:
            credits = response.json()
            print(f"[OK] D-ID API connected successfully")
            print(f"  Credits remaining: {credits.get('remaining', 'unknown')}")
            return True
        else:
            print(f"[X] D-ID API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[X] D-ID API connection failed: {e}")
        return False


def test_tts():
    """Test TTS generation"""
    print("\n[TTS] Testing TTS generation...")

    test_text = "Hello! I am your AI avatar. I can talk and move naturally with lip sync."
    out_path = Path("out/test_tts.mp3")
    out_path.parent.mkdir(exist_ok=True)

    try:
        google_tts(test_text, out_path, use_ssml=False)
        print(f"[OK] TTS generated: {out_path}")
        print(f"  File size: {out_path.stat().st_size / 1024:.2f} KB")
        return str(out_path)
    except Exception as e:
        print(f"[X] TTS generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_drive_upload(file_path):
    """Test Google Drive upload"""
    print("\n[DRIVE] Testing Google Drive upload...")

    try:
        result = drive_upload_public(Path(file_path), "MSS_Test")
        print(f"[OK] File uploaded to Drive")
        print(f"  Download URL: {result['download_url']}")
        return result['download_url']
    except Exception as e:
        print(f"[X] Drive upload failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_avatar_talking(audio_path, avatar_image_path):
    """Test D-ID talking avatar generation"""
    print("\n[DID] Testing D-ID talking avatar generation...")

    output_path = Path("out/test_talking_avatar.mp4")

    try:
        # Generate talking avatar using local files
        print("  Generating talking avatar with D-ID...")
        print(f"  Avatar: {avatar_image_path}")
        print(f"  Audio: {audio_path}")
        result = generate_did_talking_avatar(str(avatar_image_path), str(audio_path), output_path)

        if result:
            print(f"[OK] Talking avatar generated: {output_path}")
            print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
            return str(output_path)
        else:
            print("[X] D-ID generation returned None")
            return None
    except Exception as e:
        print(f"[X] Talking avatar generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("="*70)
    print("D-ID TALKING AVATAR TEST")
    print("="*70)

    # Step 1: Test D-ID API
    print("\n[1] Testing D-ID API Connection...")
    if not test_did_api():
        print("\n[X] D-ID API test failed. Check your DID_API_KEY in .env")
        return

    # Step 2: Test TTS
    print("\n[2] Testing TTS Generation...")
    audio_path = test_tts()
    if not audio_path:
        print("\n[X] TTS test failed. Check your Google Cloud credentials")
        return

    # Step 3: Find an avatar image
    print("\n[3] Finding avatar image...")
    avatar_dir = Path("avatars")

    # Use avatar with real face (not logo)
    avatar_image = avatar_dir / "avatar_1759460837.png"

    if not avatar_image.exists():
        print(f"[X] Avatar image not found: {avatar_image}")
        print("   Please ensure you have a face avatar image")
        return

    print(f"[OK] Using avatar: {avatar_image}")

    # Step 4: Test D-ID Talking Avatar
    print("\n[4] Testing D-ID Talking Avatar Generation...")
    video_path = test_avatar_talking(audio_path, avatar_image)

    if video_path:
        print("\n" + "="*70)
        print("[OK] ALL TESTS PASSED!")
        print("="*70)
        print(f"\n[VIDEO] Talking avatar video: {video_path}")
        print("\nYou can now use this avatar in your videos!")
    else:
        print("\n" + "="*70)
        print("[FAIL] TALKING AVATAR TEST FAILED")
        print("="*70)
        print("\nCheck the error messages above for details")


if __name__ == "__main__":
    main()
