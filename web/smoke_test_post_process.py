import io
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg


def make_dummy_video(path: Path, duration: float = 2.0, color: str = "black", tone: bool = True, size: str = "1080x1920"):
    """Create a small mp4 using the bundled ffmpeg."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    path.parent.mkdir(parents=True, exist_ok=True)

    inputs = [
        "-f", "lavfi", "-i", f"color=c={color}:s={size}:d={duration}",
    ]
    if tone:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}"]
    else:
        inputs += ["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration}"]

    cmd = [
        ffmpeg,
        *inputs,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-y", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[:400]}")


def run_smoke_tests():
    # Import app from api_server
    import sys
    sys.path.append(str(Path(__file__).parent))
    import api_server  # noqa

    app = api_server.app
    outdir = Path("out")
    outdir.mkdir(exist_ok=True)

    # Create dummy videos
    main_path = outdir / "dummy_main.mp4"
    intro_path = outdir / "dummy_intro.mp4"
    outro_path = outdir / "dummy_outro.mp4"

    make_dummy_video(main_path, duration=2.0, color="black", tone=True)
    make_dummy_video(intro_path, duration=1.0, color="red", tone=False)
    make_dummy_video(outro_path, duration=1.0, color="blue", tone=False)

    client = app.test_client()

    # Case 1: Skip intro/outro
    with main_path.open("rb") as f:
        data = {
            "video": (io.BytesIO(f.read()), "main.mp4"),
            "use_did": "false",
            "add_intro_outro": "false",
        }
        resp = client.post("/post-process-video", data=data, content_type="multipart/form-data")
        print("[SMOKE] skip intro/outro status:", resp.status_code)
        print("[SMOKE] response:", resp.json)

    # Case 2: Include intro/outro with uploads
    with main_path.open("rb") as f_main, intro_path.open("rb") as f_intro, outro_path.open("rb") as f_outro:
        data = {
            "video": (io.BytesIO(f_main.read()), "main.mp4"),
            "intro_video": (io.BytesIO(f_intro.read()), "intro.mp4"),
            "outro_video": (io.BytesIO(f_outro.read()), "outro.mp4"),
            "use_did": "false",
            "add_intro_outro": "true",
        }
        resp = client.post("/post-process-video", data=data, content_type="multipart/form-data")
        print("[SMOKE] include intro/outro status:", resp.status_code)
        print("[SMOKE] response:", resp.json)


if __name__ == "__main__":
    run_smoke_tests()

