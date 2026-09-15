# -*- coding: utf-8 -*-
"""Звук перехода «чух» для перебивки: воздух (полосовой шум с ростом и спадом) + взмах (свист вниз по частоте) + низкий удар.
Синтезируется, поэтому не нужны сторонние сэмплы и лицензии. Выход: assets/sfx/chuh.wav (пик — на 0,45 с)."""
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt
from common import PROJECT

SR = 48000
rng = np.random.default_rng(11)

if __name__ == "__main__":
    N = int(0.9 * SR); t = np.arange(N) / SR; peak = 0.45
    env = np.where(t < peak, (t / peak) ** 3, np.exp(-(t - peak) * 14))
    air = np.zeros(N)
    noise = rng.standard_normal(N); blk = 1200
    for i in range(0, N, blk):                              # полоса шума едет вверх к пику и вниз после
        c = 400 + 5000 * np.exp(-((i / SR - peak) / 0.12) ** 2)
        air[i:i + blk] = sosfilt(butter(2, [c * 0.6, min(c * 1.8, 20000)], "band", fs=SR, output="sos"), noise[i:i + blk])
    swish = np.sin(2 * np.pi * np.cumsum(np.interp(t, [0, peak, 0.9], [1800, 900, 300])) / SR) * np.exp(-np.abs(t - peak) * 25) * 0.25
    x = np.arange(int(0.35 * SR)) / SR
    thump = np.zeros(N); thump[int(peak * SR):int(peak * SR) + len(x)] = np.sin(2 * np.pi * np.cumsum(np.linspace(110, 45, len(x))) / SR) * np.exp(-x * 14) * 0.6
    out = np.tanh((air * env * 0.5 + swish + thump) * 1.2); out = (out / np.abs(out).max() * 0.9).astype(np.float32)
    (PROJECT / "assets/sfx").mkdir(parents=True, exist_ok=True)
    sf.write(PROJECT / "assets/sfx/chuh.wav", out, SR); print("assets/sfx/chuh.wav")
