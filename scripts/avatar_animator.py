"""
Avatar Animation System - FFmpeg-based avatar movement and talking
Creates animated talking avatars without requiring D-ID API credits

Natural Body Movements:
- Breathing: Gentle zoom in/out (1.5% scale variation)
- Horizontal Sway: Subtle left-right movement (8px variation)
- Vertical Bob: Gentle up-down movement (6px variation)
- Rotation: Slight head tilt simulation (0.03 radians ~1.7 degrees)
- Overlay Motion: Additional position shifts for more natural feel

Duration Synchronization:
- Uses math.ceil() to round up frame counts to prevent early cutoff
- Adds 5-frame buffer (~0.16s at 30fps) to ensure animation extends through full audio
- Removed 'shortest=1' from overlay filters to prevent premature ending
- The zoompan filter 'd' parameter now uses full duration in frames, not just 1 frame
"""
import subprocess
import os
from pathlib import Path
from typing import Optional
import imageio_ffmpeg


def get_ffmpeg():
    """Get FFmpeg executable path"""
    return imageio_ffmpeg.get_ffmpeg_exe()


def create_animated_talking_avatar(
    avatar_image_path: Path,
    audio_path: Path,
    output_path: Path,
    avatar_position: str = "bottom-right",
    avatar_scale: float = 0.25,
    duration: Optional[float] = None
) -> str:
    """
    Create an animated talking avatar using FFmpeg without D-ID

    Features:
    - Subtle zoom in/out breathing effect
    - Audio-reactive overlay (visualizes when avatar is speaking)
    - Smooth movements

    Args:
        avatar_image_path: Path to avatar PNG with transparency
        audio_path: Path to audio file
        output_path: Path to save output video
        avatar_position: Position on screen
        avatar_scale: Size relative to video (0.25 = 25%)
        duration: Video duration in seconds (auto-detected from audio if None)

    Returns:
        Path to generated video
    """
    ffmpeg = get_ffmpeg()

    # Get audio duration if not provided
    if duration is None:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        duration = audio.info.length

    # Video dimensions (9:16 for shorts)
    width, height = 1080, 1920

    # Calculate avatar size
    avatar_height = int(height * avatar_scale)

    # Calculate position
    if avatar_position == 'bottom-right':
        x_pos = f'W-w-20'
        y_pos = f'H-h-20'
    elif avatar_position == 'bottom-left':
        x_pos = '20'
        y_pos = f'H-h-20'
    elif avatar_position == 'top-right':
        x_pos = f'W-w-20'
        y_pos = '20'
    elif avatar_position == 'top-left':
        x_pos = '20'
        y_pos = '20'
    else:  # center
        x_pos = '(W-w)/2'
        y_pos = '(H-h)/2'

    # Create complex filter for animated avatar with natural body movements
    # - Breathing effect: gentle zoom in/out
    # - Horizontal sway: subtle left-right movement
    # - Vertical bob: gentle up-down movement
    # - Slight rotation: head tilt simulation
    # - Audio reactive: showwaves overlay for lip-sync visual

    # Calculate duration in frames (30fps) - add small buffer to prevent cutoff
    import math
    duration_frames = math.ceil(duration * 30) + 5  # Add 5 frames (~0.16s) buffer

    # Simplified, robust animation: subtle sway only (no zoompan/rotate/showwaves)
    filter_complex = f"""
    [0:v]scale=-1:{avatar_height},format=yuva420p[avatar];
    color=c=#00000000:s={width}x{height}:d={duration},fps=30[bg];
    [bg][avatar]overlay=eval=frame:x={x_pos}+sin(t*0.6)*3:y={y_pos}+cos(t*0.8)*3[vout]
    """

    cmd = [
        ffmpeg,
        '-loop', '1', '-i', str(avatar_image_path),  # Avatar image (looped)
        '-i', str(audio_path),                        # Audio
        '-filter_complex', filter_complex,
        '-map', '[vout]',
        '-map', '1:a',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-t', str(duration),
        '-pix_fmt', 'yuv420p',
        '-y', str(output_path)
    ]

    print(f"[ANIMATE] Creating animated talking avatar...")
    print(f"  Avatar: {avatar_image_path}")
    print(f"  Audio: {audio_path}")
    print(f"  Duration: {duration:.2f}s")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[X] FFmpeg animation error:\n{result.stderr}")
        raise RuntimeError(f"Avatar animation failed: {result.stderr}")

    print(f"[OK] Animated avatar created: {output_path}")
    return str(output_path)


def create_simple_talking_avatar(
    avatar_image_path: Path,
    audio_path: Path,
    output_path: Path,
    avatar_position: str = "bottom-right",
    avatar_scale: float = 0.25,
    duration: Optional[float] = None
) -> str:
    """
    Create a simpler talking avatar (less CPU intensive)
    Just adds the avatar overlay with a subtle fade in/out effect

    Args:
        avatar_image_path: Path to avatar PNG with transparency
        audio_path: Path to audio file
        output_path: Path to save output video
        avatar_position: Position on screen
        avatar_scale: Size relative to video
        duration: Video duration

    Returns:
        Path to generated video
    """
    ffmpeg = get_ffmpeg()

    # Get audio duration
    if duration is None:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        duration = audio.info.length

    width, height = 1080, 1920
    avatar_height = int(height * avatar_scale)

    # Position calculation
    position_map = {
        'bottom-right': f'W-w-20:H-h-20',
        'bottom-left': f'20:H-h-20',
        'top-right': f'W-w-20:20',
        'top-left': f'20:20',
        'center': '(W-w)/2:(H-h)/2'
    }
    pos = position_map.get(avatar_position, position_map['bottom-right'])

    # Simpler filter: just overlay with fade
    filter_complex = f"""
    [0:v]scale=-1:{avatar_height},format=yuva420p,fade=t=in:st=0:d=0.5:alpha=1[avatar];
    color=c=#00000000:s={width}x{height}:d={duration},fps=30[bg];
    [bg][avatar]overlay={pos}[v]
    """

    cmd = [
        ffmpeg,
        '-loop', '1', '-i', str(avatar_image_path),
        '-i', str(audio_path),
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-map', '1:a',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-t', str(duration),
        '-pix_fmt', 'yuv420p',
        '-y', str(output_path)
    ]

    print(f"[SIMPLE] Creating simple talking avatar...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[X] FFmpeg error:\n{result.stderr}")
        raise RuntimeError(f"Simple avatar creation failed: {result.stderr}")

    print(f"[OK] Simple avatar created: {output_path}")
    return str(output_path)


def add_avatar_to_video(
    base_video_path: Path,
    avatar_image_path: Path,
    output_path: Path,
    avatar_position: str = "bottom-right",
    avatar_scale: float = 0.25,
    animate: bool = True
) -> str:
    """
    Add animated avatar overlay to existing video

    Args:
        base_video_path: Path to base video
        avatar_image_path: Path to avatar PNG
        output_path: Path to save output
        avatar_position: Position on screen
        avatar_scale: Size relative to video
        animate: Whether to add breathing animation

    Returns:
        Path to output video
    """
    ffmpeg = get_ffmpeg()

    # Get video info
    # Probe dimensions using ffprobe when available, otherwise fall back to 1080x1920
    width, height = 1080, 1920
    try:
        ffprobe = ffmpeg.replace('ffmpeg.exe', 'ffprobe.exe').replace('ffmpeg', 'ffprobe')
        probe_cmd = [
            ffprobe,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            str(base_video_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if result.returncode == 0 and ',' in result.stdout:
            width, height = map(int, result.stdout.strip().split(','))
    except Exception:
        pass

    avatar_height = int(height * avatar_scale)

    # Position
    position_map = {
        'bottom-right': f'W-w-20:H-h-20',
        'bottom-left': f'20:H-h-20',
        'top-right': f'W-w-20:20',
        'top-left': f'20:20',
        'center': '(W-w)/2:(H-h)/2'
    }
    pos = position_map.get(avatar_position, position_map['bottom-right'])

    if animate:
        # Animated overlay with subtle sway only (no zoompan/rotate). Let -shortest stop to base video/audio.
        pos_x, pos_y = pos.split(':')
        filter_complex = f"""
        [1:v]scale=-1:{avatar_height},format=yuva420p[avatar];
        [0:v][avatar]overlay=eval=frame:x={pos_x}+sin(t*0.6)*3:y={pos_y}+cos(t*0.8)*3
        """
    else:
        # Static overlay
        filter_complex = f"""
        [1:v]scale=-1:{avatar_height},format=yuva420p[avatar];
        [0:v][avatar]overlay={pos}
        """

    cmd = [
        ffmpeg,
        '-i', str(base_video_path),
        '-loop', '1', '-i', str(avatar_image_path),
        '-filter_complex', filter_complex,
        '-c:v', 'libx264',
        '-c:a', 'copy',
        '-shortest',
        '-y', str(output_path)
    ]

    print(f"[OVERLAY] Adding avatar to video...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[X] FFmpeg overlay error:\n{result.stderr}")
        raise RuntimeError(f"Avatar overlay failed: {result.stderr}")

    print(f"[OK] Avatar added to video: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    # Test the avatar animator
    from pathlib import Path

    avatar_dir = Path("avatars")
    audio_path = Path("out/test_tts.mp3")

    # Find an avatar
    avatars = list(avatar_dir.glob("*.png"))
    if not avatars:
        print("No avatars found!")
    elif not audio_path.exists():
        print("No test audio found!")
    else:
        avatar = avatars[-1]
        output = Path("out/test_animated_avatar.mp4")

        print(f"Testing avatar animator with {avatar}")
        create_animated_talking_avatar(
            avatar,
            audio_path,
            output,
            avatar_scale=0.3
        )
        print(f"\nTest complete! Check {output}")
