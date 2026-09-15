# -*- coding: utf-8 -*-
"""Запасной вариант, если заказчик не прислал трек: нагнетающая музыка под перебивку (синтез, без лицензий): низкий диссонансный гул, ускоряющееся «сердцебиение»,
удары на вспышках, тонкий тревожный кластер сверху и нарастание в заставку. Тайминг — по кадрам перебивки."""
import json, sys
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt
SR, FPS = 48000, 30
from common import P
R = P + "work/"
plan = json.loads(sys.argv[1])          # [[name, frames], ...] до заставки
marks = {}; t = 0.0
for name, n in plan: marks[name] = (t, t + n / FPS); t += n / FPS
PRE = t; TAIL = 2.5; N = int((PRE + TAIL) * SR)
tt = np.arange(N) / SR
rng = np.random.default_rng(7)
def lp(x, f): return sosfilt(butter(4, f, "low", fs=SR, output="sos"), x)
def hp(x, f): return sosfilt(butter(2, f, "high", fs=SR, output="sos"), x)
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)
out = np.zeros(N)
# 1. гул: A1 + B♭1 (малая секунда) + E2, медленное биение, нарастает
grow = np.clip(tt / PRE, 0, 1) ** 1.4
drone = np.zeros(N)
for f, a in ((55, 1.0), (58.27, 0.55), (82.41, 0.45), (110, 0.25), (116.54, 0.18)):
    ph = 2 * np.pi * f * tt + 0.3 * np.sin(2 * np.pi * 0.07 * tt)
    drone += a * (np.sin(ph) + 0.35 * np.sin(2 * ph + 0.5))
drone = np.tanh(drone * 0.9) * (0.35 + 0.65 * grow) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.23 * tt))
drone += lp(rng.standard_normal(N), 180) * 0.25 * (0.3 + 0.7 * grow)
out += lp(drone, 520) * 0.30
# 1б. остинато струнных восьмыми (A2 A2 B♭2 A2), темп растёт вместе с сердцебиением — слышно на любых динамиках
def saw(f, n):
    x = np.arange(n) / SR; return 2 * ((f * x) % 1.0) - 1
ost = np.zeros(N); tb = 0.3; k = 0
notes = (110.0, 110.0, 116.54, 110.0, 110.0, 130.81, 116.54, 110.0)
while tb < PRE - 0.1:
    bpm = 66 + 46 * (tb / PRE) ** 1.3; step = 60 / bpm / 2
    n = int(min(step * 0.9, 0.25) * SR); f = notes[k % 8]
    note = (saw(f, n) + 0.6 * saw(f * 2.003, n)) * np.exp(-np.arange(n) / SR * 9)
    s0 = int(tb * SR); m = min(n, N - s0)
    ost[s0:s0 + m] += note[:m]; tb += step; k += 1
ost = bp(ost, 150, 1800) * (0.25 + 0.75 * grow)
out += ost * 0.22
# тиканье
tick = hp(rng.standard_normal(int(0.012 * SR)), 5000) * np.exp(-np.arange(int(0.012 * SR)) / SR * 400)
tb = 0.3
while tb < PRE - 0.1:
    bpm = 66 + 46 * (tb / PRE) ** 1.3; s0 = int(tb * SR); out[s0:s0 + len(tick)] += tick * 0.18; tb += 60 / bpm
# 2. тонкий кластер сверху (скрипичная тревога), вступает с середины
hi_env = np.clip((tt - PRE * 0.35) / (PRE * 0.6), 0, 1) ** 1.5
vib = 0.004 * np.sin(2 * np.pi * 5.3 * tt)
cl = sum(np.sin(2 * np.pi * f * tt * (1 + vib)) for f in (1318.5, 1396.9, 1480.0)) / 3
out += cl * hi_env * 0.045 + bp(rng.standard_normal(N), 3000, 7000) * hi_env * 0.012
# 3. сердцебиение: 66 → 112 уд/мин
def thump(dur=0.22, f0=75, f1=38):
    n = int(dur * SR); x = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / SR
    return np.sin(ph) * np.exp(-x * 18) + np.sin(2 * np.pi * 140 * x) * np.exp(-x * 45) * 0.5 + lp(rng.standard_normal(n), 400) * np.exp(-x * 40) * 0.4
th = thump(); th2 = thump(0.18, 65, 36) * 0.6
bt = 0.35
while bt < PRE - 0.3:
    s = int(bt * SR)
    for x, off in ((th, 0), (th2, 0.27)):
        o = s + int(off * SR); m = min(len(x), N - o)
        if m > 0: out[o:o + m] += x[:m] * 0.6
    bpm = 66 + 46 * (bt / PRE) ** 1.3; bt += 60 / bpm
# 4. удары на вспышках и в заставку: всасывание перед ударом + низкий бум
def boom(size=1.0, dur=2.2):
    n = int(dur * SR); x = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(np.linspace(62, 30, n)) / SR
    b = np.sin(ph) * np.exp(-x * 2.2) * 0.7 + np.sin(2 * np.pi * np.cumsum(np.linspace(180, 90, n)) / SR) * np.exp(-x * 6) * 0.5 + lp(rng.standard_normal(n), 1500) * np.exp(-x * 7) * 0.9 + hp(rng.standard_normal(n), 4000) * np.exp(-x * 30) * 0.25
    return np.tanh(b * 1.6) * size
def swell(dur=0.7):
    n = int(dur * SR); e = np.linspace(0, 1, n) ** 3
    return bp(rng.standard_normal(n), 800, 9000) * e * 0.35
hits = [marks[k][0] for k in marks if "flash" in k] + [PRE]
for h in hits:
    size = 1.35 if h == PRE else 1.0
    sw = swell(0.9 if h == PRE else 0.6); s = int(h * SR) - len(sw)
    if s > 0: out[s:s + len(sw)] += sw * (1.6 if h == PRE else 1.0)
    b = boom(size); s = int(h * SR); m = min(len(b), N - s); out[s:s + m] += b[:m]
# 5. нарастание в заставку: полоса шума вверх + подъём тона
rs = PRE - 3.0; n = int(3.0 * SR); x = np.arange(n) / SR
fc = 200 * (30 ** (x / 3.0)); noise = rng.standard_normal(n)
riser = np.zeros(n); blk = 2400
for i in range(0, n, blk):
    c = fc[min(i + blk // 2, n - 1)]; riser[i:i + blk] = bp(noise[i:i + blk], max(60, c * 0.7), min(20000, c * 1.4))
riser *= (x / 3.0) ** 2 * 0.5
glide = np.sin(2 * np.pi * np.cumsum(90 * (4 ** (x / 3.0))) / SR) * (x / 3.0) ** 2 * 0.25
s = int(rs * SR); out[s:s + n] += riser + glide
# после заставки — только хвост бума
out[int(PRE * SR) + int(0.05 * SR):] *= np.linspace(1, 0, N - int(PRE * SR) - int(0.05 * SR)) ** 0.5
# простая реверберация (гребенчатые фильтры)
def comb(x, d, g):
    y = x.copy(); D = int(d * SR)
    for i in range(1, 6):
        if D * i < len(x): y[D * i:] += x[:-D * i] * (g ** i)
    return y
wet = sum(comb(lp(out, 5000), d, 0.45) for d in (0.0297, 0.0371, 0.0411, 0.0437)) / 4
mix = out * 0.8 + wet * 0.35
mix = np.tanh(mix / np.max(np.abs(mix)) * 1.2) * 0.9
sf.write(R + "render/tension.wav", mix.astype(np.float32), SR)
print("tension.wav", round(len(mix) / SR, 2), "с; удары", [round(h, 2) for h in hits])
