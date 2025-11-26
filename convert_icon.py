
from PIL import Image
import os
import sys

def convert_png_to_ico(png_path, ico_path):
    try:
        img = Image.open(png_path)
        img.save(ico_path, format='ICO', sizes=[(256, 256)])
        print(f"Successfully converted {png_path} to {ico_path}")
        return True
    except Exception as e:
        print(f"Error converting image: {e}")
        return False

if __name__ == "__main__":
    png_file = r"g:\Users\daveq\MSS\web\topic-picker-standalone\favicon.png"
    ico_file = r"g:\Users\daveq\MSS\web\topic-picker-standalone\favicon.ico"
    
    if os.path.exists(png_file):
        convert_png_to_ico(png_file, ico_file)
    else:
        print(f"Source file not found: {png_file}")
