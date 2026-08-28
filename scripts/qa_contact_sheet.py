"""Monta uma folha de contato (grid) com as miniaturas dos slides."""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

THUMB = sys.argv[1] if len(sys.argv) > 1 else ".qa/thumbs"
OUT = sys.argv[2] if len(sys.argv) > 2 else ".qa/contato_deck.png"
COLS = 3
label_h = 26
bg_color = (15, 18, 25)
border = (38, 116, 248)

files = sorted(f for f in os.listdir(THUMB) if f.endswith(".png"))
imgs = [Image.open(os.path.join(THUMB, f)) for f in files]
W, H = imgs[0].size
rows = (len(imgs) + COLS - 1) // COLS
cw, ch = W, H + label_h
grid_w = COLS * cw
grid_h = rows * ch
canvas = Image.new("RGB", (grid_w, grid_h), bg_color)
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("arial.ttf", 18)
except Exception:
    font = ImageFont.load_default()

for idx, im in enumerate(imgs):
    r, c = divmod(idx, COLS)
    x, y = c * cw, r * ch
    draw.rectangle([x, y, x + cw - 4, y + ch - 6], outline=border, width=2)
    canvas.paste(im, (x + 6, y + label_h))
    draw.text((x + 12, y + 6), f"Slide {idx + 1:02d}", fill=(220, 230, 245), font=font)

canvas.save(OUT)
print(f"Folha de contato: {OUT} ({grid_w}x{grid_h}px, {len(imgs)} slides)")