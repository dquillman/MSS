"""Check if avatar images have transparent backgrounds"""
from pathlib import Path
from PIL import Image

avatar_files = [
    "avatars/avatar_1759458414.png",
    "avatars/avatar_1759460414.png",
    "avatars/avatar_1759460639.png"
]

for avatar_path in avatar_files:
    path = Path(avatar_path)
    if not path.exists():
        print(f"[SKIP] {avatar_path} - File not found")
        continue

    img = Image.open(path)
    print(f"\n{avatar_path}:")
    print(f"  Mode: {img.mode}")
    print(f"  Size: {img.size}")
    print(f"  Format: {img.format}")

    if img.mode == 'RGBA':
        # Check if there's actual transparency
        alpha = img.split()[3]
        alpha_min = min(alpha.getdata())
        alpha_max = max(alpha.getdata())
        print(f"  Alpha channel range: {alpha_min} - {alpha_max}")

        if alpha_min < 255:
            print(f"  [OK] Has transparent pixels")
        else:
            print(f"  [WARNING] No transparent pixels (fully opaque)")
    elif img.mode == 'RGB':
        print(f"  [WARNING] No alpha channel (RGB mode)")
    else:
        print(f"  [INFO] Unusual mode: {img.mode}")
