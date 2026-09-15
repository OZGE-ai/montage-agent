"""Уровень звука work/detect.wav по 40 мс — где кончается слово и начинается тишина.

    .venv/bin/python tools/dbp.py 239.2 240.6
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from snap import db

t0, t1 = float(sys.argv[1]), float(sys.argv[2])
t, row = t0, []
while t < t1:
    row.append(f"{t:.2f}:{db(t, t + 0.04):.0f}")
    t += 0.04
for i in range(0, len(row), 10):
    print(" ".join(row[i:i + 10]))
