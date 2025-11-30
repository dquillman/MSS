"""
Test version of topics_to_video.py that skips TTS
This lets you test the system without Google Cloud credentials
"""
import json
import os
from pathlib import Path
import argparse

from dotenv import load_dotenv

# Reuse helpers from make_video
from scripts.make_video import (
    read_env,
    ensure_dir,
    openai_generate_topics,
    openai_draft_from_topic,
)

# Import new utilities
from scripts.video_utils import (
    generate_thumbnail_variants,
)


def pick_topic(topics):
    print("\nToday's topic ideas (SEO-optimized):\n")
    for i, t in enumerate(topics, 1):
        print(f"{i}. {t['title']} — {t.get('angle','')}")
    while True:
        raw = input("\nPick a topic [1-5] (or 'q' to quit): ").strip()
        if raw.lower() in {"q", "quit", "exit"}:
            raise SystemExit(0)
        if raw.isdigit() and 1 <= int(raw) <= min(5, len(topics)):
            return topics[int(raw) - 1]
        print("Invalid choice. Please enter a number between 1 and 5.")


def main():
    read_env()
    parser = argparse.ArgumentParser(description="Topic→Pick→Video (TEST VERSION - No TTS)")
    parser.add_argument("--brand", default=os.getenv("MSS_BRAND", "Many Sources Say"))
    args = parser.parse_args()

    brand = args.brand
    outdir = Path("out")
    ensure_dir(outdir)

    # 1) Generate topics
    print("\n🤖 Generating SEO-optimized topics...\n")
    topics = openai_generate_topics(brand)
    (outdir / "topics.json").write_text(json.dumps({"topics": topics}, indent=2), encoding="utf-8")
    print(f"✓ Generated {len(topics)} topics\n")

    # 2) Pick one
    chosen = pick_topic(topics)
    (outdir / "topic_selected.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    print(f"\n✓ Topic selected: {chosen['title']}\n")

    # 3) Draft from topic
    print("📝 Drafting script with hook optimization...")
    draft = openai_draft_from_topic(chosen)
    (outdir / "script.json").write_text(json.dumps(draft, indent=2), encoding="utf-8")

    narration = draft["narration"]
    overlays = draft["overlays"]
    title = draft["title"]
    description = draft["description"]
    tags = draft["keywords"]

    print(f"✓ Script created ({len(narration.split())} words)\n")

    # 4) Create dummy audio for testing
    print("🎤 Creating test audio file (silent)...")
    audio_path = outdir / "voiceover.mp3"

    # Create a minimal valid MP3 file
    mp3_data = bytes([
        0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ] * 5000)  # ~50 seconds

    audio_path.write_bytes(mp3_data)
    print(f"✓ Test audio created: {audio_path}")
    print("  (Note: This is silent audio for testing)\n")

    # 5) Generate thumbnail variants
    print("🎨 Generating thumbnail variants...")
    thumb_variants = generate_thumbnail_variants(title, outdir, count=3)
    print(f"✓ Created {len(thumb_variants)} thumbnail variants:\n")
    for thumb in thumb_variants:
        print(f"  - {thumb.name}")

    # 6) Summary
    print("\n" + "="*60)
    print("✨ TEST RUN COMPLETE!")
    print("="*60)
    print(f"\n📁 Output files in: {outdir.absolute()}\n")
    print("Generated:")
    print(f"  ✓ Topics: topics.json")
    print(f"  ✓ Selected: topic_selected.json")
    print(f"  ✓ Script: script.json")
    print(f"  ✓ Audio: voiceover.mp3 (silent test file)")
    print(f"  ✓ Thumbnails: thumb_variant_1.jpg, thumb_variant_2.jpg, thumb_variant_3.jpg")

    print("\n" + "="*60)
    print("📊 WHAT'S WORKING:")
    print("="*60)
    print("  ✅ OpenAI topic generation")
    print("  ✅ OpenAI script writing with hooks")
    print("  ✅ SEO optimization (keywords, tags)")
    print("  ✅ Thumbnail variant generation")

    print("\n" + "="*60)
    print("⏭️  NEXT STEPS:")
    print("="*60)
    print("  1. Set up Google Cloud TTS for voice")
    print("  2. Set up Shotstack for video rendering")
    print("  3. Set up Google Drive for storage")
    print("  4. Set up YouTube OAuth for publishing")

    print("\n" + "="*60)
    print("📖 See UPGRADE_GUIDE.md for setup instructions")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
