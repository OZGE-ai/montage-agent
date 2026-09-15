"""Замер экспозиции под цветокор: считает ориентиры инструкции по кадрам
режима А (crop CENTER), без цветокора и с цветокором.

  лицо 150–160 · верхние 5 % кадра не выше 210
  пересвет (>250) до 0,3 % · в чёрное (<16) не больше 3 %

    .venv/bin/python tools/grade_check.py [секунды через пробел]
"""
import pathlib, subprocess, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_clean import grade                      # noqa: E402
from compose import CENTER                         # noqa: E402

SRC = ROOT / "raw/speaker.mp4"
TS = [float(x) for x in sys.argv[1:]] or [20, 100, 200, 300, 400, 500]


def skin_mask(path):
    """Маска кожи по СЫРОМУ кадру режима А (1920x1080 после CENTER).

    Строить её по цветокорректированному кадру нельзя: порог яркости сам
    отсекает потемневшие пиксели, и медиана лица почти не двигается, как бы
    сильно мы ни затемняли. Урок 04: так «лицо 158» оказалось на деле 176.

    Урок 06: студия с тёплыми деревянными рейками во всю стену. Цветовое
    условие из уроков 04–05 (R>G+18, G>B+8) ловит эту стену вместе с лицом —
    маска набирала 250 тыс. пикселей по всей ширине кадра, и «лицо» мерилось
    по стене. Поэтому маска сперва ограничена коробкой вокруг лица, и только
    внутри неё работает цветовое условие. Коробка снята по кадрам всей записи:
    лицо гуляет по x на 894–929 в исходнике (±21 px после кропа ×1.2).
    Для другой студии коробку мерить заново — tools/frame_grid.py.
    ⚠️ Коробка задана в кадре ПОСЛЕ CENTER: сменили кроп — пересчитайте её.
    14.09 кроп раздвинут до 1820x1024:0:216, коробка сдвинулась вверх.
    """
    BOX = (830, 315, 1100, 590)                 # x0, y0, x1, y1 в кадре 1920x1080
    a = np.asarray(Image.open(path).convert("RGB")).astype(float)
    lum = a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    m = (lum > 90) & (lum < 235) & (R > G + 12) & (G > B + 5)
    box = np.zeros_like(m)
    box[BOX[1]:BOX[3], BOX[0]:BOX[2]] = True    # глаза, брови и рот условие само отсеет
    return m & box


def stats(path, mask):
    a = np.asarray(Image.open(path).convert("RGB")).astype(float)
    lum = a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114
    face = float(np.median(lum[mask])) if mask.sum() > 3000 else float("nan")
    top5 = float(np.percentile(lum, 95))
    hot = float((lum > 250).mean() * 100)
    black = float((lum < 16).mean() * 100)
    return face, top5, hot, black


print(f"{'с':>6} | {'лицо':>16} | {'верх 5%':>13} | {'>250 %':>13} | {'<16 %':>13}")
print(f"{'':>6} | {'сырое→цветокор':>16} | {'сыр→цвет':>13} | {'сыр→цвет':>13} | {'сыр→цвет':>13}")
acc = []
for t in TS:
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t}", "-i", str(SRC),
                    "-frames:v", "1", "-vf", CENTER, "-y", "/tmp/g_raw.png"], check=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t}", "-i", str(SRC),
                    "-frames:v", "1", "-vf", f"{grade(1440)},{CENTER}", "-y", "/tmp/g_col.png"], check=True)
    mk = skin_mask("/tmp/g_raw.png")
    r, c = stats("/tmp/g_raw.png", mk), stats("/tmp/g_col.png", mk)
    acc.append(c)
    print(f"{t:6.0f} | {r[0]:7.0f}→{c[0]:<8.0f} | {r[1]:5.0f}→{c[1]:<7.0f} | "
          f"{r[2]:5.2f}→{c[2]:<7.2f} | {r[3]:5.2f}→{c[3]:<7.2f}")

m = np.array(acc)
print(f"\nпосле цветокора, среднее: лицо {np.nanmean(m[:,0]):.0f} (норма 150–160), "
      f"верх 5 % {m[:,1].mean():.0f} (не выше 210), "
      f"пересвет {m[:,2].mean():.2f} % (до 0.3), чёрное {m[:,3].mean():.2f} % (до 3)")
