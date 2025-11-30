from PIL import Image, ImageDraw

W, H = 1280, 720
BG = (11, 15, 25)
INK = (232, 235, 255)
ACCENT_RED = (230, 57, 70)
ACCENT_BLUE = (59, 130, 246)

img = Image.new('RGB', (W, H), BG)
d = ImageDraw.Draw(img)

# Header
d.rectangle([(0, 0), (W, 90)], fill=(16, 22, 38))
d.text((40, 25), 'Many Sources Say — Blog→Video Autopilot', fill=INK)

padding = 40
col_w = (W - padding * 5) // 4
col_h = H - 160
y0 = 120
x = padding
cols = [
    ('Source Input', [
        '• URL (fetch HTML)',
        '• Google Doc (export text)',
        '• Google Sheets row',
    ]),
    ('Draft & TTS', [
        '• OpenAI: narration + overlays + YT meta',
        '• Google TTS: en-US Neural, 1.03x',
        '• MP3 uploaded to Drive',
    ]),
    ('Render', [
        '• Shotstack 1080×1920',
        '• Gradient bg + HTML overlays',
        '• Poll until status=done',
    ]),
    ('Publish & Log', [
        '• MP4 to Drive (public)',
        '• YouTube upload + captions',
        '• Append/Update Google Sheet',
    ]),
]

for title, bullets in cols:
    d.rounded_rectangle([(x, y0), (x + col_w, y0 + col_h)], radius=12, outline=(48, 62, 90), width=2, fill=(18, 24, 38))
    d.text((x + 16, y0 + 14), title, fill=INK)
    yy = y0 + 54
    for b in bullets:
        d.text((x + 16, yy), b, fill=(200, 210, 235))
        yy += 34
    x += col_w + padding

# Arrows between columns
def arrow(cx):
    d.polygon([(cx - 10, y0 + col_h // 2 - 10), (cx - 10, y0 + col_h // 2 + 10), (cx + 10, y0 + col_h // 2)], fill=ACCENT_BLUE)

arrow(col_w + padding * 2)
arrow(col_w * 2 + padding * 3)
arrow(col_w * 3 + padding * 4)

d.text((40, H - 40), 'v2: Google TTS + Drive, MP3 probe, Shotstack render, YouTube + captions, Sheets idempotency', fill=(180, 190, 210))

import os
os.makedirs('out', exist_ok=True)
img.save('out/app_mock.jpg', quality=92)

