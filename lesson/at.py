"""Тайм-код ГОТОВОГО ролика → время исходника + что там в расшифровке.

    .venv/bin/python tools/at.py 0:35 0:50 1:02

Финал = заставка 3,5 с + вычищенный таймлайн (work/timemap.json).
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTRO = 3.5
tm = json.load(open(ROOT / "work/timemap.json"))
D = json.load(open(ROOT / "work/transcript.json", encoding="utf-8"))
words = [w for s in D["segments"] for w in s["words"] if w["w"].strip()]


def to_src(t):
    """время финала → время исходника"""
    out = t - INTRO
    for k in tm["keeps"]:
        s, e = k["src"]
        if out <= k["out"] + (e - s):
            return s + max(0.0, out - k["out"])
    last = tm["keeps"][-1]
    return last["src"][1]


def parse(x):
    if ":" in x:
        m, s = x.split(":")
        return int(m) * 60 + float(s)
    return float(x)


for arg in sys.argv[1:]:
    t = parse(arg)
    src = to_src(t)
    near = [w for w in words if src - 3 < w["s"] < src + 6]
    print(f"\n{arg} финала = {src:.2f} с исходника")
    print("   ", " ".join(f"{w['w'].strip()}" for w in near))
    print("   ", " ".join(f"{w['w'].strip()}@{w['s']:.1f}" for w in near[:14]))
