"""
FFmpeg-based video rendering (replaces Shotstack)
Composites all video elements locally without watermarks
"""
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import imageio_ffmpeg

def get_ffmpeg():
    """Get FFmpeg executable path"""
    return imageio_ffmpeg.get_ffmpeg_exe()

def render_video_with_ffmpeg(
    audio_path: str,
    overlays: List[str],
    output_path: str,
    intro_outro: Dict[str, Any],
    avatar_data: Optional[Dict[str, Any]] = None,
    stock_videos: Optional[List[str]] = None,
    aspect_ratio: str = "9:16",
    resolution: str = "1080x1920"
) -> str:
    """
    Render video using FFmpeg instead of Shotstack

    Args:
        audio_path: Path to audio file
        overlays: List of text overlays
        output_path: Where to save the final video
        intro_outro: Dict with intro/outro HTML and durations
        avatar_data: Avatar configuration (image_url, position, scale, opacity)
        stock_videos: Optional list of stock video URLs
        aspect_ratio: "9:16" or "16:9"
        resolution: Output resolution (e.g., "1080x1920")

    Returns:
        Path to rendered video file
    """
    ffmpeg = get_ffmpeg()

    # Parse durations
    intro_duration = intro_outro.get("intro_duration", 3.0)
    outro_duration = intro_outro.get("outro_duration", 3.0)

    # Get audio duration
    from mutagen.mp3 import MP3
    audio = MP3(audio_path)
    content_duration = audio.info.length
    total_duration = intro_duration + content_duration + outro_duration

    # Determine dimensions
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:  # 16:9
        width, height = 1920, 1080

    # Step 1: Create intro video
    intro_video = Path(output_path).parent / "intro_temp.mp4"
    create_intro_video(intro_video, intro_outro, intro_duration, width, height, ffmpeg)

    # Step 2: Create outro video
    outro_video = Path(output_path).parent / "outro_temp.mp4"
    create_outro_video(outro_video, intro_outro, outro_duration, width, height, ffmpeg)

    # Step 3: Create main content video with overlays
    content_video = Path(output_path).parent / "content_temp.mp4"
    create_content_video(
        content_video, audio_path, overlays, content_duration,
        width, height, stock_videos, ffmpeg
    )

    # Step 4: Concatenate intro + content + outro
    concat_list = Path(output_path).parent / "concat_list.txt"
    with open(concat_list, 'w') as f:
        f.write(f"file '{intro_video.absolute()}'\n")
        f.write(f"file '{content_video.absolute()}'\n")
        f.write(f"file '{outro_video.absolute()}'\n")

    temp_concat = Path(output_path).parent / "temp_concat.mp4"
    cmd = [
        ffmpeg, '-f', 'concat', '-safe', '0', '-i', str(concat_list),
        '-c:v', 'libx264', '-c:a', 'aac',  # Re-encode both video and audio for compatibility
        '-y', str(temp_concat)
    ]

    print(f"\n[CONCAT] Concatenating videos...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[X] FFmpeg concat error:\n{result.stderr}")
        raise RuntimeError(f"Video concatenation failed: {result.stderr}")
    print(f"   [OK] Videos concatenated: {temp_concat}")

    # Step 5: Add avatar overlay if provided
    if avatar_data:
        add_avatar_overlay(temp_concat, output_path, avatar_data, total_duration, width, height, ffmpeg, audio_path=audio_path)
    else:
        import shutil
        shutil.copy(temp_concat, output_path)

    # Cleanup temp files - DISABLED FOR DEBUGGING
    # import time
    # time.sleep(0.5)
    #
    # for temp_file in [intro_video, outro_video, content_video, concat_list, temp_concat]:
    #     try:
    #         temp_file.unlink(missing_ok=True)
    #     except (PermissionError, OSError):
    #         # File still in use, skip cleanup
    #         pass

    print(f"\n[DEBUG] Temp files preserved:")
    print(f"   Intro: {intro_video}")
    print(f"   Content: {content_video}")
    print(f"   Outro: {outro_video}")
    print(f"   Concat list: {concat_list}")
    print(f"   Temp concat: {temp_concat}")

    return str(output_path)


def _extract_lines_from_html(html: str, max_lines: int = 2) -> List[str]:
    text = re.sub(r"<[^>]+>", "\n", html or "")
    text = re.sub(r"\s+", " ", text)
    # Recover line breaks between blocks
    lines = [s.strip() for s in re.split(r"\n+", text) if s and s.strip()]
    # Heuristic: pick up to max_lines of non-empty strings with reasonable length
    out = []
    for s in lines:
        if 1 <= len(s) <= 200:
            out.append(s)
        if len(out) >= max_lines:
            break
    if not out:
        out = ["MANY SOURCES SAY"]
    return out


def _build_drawtext_filters(lines: List[str], width: int, height: int) -> str:
    # Escape for ffmpeg
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    if not lines:
        lines = ["MANY SOURCES SAY"]
    # Position lines vertically around center
    filters = []
    if len(lines) == 1:
        filters.append(f"drawtext=text='{esc(lines[0])}':fontsize=96:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2")
    else:
        filters.append(f"drawtext=text='{esc(lines[0])}':fontsize=84:fontcolor=white:x=(w-text_w)/2:y=(h/2-60)")
        filters.append(f"drawtext=text='{esc(lines[1])}':fontsize=48:fontcolor=#94a3b8:x=(w-text_w)/2:y=(h/2+10)")
    return ",".join(filters)


def create_intro_video(output_path: Path, intro_outro: Dict, duration: float, width: int, height: int, ffmpeg: str):
    """Create intro video honoring provided HTML/text and optional audio file.

    intro_outro may include:
      - html: HTML template; we extract up to 2 visible lines
      - audio_file: path to MP3 to use instead of silence
    """
    lines = _extract_lines_from_html(intro_outro.get("html", ""), max_lines=2)
    vf = _build_drawtext_filters(lines, width, height)
    audio_file = intro_outro.get("audio_file")

    if audio_file and Path(audio_file).exists():
        inputs = [ffmpeg, '-f', 'lavfi', '-i', f'color=c=#0B0F19:s={width}x{height}:d={duration}', '-i', str(audio_file)]
    else:
        inputs = [ffmpeg, '-f', 'lavfi', '-i', f'color=c=#0B0F19:s={width}x{height}:d={duration}', '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:d={duration}']

    cmd = [
        *inputs,
        '-vf', vf,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-preset', 'veryfast',
        '-crf', '23',
        '-shortest',
        '-y', str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def create_outro_video(output_path: Path, intro_outro: Dict, duration: float, width: int, height: int, ffmpeg: str):
    """Create outro video honoring provided HTML/text and optional audio file."""
    lines = _extract_lines_from_html(intro_outro.get("html", ""), max_lines=2)
    # If nothing meaningful, default outro line
    if lines == ["MANY SOURCES SAY"]:
        lines = ["THANKS FOR WATCHING", "MANY SOURCES SAY"]
    vf = _build_drawtext_filters(lines, width, height)
    audio_file = intro_outro.get("audio_file")

    if audio_file and Path(audio_file).exists():
        inputs = [ffmpeg, '-f', 'lavfi', '-i', f'color=c=#0B0F19:s={width}x{height}:d={duration}', '-i', str(audio_file)]
    else:
        inputs = [ffmpeg, '-f', 'lavfi', '-i', f'color=c=#0B0F19:s={width}x{height}:d={duration}', '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:d={duration}']

    cmd = [
        *inputs,
        '-vf', vf,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-preset', 'veryfast',
        '-crf', '23',
        '-shortest',
        '-y', str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def create_content_video(output_path: Path, audio_path: str, overlays: List[str], duration: float,
                        width: int, height: int, stock_videos: Optional[List[str]], ffmpeg: str):
    """Create main content video with audio and text overlays"""
    import os

    print(f"\n[DEBUG] Content video creation:")
    print(f"   Audio path: {audio_path}")
    print(f"   Audio exists: {os.path.exists(audio_path)}")
    print(f"   Duration: {duration}")

    # Create background
    use_stock = False  # Initialize here

    if stock_videos and len(stock_videos) > 0:
        # Download first stock video and use as background
        import requests
        import hashlib
        video_hash = hashlib.md5(stock_videos[0].encode()).hexdigest()[:8]
        stock_local = output_path.parent / f"stock_{video_hash}.mp4"

        if not stock_local.exists():
            print(f"   [DOWNLOAD] Downloading stock video...")
            try:
                # Add timeout to prevent hanging on large files
                resp = requests.get(stock_videos[0], stream=True, timeout=30)
                resp.raise_for_status()

                # Download with progress check
                total_size = 0
                max_size = 100 * 1024 * 1024  # 100MB limit

                with open(stock_local, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=1024*1024):  # 1MB chunks
                        if chunk:
                            total_size += len(chunk)
                            if total_size > max_size:
                                print(f"   [!] Stock video too large (>{max_size/1024/1024}MB), skipping...")
                                stock_local.unlink(missing_ok=True)
                                use_stock = False
                                break
                            f.write(chunk)

                if not use_stock or not stock_local.exists():
                    print(f"   [!] Using gradient background instead")
                    bg_input = f'color=c=#182032:s={width}x{height}:d={duration}'
                    use_stock = False
            except Exception as e:
                print(f"   [!] Stock download failed: {e}, using gradient background")
                stock_local.unlink(missing_ok=True)
                bg_input = f'color=c=#182032:s={width}x{height}:d={duration}'
                use_stock = False

        if use_stock and stock_local.exists():
            bg_input = str(stock_local)
        else:
            bg_input = f'color=c=#182032:s={width}x{height}:d={duration}'
            use_stock = False
    else:
        bg_input = f'color=c=#182032:s={width}x{height}:d={duration}'
        use_stock = False

    # Build drawtext filter for overlays
    # For now, just use first overlay
    text = overlays[0] if overlays else "News Content"
    text = text.replace(":", "\\:").replace("'", "\\'")  # Escape for FFmpeg

    if use_stock:
        # Use stock video as background, scale and loop as needed
        vf = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setpts=PTS-STARTPTS,loop=loop=-1:size=1:start=0[bg];[bg]drawtext=text='{text}':fontsize=68:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
        cmd = [
            ffmpeg,
            '-stream_loop', '-1', '-i', bg_input,  # Loop stock video
            '-i', audio_path,
            '-filter_complex', vf,
            '-c:v', 'libx264',
            '-preset', 'veryfast',  # Much faster encoding
            '-crf', '23',  # Good quality
            '-c:a', 'aac',
            '-shortest',
            '-y', str(output_path)
        ]
    else:
        # Use solid color background
        vf = f"drawtext=text='{text}':fontsize=68:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
        cmd = [
            ffmpeg,
            '-f', 'lavfi', '-i', bg_input,
            '-i', audio_path,
            '-vf', vf,
            '-c:v', 'libx264',
            '-preset', 'veryfast',  # Much faster encoding
            '-crf', '23',  # Good quality
            '-c:a', 'aac',
            '-shortest',
            '-y', str(output_path)
        ]

    print(f"   Running FFmpeg command...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[X] Content video FFmpeg error:\n{result.stderr}")
        raise RuntimeError(f"Content video creation failed: {result.stderr}")
    print(f"   [OK] Content video created: {output_path}")


def add_avatar_overlay(input_video: Path, output_video: Path, avatar_data: Dict,
                      duration: float, width: int, height: int, ffmpeg: str, audio_path: Optional[str] = None):
    """Add avatar overlay to video - uses animated avatar with FFmpeg"""
    import os
    import requests
    import hashlib
    import time
    from pathlib import Path as P

    avatar_url = avatar_data.get('image_url', '')
    position = avatar_data.get('position', 'bottom-right')
    scale = avatar_data.get('scale', 25) / 100.0  # Convert to decimal
    opacity = avatar_data.get('opacity', 100) / 100.0

    # Check if D-ID is enabled and has credits
    did_api_key = os.getenv("DID_API_KEY")
    did_enabled = False  # Disable D-ID by default, use local animation instead

    # You can enable D-ID by setting USE_DID_ANIMATION=true in .env
    if os.getenv("USE_DID_ANIMATION", "false").lower() == "true":
        did_enabled = did_api_key and did_api_key != "your_d_id_api_key_here"

    print(f"\n[DEBUG] Avatar overlay:")
    print(f"   D-ID enabled: {did_enabled}")
    print(f"   Audio path: {audio_path}")
    print(f"   Using local FFmpeg animation: {not did_enabled}")

    avatar_local = None

    if did_enabled and audio_path:
        # Generate talking avatar with D-ID
        print("[DID] Generating talking avatar with D-ID...")
        try:
            # Import D-ID function from make_video
            import sys
            sys.path.insert(0, str(P(__file__).parent.parent))
            from scripts.make_video import generate_did_talking_avatar, drive_upload_public

            # Generate talking avatar video
            did_output = P(output_video).parent / f"did_avatar_{int(time.time())}.mp4"

            # Upload audio to drive so D-ID can access it
            print(f"[UPLOAD] Uploading audio to Drive for D-ID...")
            audio_result = drive_upload_public(P(audio_path), "MSS_Avatars")
            audio_url = audio_result['download_url']

            # Upload avatar image to drive so D-ID can access it
            print(f"[UPLOAD] Uploading avatar image to Drive for D-ID...")

            # Download avatar if it's a URL
            filename_hash = hashlib.md5(f"{avatar_url}{time.time()}".encode()).hexdigest()[:8]
            avatar_temp = P(output_video).parent / f"avatar_temp_{filename_hash}.png"

            if avatar_url.startswith('http'):
                response = requests.get(avatar_url)
                avatar_temp.write_bytes(response.content)
            else:
                import shutil
                shutil.copy(avatar_url, avatar_temp)

            avatar_result = drive_upload_public(avatar_temp, "MSS_Avatars")
            avatar_image_url = avatar_result['download_url']

            # Generate talking avatar
            did_result = generate_did_talking_avatar(avatar_image_url, audio_url, did_output)

            if did_result:
                # Use the D-ID video as the avatar
                avatar_local = did_output
                print(f"[OK] D-ID talking avatar generated: {avatar_local}")
                # Cleanup temp avatar image since we're using D-ID video
                try:
                    avatar_temp.unlink(missing_ok=True)
                except:
                    pass
            else:
                print("[!] D-ID generation failed, falling back to static image")
                avatar_local = avatar_temp
                # Don't delete avatar_temp, we need it!

        except Exception as e:
            print(f"[!] D-ID error: {e}, falling back to static image")
            did_enabled = False

    if not avatar_local:
        # Use local FFmpeg-based animation (no D-ID needed)

        # Check if it's a localhost URL and convert to local path
        if 'localhost' in avatar_url:
            # Extract filename from localhost URL: http://localhost:5000/avatars/avatar_xxx.png -> avatars/avatar_xxx.png
            import re
            match = re.search(r'/avatars/(avatar_[^/]+\.png)', avatar_url)
            if match:
                avatar_local = P('avatars') / match.group(1)
                if not avatar_local.exists():
                    print(f"[!] Avatar file not found at: {avatar_local}")
                    print(f"[!] Checking current directory for: {match.group(1)}")
                    # Check if file exists in current directory
                    alt_path = P(match.group(1))
                    if alt_path.exists():
                        avatar_local = alt_path
                    else:
                        # List available avatars
                        import os
                        avatars_dir = P('avatars')
                        if avatars_dir.exists():
                            available = list(avatars_dir.glob('*.png'))
                            if available:
                                print(f"[!] Available avatars: {[f.name for f in available]}")
                                # Use the most recent one
                                avatar_local = sorted(available, key=lambda p: p.stat().st_mtime)[-1]
                                print(f"[OK] Using most recent avatar: {avatar_local}")
                            else:
                                print(f"[X] No avatars found in {avatars_dir}")
                                raise FileNotFoundError(f"No avatar images found")
                        else:
                            raise FileNotFoundError(f"Avatars directory not found")
            else:
                # Fallback: just use the filename part
                avatar_local = P('avatars') / avatar_url.split('/')[-1]
        elif avatar_url.startswith('http'):
            # Download external URL
            filename_hash = hashlib.md5(f"{avatar_url}{time.time()}".encode()).hexdigest()[:8]
            avatar_local = P(output_video).parent / f"avatar_temp_{filename_hash}.png"
            response = requests.get(avatar_url)
            avatar_local.write_bytes(response.content)
        else:
            # Already local file path
            avatar_local = P(avatar_url)

    # Calculate avatar size (scale relative to video height)
    avatar_height = int(height * scale)

    # Calculate position
    if position == 'bottom-right':
        x_pos = f'W-w-20'
        y_pos = f'H-h-20'
    elif position == 'bottom-left':
        x_pos = '20'
        y_pos = f'H-h-20'
    elif position == 'top-right':
        x_pos = f'W-w-20'
        y_pos = '20'
    elif position == 'top-left':
        x_pos = '20'
        y_pos = '20'
    else:  # center
        x_pos = '(W-w)/2'
        y_pos = '(H-h)/2'

    # Check if avatar is video (D-ID) or image
    is_video = str(avatar_local).endswith('.mp4')

    if is_video:
        # D-ID talking avatar video - overlay with looping if needed
        cmd = [
            ffmpeg,
            '-i', str(input_video),
            '-stream_loop', '-1', '-i', str(avatar_local),  # Loop avatar video
            '-filter_complex',
            f'[1:v]scale=-1:{avatar_height},setpts=PTS-STARTPTS[avatar];[0:v][avatar]overlay={x_pos}:{y_pos}:shortest=1:format=auto',
            '-c:v', 'libx264', '-c:a', 'copy',
            '-y', str(output_video)
        ]
    else:
        # Animated image avatar with breathing effect
        print(f"[ANIMATE] Adding animated avatar overlay...")

        # Add breathing animation with zoompan (much more subtle!)
        # Scale first, then apply VERY subtle zoom (1.0 +/- 0.005 = 0.5% breathing)
        filter_complex = f"""
        [1:v]scale=-1:{avatar_height}[scaled];
        [scaled]format=yuva420p,zoompan=z='1+sin(time*1.5)*0.005':d=1:fps=30[avatar];
        [0:v][avatar]overlay={x_pos}:{y_pos}:shortest=1
        """

        cmd = [
            ffmpeg,
            '-i', str(input_video),
            '-loop', '1', '-i', str(avatar_local),
            '-filter_complex', filter_complex,
            '-c:v', 'libx264',
            '-preset', 'veryfast',  # Much faster encoding
            '-crf', '23',  # Good quality
            '-c:a', 'copy',
            '-shortest',
            '-y', str(output_video)
        ]

    print(f"[RENDER] Compositing avatar overlay...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[X] FFmpeg error:\n{result.stderr}")
        raise RuntimeError(f"FFmpeg overlay failed: {result.stderr}")

    print(f"[OK] Avatar overlay complete!")

    # Cleanup - delay to ensure FFmpeg releases the file
    time.sleep(0.5)
    if avatar_url.startswith('http'):
        try:
            avatar_local.unlink(missing_ok=True)
        except PermissionError:
            # File still locked, just leave it
            pass
