# -*- coding: utf-8 -*-
"""Шаг 5. «Э-э», «м-м», растянутые гласные — по звуку, потому что whisper их не пишет.

Признак запинки: голос ≥0.25 с, ровный основной тон (коэф. вариации < 0.06) и неподвижный тембр
(изменение спектра за 50 мс ниже 25-го перцентиля). У живой речи тембр меняется каждые 80–200 мс.
Выход: work/voiced_runs.json — используется в edit.py."""
import json
import numpy as np, soundfile as sf

SR, HOP, WIN = 16000, 160, 640

def detect_runs(A):
    """Голосовые участки ≥0.25 с с признаками: длительность, коэф. вариации тона, медианное изменение тембра.
    Возвращает (runs, flux_p25)."""
    nfr = (len(A) - WIN) // HOP
    voiced = np.zeros(nfr, bool); f0 = np.zeros(nfr, np.float32)
    win = np.hanning(WIN).astype(np.float32)
    edges = np.unique(np.geomspace(4, 400, 25).astype(int)); nb = len(edges) - 1
    bands = np.zeros((nfr, nb), np.float32)
    for c0 in range(0, nfr, 8000):
        idx = np.arange(c0, min(nfr, c0 + 8000))
        fr = A[idx[:, None] * HOP + np.arange(WIN)[None, :]] * win
        fr -= fr.mean(1, keepdims=True)
        sp = np.abs(np.fft.rfft(fr, n=1024)) ** 2
        ac = np.fft.irfft(sp, n=1024)[:, :WIN].real; ac /= ac[:, :1] + 1e-9          # автокорреляция через спектр
        k = 40 + np.argmax(ac[:, 40:229], 1); pk = ac[np.arange(len(idx)), k]
        voiced[idx] = pk > 0.55; f0[idx] = SR / k
        bands[idx] = 10 * np.log10(np.stack([sp[:, edges[i]:edges[i + 1]].sum(1) for i in range(nb)], 1) + 1e-10)
    flux = np.zeros(nfr, np.float32); flux[5:] = np.abs(bands[5:] - bands[:-5]).mean(1)
    runs, s = [], None
    for j in range(nfr + 1):
        v = j < nfr and voiced[j]
        if v and s is None: s = j
        if not v and s is not None:
            if j - s >= 25:
                ff = f0[s:j]
                runs.append(dict(t0=round(s * HOP / SR, 2), t1=round(j * HOP / SR, 2), d=round((j - s) * HOP / SR, 2),
                                 cv=round(float(np.std(ff) / np.mean(ff)), 3), flux=round(float(np.median(flux[s:j])), 2)))
            s = None
    return runs, float(np.percentile(flux[voiced], 25)) if voiced.any() else 0.0


def hesitation_candidates(runs, flux_p25):
    return [r for r in runs if r["d"] >= 0.30 and r["cv"] < 0.06 and r["flux"] < flux_p25]


if __name__ == "__main__":
    from common import P
    A, _ = sf.read(P + "work/master_A_16k.wav", dtype="float32")
    runs, p25 = detect_runs(A)
    json.dump(dict(flux_p25=p25, runs=runs), open(P + "work/voiced_runs.json", "w"))
    print("голосовых участков ≥0.25 с:", len(runs), "| кандидатов в «э-э»:", len(hesitation_candidates(runs, p25)), "| порог тембра", round(p25, 2))
