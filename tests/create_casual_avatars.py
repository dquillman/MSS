"""
Generate casual podcast-style avatars with DALL-E
Avatars sitting at desk with microphone - both male and female
"""

import os
from pathlib import Path
from openai import OpenAI
import requests
from PIL import Image
from rembg import remove
import io
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_casual_avatar(gender="male"):
    """Generate a casual avatar sitting at desk with microphone"""

    # Gender-specific prompts
    if gender == "male":
        prompt = """Professional male podcaster in casual attire sitting at desk with microphone:
        - Man in his 30s-40s wearing casual button-down shirt or polo
        - Sitting at a modern desk with a professional podcast microphone in front
        - Friendly, approachable expression, slight smile
        - Looking directly at camera
        - Well-lit home office or podcast studio background
        - Clean, professional but casual vibe
        - High quality, photorealistic headshot style
        - Plain or slightly blurred background for easy removal"""

        name_prefix = "casual_male"
    else:
        prompt = """Professional female podcaster in casual attire sitting at desk with microphone:
        - Woman in her 30s-40s wearing casual blouse or sweater
        - Sitting at a modern desk with a professional podcast microphone in front
        - Friendly, approachable expression, slight smile
        - Looking directly at camera
        - Well-lit home office or podcast studio background
        - Clean, professional but casual vibe
        - High quality, photorealistic headshot style
        - Plain or slightly blurred background for easy removal"""

        name_prefix = "casual_female"

    print(f"\n[DALL-E] Generating {gender} casual avatar with microphone...")
    print(f"[PROMPT] {prompt[:100]}...")

    # Generate image with DALL-E
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="hd",
        n=1,
    )

    image_url = response.data[0].url
    print(f"[OK] Image generated: {image_url}")

    # Download the image
    img_response = requests.get(image_url)
    if img_response.status_code != 200:
        print(f"[ERROR] Failed to download image")
        return None

    # Load image
    input_img = Image.open(io.BytesIO(img_response.content))

    # Create avatars directory if it doesn't exist
    avatars_dir = Path("avatars")
    avatars_dir.mkdir(exist_ok=True)

    # Save original with background
    import time
    timestamp = int(time.time())
    original_path = avatars_dir / f"{name_prefix}_with_bg_{timestamp}.png"
    input_img.save(original_path, "PNG")
    print(f"[OK] Saved original: {original_path}")

    # Remove background
    print(f"[REMBG] Removing background...")
    output_img = remove(input_img)

    # Save without background
    output_path = avatars_dir / f"{name_prefix}_no_bg_{timestamp}.png"
    output_img.save(output_path, "PNG")
    print(f"[OK] Saved no-background: {output_path}")

    return output_path

def add_to_avatar_library(avatar_path, gender, name):
    """Add the new avatar to avatar_library.json"""

    library_path = Path("avatar_library.json")

    if library_path.exists():
        library = json.loads(library_path.read_text(encoding="utf-8"))
    else:
        library = {"avatars": []}

    # Create new avatar entry
    import time
    timestamp = int(time.time())

    new_avatar = {
        "id": f"avatar_{timestamp}",
        "name": name,
        "type": "image",
        "image_url": f"http://localhost:5000/avatars/{avatar_path.name}",
        "video_url": "",
        "position": "bottom-right",
        "scale": 18,
        "opacity": 100,
        "voice": "en-US-News-L" if gender == "male" else "en-US-News-K",
        "gender": gender,
        "active": False
    }

    # Add to library
    library["avatars"].append(new_avatar)

    # Save library
    library_path.write_text(json.dumps(library, indent=2), encoding="utf-8")
    print(f"[OK] Added {name} to avatar_library.json")

    return new_avatar

if __name__ == "__main__":
    print("=" * 70)
    print("Casual Avatar Generator - Podcast Style")
    print("=" * 70)

    # Generate male casual avatar
    male_path = generate_casual_avatar("male")
    if male_path:
        add_to_avatar_library(male_path, "male", "Casual Mike")

    # Generate female casual avatar
    female_path = generate_casual_avatar("female")
    if female_path:
        add_to_avatar_library(female_path, "female", "Casual Sarah")

    print("\n" + "=" * 70)
    print("Done! Check avatar_library.json and avatars/ folder")
    print("=" * 70)
