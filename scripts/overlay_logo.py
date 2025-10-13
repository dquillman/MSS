from pathlib import Path
import sys
import subprocess
import imageio_ffmpeg


def overlay(video_path: str, logo_path: str, position: str = 'bottom-left', opacity: float = 0.6, scale_h: int = 100) -> Path:
    """
    Overlay a PNG logo onto a video using ffmpeg.

    Args:
        video_path: Input MP4 path
        logo_path: PNG path (ideally with alpha)
        position: one of bottom-left, bottom-right, top-left, top-right, center
        opacity: 0.0..1.0 alpha applied to logo
        scale_h: logo height in pixels (width auto)

    Returns: output Path (<name>_logo.mp4)
    """
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    pos_map = {
        'bottom-right': 'W-w-20:H-h-20',
        'bottom-left': '20:H-h-20',
        'top-right': 'W-w-20:20',
        'top-left': '20:20',
        'center': '(W-w)/2:(H-h)/2',
    }
    pos = pos_map.get(position, '20:H-h-20')

    video = Path(video_path)
    logo = Path(logo_path)
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video}")
    if not logo.exists():
        raise FileNotFoundError(f"Logo not found: {logo}")

    out = video.with_name(video.stem + '_logo.mp4')
    filter_complex = (
        f"[1:v]scale=-1:{scale_h},format=yuva420p,colorchannelmixer=aa={opacity}[logo];"
        f"[0:v][logo]overlay={pos}"
    )
    cmd = [
        ffmpeg,
        '-i', str(video),
        '-i', str(logo),
        '-filter_complex', filter_complex,
        '-c:v', 'libx264',
        '-c:a', 'copy',
        '-y', str(out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not out.exists():
        sys.stderr.write((res.stderr or '')[:600])
        raise SystemExit(1)
    print(str(out))
    return out


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python scripts/overlay_logo.py <video.mp4> <logo.png> [position]")
        sys.exit(2)
    video = sys.argv[1]
    logo = sys.argv[2]
    pos = sys.argv[3] if len(sys.argv) > 3 else 'bottom-left'
    overlay(video, logo, pos)

