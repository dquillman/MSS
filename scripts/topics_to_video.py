import json
import os
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

# Reuse helpers from make_video
from scripts.make_video import (
    read_env,
    ensure_dir,
    openai_generate_topics,
    openai_draft_from_topic,
    google_tts,
    drive_upload_public,
    get_mp3_duration_seconds,
    build_shotstack_payload,
    build_shotstack_payload_wide,
    shotstack_render_and_download,
    shotstack_thumbnail,
    shotstack_render,
    shotstack_poll,
    youtube_upload,
    sheets_append_log,
)

# Import new utilities
from scripts.video_utils import (
    get_stock_footage_for_keywords,
    generate_thumbnail_variants,
    generate_chapter_markers,
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
    parser = argparse.ArgumentParser(description="Topic→Pick→Video (dual renders + thumbnail)")
    parser.add_argument("--brand", default=os.getenv("MSS_BRAND", "Many Sources Say"))
    parser.add_argument("--schedule", help="ISO8601 publish time for YouTube (requires privacy=private)")
    parser.add_argument("--privacy", default=os.getenv("YOUTUBE_PRIVACY_STATUS", "unlisted"))
    args = parser.parse_args()

    brand = args.brand
    outdir = Path("out")
    ensure_dir(outdir)

    # 1) Generate topics
    topics = openai_generate_topics(brand)
    (outdir / "topics.json").write_text(json.dumps({"topics": topics}, indent=2), encoding="utf-8")

    # 2) Pick one
    chosen = pick_topic(topics)
    (outdir / "topic_selected.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")

    # 3) Draft from topic
    draft = openai_draft_from_topic(chosen)
    (outdir / "script.json").write_text(json.dumps(draft, indent=2), encoding="utf-8")

    narration = draft["narration"]
    overlays = draft["overlays"]
    title = draft["title"]
    description = draft["description"]
    tags = draft["keywords"]

    # 4) Get stock footage (if enabled)
    stock_videos = []
    visual_cues = draft.get("visual_cues", tags[:5])
    if os.getenv("ENABLE_STOCK_FOOTAGE", "false").lower() in {"true", "1", "yes"}:
        print(f"Fetching stock footage for: {', '.join(visual_cues[:3])}...")
        stock_videos = get_stock_footage_for_keywords(visual_cues, max_clips=3)
        print(f"Found {len(stock_videos)} stock video clips")

    # 5) TTS via Google with SSML
    audio_path = outdir / "voiceover.mp3"
    print("Generating voiceover (Google TTS with SSML)...")
    google_tts(narration, audio_path, use_ssml=True)
    dur = get_mp3_duration_seconds(audio_path)
    print(f"Audio duration: {dur:.1f}s")

    # 6) Upload audio to Drive (public)
    print("Uploading audio to Drive (public)...")
    audio_up = drive_upload_public(audio_path, os.getenv("DRIVE_AUDIO_FOLDER", "/autopilot/audio/"))
    audio_url = audio_up["download_url"]

    # 7) Shotstack render - PARALLEL execution
    print("Submitting parallel renders (shorts + wide)...")
    payload_v = build_shotstack_payload(audio_url, overlays, dur, title, stock_videos)
    payload_w = build_shotstack_payload_wide(audio_url, overlays, dur, title, stock_videos)

    (outdir / "shotstack_vertical.json").write_text(json.dumps(payload_v, indent=2), encoding="utf-8")
    (outdir / "shotstack_wide.json").write_text(json.dumps(payload_w, indent=2), encoding="utf-8")

    # Submit both renders
    submit_v = shotstack_render(payload_v)
    submit_w = shotstack_render(payload_w)
    render_id_v = submit_v.get("response", {}).get("id") or submit_v.get("id")
    render_id_w = submit_w.get("response", {}).get("id") or submit_w.get("id")

    print(f"Vertical render ID: {render_id_v}")
    print(f"Wide render ID: {render_id_w}")

    # Poll both renders in parallel
    def poll_and_download(render_id, out_path):
        print(f"Polling {out_path.name}...")
        final = shotstack_poll(render_id)
        url = final.get("response", {}).get("url") or final.get("url")
        import requests
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with out_path.open("wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
        return {"render_id": render_id, "url": url}

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_v = executor.submit(poll_and_download, render_id_v, outdir / "shorts.mp4")
        future_w = executor.submit(poll_and_download, render_id_w, outdir / "wide.mp4")

        res_v = future_v.result()
        res_w = future_w.result()

    print("✓ Both renders completed!")

    # 8) Generate thumbnail variants (using enhanced generator)
    print("Generating thumbnail variants...")
    thumb_variants = generate_thumbnail_variants(title, outdir, count=int(os.getenv("THUMBNAIL_VARIANTS", "3")))
    print(f"Created {len(thumb_variants)} thumbnail variants")
    thumb = {"url": str(thumb_variants[0])} if thumb_variants else shotstack_thumbnail(title, outdir / "thumb.jpg")

    # 8) Upload MP4s to Drive
    print("Uploading videos to Drive (public)...")
    vid_v_up = drive_upload_public(outdir / "shorts.mp4", os.getenv("DRIVE_RENDERS_FOLDER", "/autopilot/renders/"))
    vid_w_up = drive_upload_public(outdir / "wide.mp4", os.getenv("DRIVE_RENDERS_FOLDER", "/autopilot/renders/"))

    # 9) Generate chapter markers
    chapter_markers = generate_chapter_markers(overlays, dur)

    # 10) YouTube upload (optional) with scheduling + thumbnail + chapters
    yt_url = None
    if os.getenv("DISABLE_YT_UPLOAD") not in {"1", "true", "TRUE"}:
        print("Uploading to YouTube (shorts)...")
        schedule_iso = args.schedule or os.getenv("SCHEDULE_PUBLISH_ISO")
        privacy = args.privacy
        if schedule_iso and privacy != "private":
            print("Note: Scheduling requires privacy=private. Overriding to private.")
            privacy = "private"
        # Use first thumbnail variant
        thumb_path = thumb_variants[0] if thumb_variants else outdir / "thumb.jpg"
        yt_url = youtube_upload(outdir / "shorts.mp4", title, description, tags, privacy,
                               publish_at_iso=schedule_iso, thumbnail_path=thumb_path,
                               chapter_markers=chapter_markers)

    # 10) Summary
    summary = {
        "topic": chosen,
        "title": title,
        "audio_url": audio_url,
        "vertical": {"render_id": res_v.get("render_id"), "video_url": res_v.get("url"), "drive_view": vid_v_up.get("view_url")},
        "wide": {"render_id": res_w.get("render_id"), "video_url": res_w.get("url"), "drive_view": vid_w_up.get("view_url")},
        "thumbnail_url": thumb.get("url"),
        "youtube_url": yt_url,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nDone. Summary at:", outdir / "summary.json")

    # 11) Sheets log (optional)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    sheets_append_log([
        now,
        title,
        f"{dur:.1f}",
        res_v.get("render_id"),
        res_v.get("url"),
        res_w.get("render_id"),
        res_w.get("url"),
        yt_url or "",
    ])


if __name__ == "__main__":
    main()
