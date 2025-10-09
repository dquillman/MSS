from pathlib import Path
from typing import Optional
import subprocess
import tempfile


def render_html_to_video(
    html: str,
    duration: float,
    width: int,
    height: int,
    out_path: Path,
    ffmpeg: str,
    tts_audio_path: Optional[Path] = None,
) -> Path:
    """
    Render HTML to an MP4 video using Playwright (Chromium) screen recording.
    Falls back to a single-frame PNG -> MP4 if Playwright is unavailable.

    Args:
        html: HTML content to render
        duration: seconds
        width, height: output size
        out_path: target MP4 path
        ffmpeg: path to ffmpeg executable
        tts_audio_path: optional MP3 to mux

    Returns:
        Path to MP4 file
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Prepare HTML content with fixed sizing and neutral background
            html_doc = f"""
            <html>
              <head>
                <meta charset='utf-8'>
                <style>
                  html, body {{ margin:0; padding:0; width:100%; height:100%; background:#0B0F19; }}
                  .root {{ width:{width}px; height:{height}px; }}
                </style>
              </head>
              <body>
                <div class='root'>
                  {html}
                </div>
              </body>
            </html>
            """

            html_file = tmpdir_path / "index.html"
            html_file.write_text(html_doc, encoding="utf-8")

            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    record_video_dir=str(tmpdir_path),
                    record_video_size={"width": width, "height": height},
                )
                page = context.new_page()
                page.goto(html_file.as_uri())
                # Allow animations to play
                page.wait_for_timeout(int(duration * 1000))
                context.close()
                browser.close()

            # Find the recorded webm video in temp dir
            webms = list(tmpdir_path.glob("**/*.webm"))
            if not webms:
                raise RuntimeError("No recorded video found from Playwright")

            webm_in = webms[0]
            # Convert to mp4 and optionally mux audio
            if tts_audio_path and Path(tts_audio_path).exists():
                cmd = [
                    ffmpeg,
                    "-i",
                    str(webm_in),
                    "-i",
                    str(tts_audio_path),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "30",
                    "-c:a",
                    "aac",
                    "-shortest",
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(out_path),
                ]
            else:
                cmd = [
                    ffmpeg,
                    "-i",
                    str(webm_in),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "30",
                    "-an",
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(out_path),
                ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"Playwright render ffmpeg failed: {res.stderr[:300]}")

            return out_path

    except Exception as e:
        # Fallback: simple PNG -> MP4 with optional audio
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            png = tmpdir_path / "frame.png"
            try:
                from PIL import Image, ImageDraw, ImageFont
                img = Image.new("RGB", (width, height), color="#0B0F19")
                draw = ImageDraw.Draw(img)
                # Basic text extraction: strip tags and draw first two lines
                import re
                text = re.sub(r"<[^>]+>", "\n", html or "")
                lines = [s.strip() for s in re.split(r"\n+", text) if s.strip()][:2]
                try:
                    font_title = ImageFont.truetype("arial.ttf", 64)
                    font_sub = ImageFont.truetype("arial.ttf", 36)
                except Exception:
                    font_title = ImageFont.load_default()
                    font_sub = ImageFont.load_default()
                y = height // 2 - 40
                if lines:
                    w, h = draw.textsize(lines[0], font=font_title)
                    draw.text(((width - w) // 2, y), lines[0], fill="#FFD700", font=font_title)
                    y += h + 10
                if len(lines) > 1:
                    w, h = draw.textsize(lines[1], font=font_sub)
                    draw.text(((width - w) // 2, y), lines[1], fill="#94a3b8", font=font_sub)
                img.save(png)
            except Exception:
                png.write_bytes(b"")

            if tts_audio_path and Path(tts_audio_path).exists():
                cmd = [
                    ffmpeg,
                    "-loop",
                    "1",
                    "-i",
                    str(png),
                    "-i",
                    str(tts_audio_path),
                    "-t",
                    str(duration),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(out_path),
                ]
            else:
                cmd = [
                    ffmpeg,
                    "-loop",
                    "1",
                    "-i",
                    str(png),
                    "-t",
                    str(duration),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-an",
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(out_path),
                ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"Fallback PNG->MP4 failed: {res.stderr[:300]}")
            return out_path

