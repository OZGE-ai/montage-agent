# -*- coding: utf-8 -*-
"""Шаг 3. Кто говорит: основной тон голоса по каждому слову (ведущая ~205–260 Гц, гость ~150–190 Гц)
и разница уровней на крупных камерах. Выход — work/words_feat.json.

Агент (LLM) смотрит на медианный тон по сегментам и вписывает номера сегментов ведущей
в project.json → host_segments; спорные места помечаются «?» в монтажном листе."""
import json, subprocess
import numpy as np, soundfile as sf
from common import CAMS, OFF, P, cam_file

SR = 16000


def wav(cam):
    path = P + f"work/{cam}16.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cam_file(cam), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", path], check=True)
    return sf.read(path)[0]


def win(x, off, t0, t1):
    s = int((t0 + off) * SR); e = int((t1 + off) * SR)
    return None if s < 0 or e > len(x) or e <= s else x[s:e]


def f0s(x):
    fl, hop, out = 640, 160, []
    for i in range(0, len(x) - fl, hop):
        fr = x[i:i + fl] * np.hanning(fl); fr = fr - fr.mean()
        if (fr ** 2).sum() < 1e-5: continue
        ac = np.correlate(fr, fr, "full")[fl - 1:]; ac /= ac[0]
        k = int(SR / 400) + np.argmax(ac[int(SR / 400):int(SR / 70)])
        if ac[k] > 0.45: out.append(SR / k)
    return out


if __name__ == "__main__":
    A, B, C = wav("A"), wav("B"), wav("C")
    d = json.load(open(P + "work/transcript_raw.json"))
    words = []
    for s in d["segments"]:
        for w in s["words"]:
            w["seg"] = s["id"]; words.append(w)
    for w in words:
        x = win(A, 0, w["start"], w["end"]); f = f0s(x) if x is not None and len(x) > 700 else []
        w["f0"] = round(float(np.median(f)), 1) if len(f) >= 2 else None
        b = win(B, OFF["B"], w["start"], w["end"]); c = win(C, OFF["C"], w["start"], w["end"])
        w["bc_db"] = round(float(10 * np.log10((b ** 2).mean() + 1e-12) - 10 * np.log10((c ** 2).mean() + 1e-12)), 1) if b is not None and c is not None and len(b) else None
    json.dump(words, open(P + "work/words_feat.json", "w"), ensure_ascii=False)
    by = {}
    for w in words:
        if w["f0"]: by.setdefault(w["seg"], []).append(w["f0"])
    for seg in sorted(by):
        print(seg, "f0 медиана", round(float(np.median(by[seg]))), "p25", round(float(np.percentile(by[seg], 25))))
