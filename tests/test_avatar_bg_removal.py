"""Test script to diagnose avatar background removal"""
import sys
from pathlib import Path
from PIL import Image
from rembg import remove

# Test with the most recent avatar
avatar_path = Path("avatars/avatar_1759458414.png")

if not avatar_path.exists():
    print(f"❌ Avatar file not found: {avatar_path}")
    sys.exit(1)

print(f"Testing background removal on: {avatar_path}")
print(f"File size: {avatar_path.stat().st_size / 1024:.2f} KB")

try:
    # Load the image
    input_img = Image.open(avatar_path)
    print(f"Image mode: {input_img.mode}")
    print(f"Image size: {input_img.size}")

    # Remove background
    print("Removing background...")
    output_img = remove(input_img)

    print(f"Output image mode: {output_img.mode}")
    print(f"Output image size: {output_img.size}")

    # Save test output
    test_output = Path("avatars/test_output_no_bg.png")
    output_img.save(test_output)
    print(f"✓ Successfully saved test output to: {test_output}")
    print(f"Output file size: {test_output.stat().st_size / 1024:.2f} KB")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
