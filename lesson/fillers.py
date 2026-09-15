"""Протяжные «а-а-а» — заминки, которыми спикер связывает фразы.

По уровню звука их не видно: они звучат как речь. Отличие — спектр стоит на
месте: одна и та же гласная тянется без согласных. Ищем участки, где громкость
на уровне речи, спектральный центроид низкий (гласная) и почти не меняется.

Whisper такие звуки не пишет отдельным словом, а приклеивает к соседнему —
поэтому «паузы» между словами там нет и cuts.py их не находит.

    .venv/bin/python tools/fillers.py [мин_длительность]
"""
import json, math, pathlib, sys, wave, array
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 0.45
SR_HOP, WIN = 0.010, 0.025

w = wave.open(str(ROOT / "work/detect.wav"))
sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
n, hop = int(WIN * sr), int(SR_HOP * sr)
frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
win = np.hanning(n)
spec = np.abs(np.fft.rfft(frames * win, axis=1))
freq = np.fft.rfftfreq(n, 1 / sr)
rms = np.sqrt((frames ** 2).mean(1)) + 1e-9
db = 20 * np.log10(rms)
cen = (spec * freq).sum(1) / (spec.sum(1) + 1e-9)
speech = np.median(db[db > db.max() - 25])

# кадр-кандидат: громко и это гласная (низкий центроид). Спектр проверяем
# НЕ на всём куске, а обрезав по 60 мс с краёв: на входе и выходе заминки
# есть согласные соседних слов, и они одни ломали проверку «спектр стоит»
# (урок 03: два «а-э-э» по секунде в первых 12 с детектор так пропустил).
ok = (db > speech - 10) & (cen < 1500)
EDGE = 6
runs, i = [], 0
while i < len(ok):
    if ok[i]:
        j = i
        while j < len(ok) and ok[j]:
            j += 1
        if (j - i) * SR_HOP >= MIN:
            core = slice(i + EDGE, max(i + EDGE + 1, j - EDGE))
            if (cen[core].std() < 200 and db[core].std() < 4.5
                    and 250 < cen[core].mean() < 1100):
                runs.append((i * SR_HOP, j * SR_HOP, cen[core].mean(), db[core].mean()))
        i = j
    else:
        i += 1

D = json.load(open(ROOT / "work/transcript.json", encoding="utf-8"))
words = [x for s in D["segments"] for x in s["words"] if x["w"].strip()]
print(f"уровень речи {speech:.1f} dB, кандидатов: {len(runs)}\n")
for a, b, c, d in runs:
    ctx = [x["w"].strip() for x in words if a - 1.6 < x["s"] < b + 1.6]
    print(f"{a:8.2f}–{b:7.2f} ({b-a:.2f} с) центроид {c:4.0f} Гц, {d:5.1f} dB — "
          f"…{' '.join(ctx)[:70]}…")
