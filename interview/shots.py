# -*- coding: utf-8 -*-
"""Шаг 7. Выбор камер — как режиссёр монтажа.

Правила (сформулированы заказчиком и проверяются автоматически):
  * крупный план — только того, кто говорит; план не переходит через смену говорящего;
  * вступление ведущей (представление гостя) — целиком центральная камера, она говорит в неё;
  * взгляд в центральную камеру → общий план (контакт со зрителем);
  * общий план «для воздуха» в длинных ответах — только когда ведущая слушает, а не читает с листа;
  * корпе/декор в центре — только на общем плане (крупный ведущей кадрируется в render.py);
  * никаких приближений: склейки и смены камер — мягкое растворение (render.py).
Выход — work/shots.json."""
import json, bisect
import numpy as np
from common import CFG, P
R = P + "work/"
pieces = json.load(open(R + "edit_pieces.json"))["pieces"]
WV = json.load(open(R + "words_verbatim.json")); WF = json.load(open(R + "words_feat.json"))
HOST = set(CFG["host_segments"])
starts = []; acc = 0.0
for a, b in pieces: starts.append(acc); acc += b - a
TOTAL = acc
def prog(t):
    k = bisect.bisect_right([p[0] for p in pieces], t) - 1
    if k < 0: return 0.0
    a, b = pieces[k]; return starts[k] + min(max(t - a, 0), b - a)
def src(p):
    k = bisect.bisect_right(starts, p) - 1; k = max(0, min(k, len(pieces) - 1))
    return pieces[k][0] + (p - starts[k])
ft = np.array([w["start"] for w in WF]); fs = np.array([w["seg"] in HOST for w in WF])
def is_host(t):
    i = np.clip(np.searchsorted(ft, t), 1, len(ft) - 1); j = i if abs(ft[i] - t) < abs(ft[i-1] - t) else i - 1; return bool(fs[j])
words = [dict(w=w["w"], p0=prog(w["s"]), p1=prog(w["e"]), host=is_host((w["s"] + w["e"]) / 2))
         for w in WV if any(a - 0.01 <= w["s"] and w["e"] <= b + 0.01 for a, b in pieces)]
# ── реплики (смены говорящего), короткие <1.2 с поглощаются ──
turns = []
for x in words:
    s_ = "host" if x["host"] else "guest"
    if turns and turns[-1]["who"] == s_: turns[-1]["p1"] = x["p1"]
    else: turns.append(dict(who=s_, p0=x["p0"], p1=x["p1"]))
changed = True
while changed:
    changed = False
    for i, tu in enumerate(turns):
        if tu["p1"] - tu["p0"] < 1.2 and 0 < i < len(turns) - 1 and turns[i-1]["who"] == turns[i+1]["who"]:
            turns[i-1]["p1"] = turns[i+1]["p1"]; del turns[i:i+2]; changed = True; break
# границы реплик — в паузе между словами
for a, b in zip(turns, turns[1:]):
    m = (a["p1"] + b["p0"]) / 2; a["p1"] = m; b["p0"] = m
turns[0]["p0"] = 0.0; turns[-1]["p1"] = TOTAL
# ── взгляд и чтение ──
GA = json.load(open(R + "gaze_A.json")); EY = json.load(open(R + "eyes_C.json"))
def series(L, key):
    t = np.array([q["t"] for q in L]); v = np.array([key(q) if q["found"] else np.nan for q in L]); return t, v
tg, vg = series(GA["guest"], lambda q: q["yaw"] + 0.6 * q["iris"])
th, vh = series(GA["host"], lambda q: q["yaw"] + 0.6 * q["iris"])
te, ve = series(EY, lambda q: q["open"])
def med(t, v, s0, s1):
    m = (t >= s0) & (t < s1); x = v[m]; x = x[~np.isnan(x)]; return float(np.median(x)) if len(x) else np.nan
def reading_frac(p0, p1):
    # доля времени, когда ведущая читает (веки опущены), сглаживание 1,7 с против морганий
    ss = [src(p) for p in np.arange(p0, p1, 1/3)]
    r = [med(te, ve, s - 0.85, s + 0.85) < 0.30 for s in ss]
    return float(np.mean(r)) if r else 1.0
def guest_center(p0, p1): return med(tg, vg, src(p0), src(p1)) < 0.30
# точки склейки: паузы между словами и стыки кусков
jumps = starts[1:]
soft = [((x["p1"] + y["p0"]) / 2, y["p0"] - x["p1"]) for x, y in zip(words, words[1:]) if y["p0"] - x["p1"] >= 0.08]
cands = sorted([(j, 0.6) for j in jumps] + [(t, min(g, 0.5)) for t, g in soft])
def cut_near(lo, hi, target):
    opts = [c for c in cands if lo <= c[0] <= hi]
    return min(opts, key=lambda c: abs(c[0] - target) * 0.5 - c[1] * 3)[0] if opts else None

intro_end = next(x["p1"] for x in words if x["w"].startswith(CFG["body"]["intro_last_word"])) + 0.1
shots = []
def add(a, b, cam):
    if shots and shots[-1][2] == cam: shots[-1][1] = b
    else: shots.append([a, b, cam])
MAXC, AIR = 40.0, 7.0
for tu in turns:
    a, b, who = tu["p0"], tu["p1"], tu["who"]
    close = "B" if who == "guest" else "C"
    if b <= intro_end + 0.5:
        add(a, b, "A"); continue
    if a < intro_end + 0.5:
        e = cut_near(intro_end, min(b, intro_end + 2.0), intro_end + 0.3) or intro_end + 0.3
        add(a, e, "A"); a = e
    t = a
    while b - t > 0.01:
        # общий «для воздуха» / взгляд в центр — только если ведущая не читает
        want_air = (shots and shots[-1][2] == close and t - shots[-1][0] >= MAXC - 8)
        if who == "guest" and b - t >= AIR + 6 and (want_air or guest_center(t, t + AIR)):
            e = cut_near(t + 5.5, t + 9.0, t + AIR)
            if e and reading_frac(t, e) <= 0.10:
                add(t, e, "A"); t = e; continue
        # крупный говорящего до конца реплики или до MAXC
        run0 = shots[-1][0] if shots and shots[-1][2] == close else t
        if b - run0 <= MAXC: add(t, b, close); t = b
        else:
            e = cut_near(t + 12, min(b - 6, run0 + MAXC), run0 + MAXC - 3) or min(b, t + MAXC)
            add(t, e, close); t = e
            # после длинного крупного — общий, если ведущая слушает, иначе просто продолжаем крупный
            if b - t > 8:
                e2 = cut_near(t + 5.5, t + 9.0, t + AIR)
                if e2 and reading_frac(t, e2) <= 0.10: add(t, e2, "A"); t = e2
                else:
                    e3 = cut_near(t + 12, min(b, t + MAXC), t + 25) or b
                    shots.append([t, e3, close]) if shots[-1][2] != close else None
                    if shots[-1][2] == close: shots[-1][1] = e3
                    t = e3
# длинные крупные планы (>40 с): ищем окна, где ведущая слушает (не читает), и ставим туда общий примерно раз в 30 с
out = []
for a_, b_, cam in shots:
    if cam == "A" or b_ - a_ <= MAXC: out.append([a_, b_, cam]); continue
    t = a_; segs_ = []
    while b_ - t > MAXC:
        best = None
        for c0, _ in cands:
            if not (t + 14 <= c0 <= min(t + 34, b_ - 14)): continue
            e = cut_near(c0 + 5.5, c0 + 9.0, c0 + 7.0)
            if not e: continue
            rf = reading_frac(c0, e)
            if rf <= 0.10:
                score = abs(c0 - (t + 28)) + rf * 50
                if best is None or score < best[0]: best = (score, c0, e)
        if not best: break
        segs_ += [[t, best[1], cam], [best[1], best[2], "A"]]; t = best[2]
    segs_.append([t, b_, cam]); out += segs_
shots = out
# финал: последние слова гостя + «Спасибо вам» — общий, если ведущая не читает
last = shots[-1]
if last[2] != "A" and last[1] - last[0] > 7:
    m = cut_near(TOTAL - 6.5, TOTAL - 3.5, TOTAL - 5)
    if m and reading_frac(m, TOTAL) <= 0.2: last[1] = m; shots.append([m, TOTAL, "A"])
# проверки
bad_speaker = []
for a, b, cam in shots:
    if cam == "A": continue
    other = [x for x in words if a <= x["p0"] < b and (x["host"] != (cam == "C"))]
    if sum(x["p1"] - x["p0"] for x in other) > 1.0: bad_speaker.append((round(a, 1), round(b, 1), cam, " ".join(x["w"] for x in other)[:60]))
readA = [(round(a, 1), round(b, 1), round(reading_frac(a, b), 2)) for a, b, c in shots if c == "A" and a > intro_end and reading_frac(a, b) > 0.15]
d = np.array([b - a for a, b, _ in shots])
print("планов", len(shots), "длит. мин/медиана/макс", d.min().round(1), np.median(d).round(1), d.max().round(1))
print("камеры:", {c: sum(1 for s in shots if s[2] == c) for c in "ABC"}, "секунд:", {c: round(sum(b - a for a, b, cc in shots if cc == c)) for c in "ABC"})
print("крупный не того, кто говорит (>1 с):", bad_speaker)
print("общие, где ведущая читает >15%:", readA)
print("смен камеры", len(shots) - 1, "склеек внутри планов (растворение)", sum(1 for j in jumps if not any(abs(j - s[0]) < 0.01 for s in shots)))
json.dump(dict(pieces=pieces, starts=starts, total=TOTAL, shots=shots, words=words, turns=turns, intro_end=intro_end), open(R + "shots.json", "w"), ensure_ascii=False)
print("конец:", [(round(a, 1), round(b, 1), c) for a, b, c in shots[-4:]])
