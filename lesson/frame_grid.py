"""Замер кадра нового урока: сетка координат + края стены и растений.

Все кропы в compose.py — пиксели конкретной съёмки. Под новый урок их
надо мерить заново, а не переносить числа. Скрипт берёт кадр исходника,
кладёт сетку в пикселях исходника и печатает найденные края:
  • светлую стену слева (её в кадр не пускаем),
  • левую кромку зелени справа (горшок с бамбуком).
Лицо спикера находится глазами по сетке — положите его x в формулы ниже.

    .venv/bin/python tools/frame_grid.py [секунда]   → work/grid.png
"""
import pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
t = sys.argv[1] if len(sys.argv) > 1 else "300"
# исходник, а если его уже нет — мастер (он того же размера кадра)
cands = [q for q in (ROOT / "raw").glob("speaker.*") if q.exists()] + [ROOT / "work/clean.mov"]
src = next(q for q in cands if q.exists())
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", t, "-i", str(src),
                "-frames:v", "1", "-y", str(ROOT / "work/frame.png")], check=True)
im = Image.open(ROOT / "work/frame.png").convert("RGB")
W, H = im.size
a = np.asarray(im).astype(int)
R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]

# светлая стена: колонки у левого края заметно ярче медианы кадра
lum = a.mean(axis=2)[: H * 2 // 3].mean(axis=0)
base = np.median(lum)
wall = next((x for x in range(W // 4) if lum[x] < base * 1.35), 0)
# зелень справа: устойчивые колонки, где зелёный заметно выше красного и синего
leaf = ((G > R + 12) & (G > B + 12) & (G > 40))[: int(H * 0.88)].sum(axis=0)
bamboo = next((x for x in range(W // 2, W) if leaf[x] > H * 0.012), None)

print(f"кадр {W}x{H}")
print(f"стена слева до x ≈ {wall}  → левый край кропа ставить не левее {wall + 20}")
print(f"зелень справа с x ≈ {bamboo}" if bamboo else "зелени справа не найдено")

sc = 1280 / W
sm = im.resize((1280, int(H * sc)))
d = ImageDraw.Draw(sm)
try:
    F = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14)
except Exception:
    F = ImageFont.load_default()
step = W // 24
for x in range(0, W + 1, step):
    X = x * sc
    d.line([(X, 0), (X, sm.height)], fill=(255, 60, 60) if x % (step * 4) == 0 else (110, 110, 110))
    if x % (step * 2) == 0:
        d.text((X + 3, 3), str(x), fill=(255, 220, 0), font=F)
for y in range(0, H + 1, H // 12):
    Y = y * sc
    d.line([(0, Y), (1280, Y)], fill=(110, 110, 110))
    d.text((3, Y + 3), str(y), fill=(255, 220, 0), font=F)
for x, col in ((wall, (255, 255, 255)), (bamboo, (80, 255, 80))):
    if x:
        d.line([(x * sc, 0), (x * sc, sm.height)], fill=col, width=3)
sm.save(ROOT / "work/grid.png")
print("сетка: work/grid.png (белая линия — стена, зелёная — растение)")
