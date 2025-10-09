"""
Generate a professional male avatar with transparent background
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import requests
from rembg import remove
from PIL import Image
import io

load_dotenv()

def generate_male_avatar():
    """Generate a professional male news anchor avatar"""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = """Professional male news anchor headshot portrait:

- Professional male news anchor in his 30s-40s
- Wearing a business suit with tie
- Clean, professional appearance
- Neutral, friendly expression
- Looking directly at camera
- Shoulders and upper torso visible
- Plain white or light gray background
- Professional studio lighting
- High quality, photorealistic
- Sharp focus on face
- NO graphics, NO text, NO logos
- Professional headshot style
"""

    print("[DALL-E] Generating male avatar...")
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="hd",
        n=1,
    )

    image_url = response.data[0].url
    print(f"[OK] Image generated: {image_url}")

    # Download image
    print("[DOWNLOAD] Downloading image...")
    img_response = requests.get(image_url, timeout=30)
    img_response.raise_for_status()

    # Save original
    original_path = Path("avatars") / f"male_avatar_original.png"
    original_path.write_bytes(img_response.content)
    print(f"[OK] Original saved: {original_path}")

    # Remove background
    print("[REMBG] Removing background...")
    input_img = Image.open(io.BytesIO(img_response.content))
    output_img = remove(input_img)

    # Save with transparent background
    output_path = Path("avatars") / f"male_avatar_no_bg.png"
    output_img.save(output_path, "PNG")
    print(f"[OK] Background removed: {output_path}")

    return output_path

if __name__ == "__main__":
    avatar_path = generate_male_avatar()
    print(f"\n[SUCCESS] Male avatar created: {avatar_path}")
    print("  Add this to your avatar library via the web UI!")
