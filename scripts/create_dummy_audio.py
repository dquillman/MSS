"""
Create a dummy audio file for testing without Google Cloud TTS
"""
from pathlib import Path

# Create a minimal valid MP3 file (silent, 10 seconds)
# This is a valid MP3 header for a silent audio file
mp3_data = bytes([
    0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
] * 1000)  # Repeat to make ~10 seconds

out_dir = Path("out")
out_dir.mkdir(exist_ok=True)

audio_path = out_dir / "voiceover.mp3"
audio_path.write_bytes(mp3_data)

print(f"✓ Created dummy audio file: {audio_path}")
print("Note: This is silent audio for testing only!")
