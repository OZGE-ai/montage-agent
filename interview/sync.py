# -*- coding: utf-8 -*-
"""Шаг 1. Синхронизация камер по звуку (кросс-корреляция) и выбор мастер-звука.

    MONTAGE_PROJECT=~/Projects/interview python interview/sync.py

Считает офсет каждой камеры относительно A на трёх участках записи (проверка дрейфа),
печатает офсеты в секундах и кадрах, уровень шума и число пиков у 0 дБ.
Офсеты записываются в project.json → cameras.X.offset (время в файле X = время A + offset)."""
import json, subprocess
import numpy as np
from scipy.signal import correlate
from common import CFG, CAMS, P, PROJECT, cam_file

SR = 8000
FPS = CFG.get("fps", 30)


def load(cam):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", cam_file(cam), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"])
    return np.frombuffer(raw, np.float32)


def offset(ref, tgt, t0, t1):
    """time_in_tgt = time_in_ref + offset"""
    r = ref[int(t0 * SR):int(t1 * SR)]
    c = correlate(tgt, r, mode="full", method="fft")
    lag = int(np.argmax(np.abs(c))) - (len(r) - 1)
    pk = float(np.abs(c).max()); floor = float(np.sort(np.abs(c))[-5000:-100].mean())
    return (lag - t0 * SR) / SR, pk / floor


def stats(x):
    hop = 400; n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    return dict(floor_p5=round(float(np.percentile(db, 5)), 1), speech_p95=round(float(np.percentile(db, 95)), 1),
                clipped=int((np.abs(x) > 0.98).sum()))


if __name__ == "__main__":
    audio = {c: load(c) for c in CAMS}
    dur = min(len(x) for x in audio.values()) / SR
    probes = [(dur * f, dur * f + 60) for f in (0.1, 0.45, 0.8)]
    cfg = json.load(open(PROJECT / "project.json", encoding="utf-8"))
    for c in CAMS:
        print(c, CAMS[c]["file"], stats(audio[c]))
        if c == "A": continue
        offs = [offset(audio["A"], audio[c], a, b) for a, b in probes]
        for (a, _), (o, q) in zip(probes, offs):
            print(f"   участок {a:6.0f} с: offset {o:+.4f} с ({o * FPS:+.1f} кадра), пик/фон {q:.1f}")
        o = float(np.median([x for x, _ in offs]))
        print(f"   дрейф {abs(offs[0][0] - offs[-1][0]) * 1000:.1f} мс")
        cfg["cameras"][c]["offset"] = round(o, 3)
    json.dump(cfg, open(PROJECT / "project.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("офсеты записаны в project.json")
