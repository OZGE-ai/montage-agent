"""Замер x лица по всей записи — проверка, что кроп режима А держит лицо по центру.

Детектора лиц в окружении нет, поэтому ищем кожу по цвету и яркости:
лицо спикера заметно светлее тёмной деревянной стены и тёплого дерева,
и у него R > G > B с большим разрывом. Считаем медиану x таких пикселей
в полосе головы. Печатает разброс по кадрам — по нему видно, уезжает ли
спикер из центра окна.

    .venv/bin/python tools/face_x.py [шаг_секунд]
"""
import pathlib, subprocess, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "raw/speaker.mp4"
step = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(SRC)], capture_output=True, text=True).stdout)
xs = []
t = 5.0
while t < dur - 3:
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t}", "-i", str(SRC),
                    "-frames:v", "1", "-y", "/tmp/fx.png"], check=True)
    a = np.asarray(Image.open("/tmp/fx.png").convert("RGB")).astype(int)
    band = a[280:700]                      # полоса головы
    R, G, B = band[:, :, 0], band[:, :, 1], band[:, :, 2]
    lum = band.mean(axis=2)
    # абажуры торшеров тоже тёплые и светлые — их отсекает верхний порог яркости
    skin = (lum > 105) & (lum < 190) & (R > G + 18) & (G > B + 8) & (R > 120)
    if skin.sum() > 2000:
        x = float(np.median(np.nonzero(skin)[1]))
        xs.append((t, x))
        print(f"{t:7.1f}  x={x:7.1f}  пикселей={skin.sum()}")
    else:
        print(f"{t:7.1f}  лицо не найдено ({skin.sum()})")
    t += step
v = np.array([x for _, x in xs])
print(f"\nкадров: {len(v)}   медиана x = {np.median(v):.0f}   "
      f"мин {v.min():.0f}  макс {v.max():.0f}  разброс {v.max()-v.min():.0f} px")
