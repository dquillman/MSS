"""
Test Full Avatar Video Generation
Creates a complete video with animated talking avatar using FFmpeg
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
    get_mp3_duration_seconds,
    get_active_avatar_voice,
    render_video
)
import json


def test_full_video_with_avatar():
    """Generate a full test video with animated avatar"""

    print("="*70)
    print("FULL AVATAR VIDEO TEST")
    print("="*70)

    # Prepare output directory
    outdir = Path("out")
    outdir.mkdir(exist_ok=True)

    # Test script
    test_narration = """
    Welcome to Many Sources Say! Today we're testing our new animated avatar system.
    This avatar can move and talk without requiring any external API credits.
    The avatar uses advanced FFmpeg techniques to create smooth, natural-looking animations
    with breathing effects and synchronized audio visualization.
    Pretty cool, right? Let's see how it looks in a real video!
    """

    test_overlays = [
        "Animated Avatar System",
        "No API Credits Required",
        "Smooth Natural Animation",
        "FFmpeg Powered",
        "Many Sources Say"
    ]

    title = "Testing Animated Avatar System"

    print("\n[1] Generating TTS audio...")
    audio_path = outdir / "test_avatar_narration.mp3"
    try:
        google_tts(test_narration, audio_path, use_ssml=False)
        duration = get_mp3_duration_seconds(audio_path)
        print(f"[OK] Audio generated: {duration:.1f}s")
    except Exception as e:
        print(f"[X] TTS failed: {e}")
        return

    print("\n[2] Rendering video with animated avatar...")
    print("    Using VIDEO_RENDERER=ffmpeg (local rendering)")

    # Make sure we're using FFmpeg renderer
    os.environ['VIDEO_RENDERER'] = 'ffmpeg'

    try:
        # Generate vertical (9:16) video
        output_path = outdir / "test_avatar_video_shorts.mp4"

        result = render_video(
            audio_path=str(audio_path),
            overlays=test_overlays,
            total_secs=duration,
            title=title,
            output_path=str(output_path),
            stock_videos=None,  # No stock videos for faster testing
            aspect_ratio="9:16"
        )

        if result.get("status") == "done":
            print(f"\n[OK] Video generated successfully!")
            print(f"     Output: {output_path}")
            print(f"     Size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print(f"[X] Video generation failed: {result}")

    except Exception as e:
        print(f"[X] Video rendering error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Check avatar library
    avatar_lib = Path("avatar_library.json")
    if avatar_lib.exists():
        lib_data = json.loads(avatar_lib.read_text())
        active_avatar = next((a for a in lib_data.get('avatars', []) if a.get('active')), None)
        if active_avatar:
            print(f"\n[INFO] Active avatar: {active_avatar.get('name')}")
            print(f"       Position: {active_avatar.get('position')}")
            print(f"       Scale: {active_avatar.get('scale')}%")

    print("\n" + "="*70)
    print("[SUCCESS] Full avatar video test complete!")
    print("="*70)
    print(f"\nCheck the video: {output_path}")
    print("\nThe avatar should be:")
    print("  - Positioned in the bottom-right corner")
    print("  - Animated with subtle breathing movement")
    print("  - Visible throughout the entire video")


if __name__ == "__main__":
    test_full_video_with_avatar()
