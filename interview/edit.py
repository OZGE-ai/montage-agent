# -*- coding: utf-8 -*-
"""Шаг 6. Вырезки: по смыслу, паразиты и неправильные повторы (решения агента в project.json → edits),
паузы и «э-э» (по звуку). Выход — work/edit_pieces.json: оставляемые куски исходника по времени камеры A.

edits: {"причина": [время_начала_слова, ..., [от, до], ...]} — время из дословной расшифровки (words_verbatim.json).
Слова выбирает агент, читая расшифровку; скрипт сам находит безопасные точки склейки в паузах."""
import json
import numpy as np, soundfile as sf
from common import CFG, P

SR, HOP, WIN = 16000, 160, 640
KEEP_AFTER, KEEP_BEFORE = 0.10, 0.15      # сколько тишины оставить после слова и перед следующим
PAUSE_MIN = 0.40                          # паузы длиннее — укорачиваем до ~0.25 с

W = json.load(open(P + "work/words_verbatim.json"))
A, _ = sf.read(P + "work/master_A_16k.wav", dtype="float32")


def voicing():
    nfr = (len(A) - WIN) // HOP
    voiced = np.zeros(nfr, bool); f0 = np.zeros(nfr, np.float32); win = np.hanning(WIN).astype(np.float32)
    for c0 in range(0, nfr, 8000):
        idx = np.arange(c0, min(nfr, c0 + 8000))
        fr = A[idx[:, None] * HOP + np.arange(WIN)[None, :]] * win; fr -= fr.mean(1, keepdims=True)
        ac = np.fft.irfft(np.abs(np.fft.rfft(fr, n=2048)) ** 2, n=2048)[:, :WIN].real; ac /= ac[:, :1] + 1e-9
        k = 40 + np.argmax(ac[:, 40:229], 1); pk = ac[np.arange(len(idx)), k]
        voiced[idx] = pk > 0.6; f0[idx] = SR / k
    return voiced, f0


voiced, f0 = voicing()
def fi(t): return int(round(t * SR / HOP))


def voiced_info(t0, t1):
    a, b = fi(t0), fi(t1)
    if b - a < 3: return dict(run=0.0, cv=0.0)
    best, s = (0, 0, 0), None
    for j, x in enumerate(list(voiced[a:b]) + [False]):
        if x and s is None: s = j
        if not x and s is not None:
            if j - s > best[0]: best = (j - s, s, j)
            s = None
    seg = f0[a + best[1]:a + best[2]]
    return dict(run=best[0] * HOP / SR, cv=float(np.std(seg) / (np.mean(seg) + 1e-9)) if best[0] > 3 else 0.0)


if __name__ == "__main__":
    drop = {}
    for why, items in CFG["edits"].items():
        for it in items:
            if isinstance(it, list):
                for i, w in enumerate(W):
                    if it[0] <= w["s"] < it[1]: drop[i] = why
            else:
                c = [i for i, w in enumerate(W) if abs(w["s"] - it) < 0.03]
                assert c, ("в расшифровке нет слова, начинающегося в", it); drop[c[0]] = why
    body = CFG["body"]
    b0 = next(i for i, w in enumerate(W) if w["w"].startswith(body["first_word"]))
    b1 = min((i for i, w in enumerate(W) if w["w"].startswith(body["last_word"])), key=lambda i: abs(W[i]["s"] - body["last_word_near"]))
    keep = [i for i in range(b0, b1 + 1) if i not in drop]
    pieces, log, cur = [], [], [W[keep[0]]["s"] - 0.12, None]
    for a_i, b_i in zip(keep, keep[1:]):
        wa, wb = W[a_i], W[b_i]; gap = wb["s"] - wa["e"]; kind = None
        if b_i != a_i + 1: kind = "вырезка:" + drop[a_i + 1]
        elif gap >= PAUSE_MIN:
            vi = voiced_info(wa["e"] + 0.06, wb["s"] - 0.06)
            if vi["run"] >= 0.25 and vi["cv"] > 0.09:
                log.append(dict(t=wa["e"], kind="в паузе похоже на речь — оставлено")); continue
            kind = "э-э/м-м" if vi["run"] >= 0.25 else "пауза"
        if not kind: continue
        c0, c1 = wa["e"] + KEEP_AFTER, wb["s"] - KEEP_BEFORE
        if kind.startswith("вырезка"):
            c0 = max(min(c0, (wa["e"] + W[a_i + 1]["s"]) / 2 + 0.05), wa["e"] + 0.04)
            c1 = min(max(c1, (W[b_i - 1]["e"] + wb["s"]) / 2 - 0.05), wb["s"] - 0.06)
        if c1 - c0 >= 0.12:
            cur[1] = round(c0, 3); pieces.append(cur); cur = [round(c1, 3), None]
            log.append(dict(t=round(wa["e"], 2), cut=round(c1 - c0, 2), kind=kind, text=f"{wa['w']} | {wb['w']}"))
    cur[1] = body["end_before_stop"]; pieces.append(cur)
    # тишина в начале длинного слова (whisper приклеивает паузу к слову)
    fixed = []
    for p0, p1 in pieces:
        t = p0
        for w in (w for w in W if p0 - 0.01 <= w["s"] and w["e"] <= p1 + 0.01):
            if w["e"] - w["s"] > 0.11 * len(w["w"].strip(".,?!…-")) + 0.65 and w["s"] - 0.01 > p0:
                v = voiced[fi(w["s"]):fi(w["e"])]; j = 0
                while j < len(v) and not v[j]: j += 1
                lead = j * HOP / SR
                if lead >= 0.35 and lead - 0.19 >= 0.15:
                    fixed.append([t, round(w["s"] + 0.03, 3)]); t = round(w["s"] + lead - 0.16, 3)
                    log.append(dict(t=round(w["s"], 2), cut=round(lead - 0.19, 2), kind="пауза в начале слова"))
        fixed.append([t, p1])
    pieces = [p for p in fixed if p[1] - p[0] > 0.05]
    # растянутые звуки: ровный голос ≥0.30 с → оставляем 0.12 + 0.08 с
    hv = json.load(open(P + "work/voiced_runs.json"))
    hes = [r for r in hv["runs"] if r["d"] >= 0.30 and r["cv"] < 0.06 and r["flux"] < hv["flux_p25"]]
    out = []
    for p0, p1 in pieces:
        t = p0
        for r in hes:
            c0, c1 = r["t0"] + 0.12, r["t1"] - 0.08
            if c0 > t + 0.05 and c1 < p1 - 0.05 and c1 - c0 >= 0.12:
                out.append([t, round(c0, 3)]); t = round(c1, 3); log.append(dict(t=round(c0, 2), cut=round(c1 - c0, 2), kind="э-э/растянутый звук"))
        out.append([t, p1])
    pieces = [p for p in out if p[1] - p[0] > 0.05]
    total = sum(b - a for a, b in pieces)
    stat = {}
    for l in log:
        if "cut" in l: stat.setdefault(l["kind"], [0, 0.0]); stat[l["kind"]][0] += 1; stat[l["kind"]][1] += l["cut"]
    print("кусков", len(pieces), "длина", f"{int(total // 60)}:{total % 60:04.1f}")
    for k, (n, s) in stat.items(): print(f"  {k}: {n} мест, {s:.1f} с")
    json.dump(dict(pieces=pieces, log=log, drop={str(k): v for k, v in drop.items()}), open(P + "work/edit_pieces.json", "w"), ensure_ascii=False, indent=1)
