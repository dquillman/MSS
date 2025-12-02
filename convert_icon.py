
from PIL import Image
import os

source_path = r"g:\Users\daveq\MSS\web\topic-picker-standalone\favicon.jpg"
dest_path = r"g:\Users\daveq\MSS\web\topic-picker-standalone\favicon.ico"

try:
    img = Image.open(source_path)
    # Resize to standard icon sizes
    img.save(dest_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Successfully converted {source_path} to {dest_path}")
except Exception as e:
    print(f"Error converting image: {e}")
