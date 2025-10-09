import json
from pathlib import Path
from typing import Optional
import time

import imageio_ffmpeg


def load_library(lib_path: Path) -> dict:
    if not lib_path.exists():
        raise FileNotFoundError(f"Library not found: {lib_path}")
    return json.loads(lib_path.read_text(encoding="utf-8"))


def save_library(lib_path: Path, data: dict) -> None:
    lib_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def bake_item(kind: str, item: dict, out_dir: Path, ffmpeg: str) -> Optional[Path]:
    html = item.get("html")
    video_url = item.get("videoUrl")
    duration = float(item.get("duration", 3.0) or 3.0)

    if video_url:
        print(f"[{kind.upper()}] Skipping bake; already has videoUrl: {video_url}")
        return None
    if not html:
        print(f"[{kind.upper()}] No HTML to bake; skipping.")
        return None

    ts = int(time.time())
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{kind}_baked_{ts}.mp4"

    try:
        from scripts.html_to_video import render_html_to_video
        render_html_to_video(
            html=html,
            duration=duration,
            width=1080,
            height=1920,
            out_path=out_path,
            ffmpeg=ffmpeg,
            tts_audio_path=None,
        )
        print(f"[{kind.UPPER()}] Baked to: {out_path}")
        return out_path
    except Exception as e:
        print(f"[{kind.upper()}] Bake failed: {e}")
        return None


def main():
    repo_root = Path(__file__).parent.parent
    lib_path = repo_root / "intro_outro_library.json"
    data = load_library(lib_path)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    io_dir = repo_root / "intro_outro"
    io_dir.mkdir(exist_ok=True)

    active_intro = next((x for x in data.get("intros", []) if x.get("active")), None)
    active_outro = next((x for x in data.get("outros", []) if x.get("active")), None)

    if active_intro:
        path = bake_item("intro", active_intro, io_dir, ffmpeg)
        if path:
            url = f"http://localhost:5000/intro_outro/{path.name}"
            active_intro["videoUrl"] = url
            print(f"[INTRO] Updated videoUrl -> {url}")
    else:
        print("[INTRO] No active intro found.")

    if active_outro:
        path = bake_item("outro", active_outro, io_dir, ffmpeg)
        if path:
            url = f"http://localhost:5000/intro_outro/{path.name}"
            active_outro["videoUrl"] = url
            print(f"[OUTRO] Updated videoUrl -> {url}")
    else:
        print("[OUTRO] No active outro found.")

    save_library(lib_path, data)
    print("\n[OK] Saved library with baked videoUrl(s):", lib_path)


if __name__ == "__main__":
    main()

