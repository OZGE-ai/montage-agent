# -*- coding: utf-8 -*-
"""Общие настройки: папка проекта и project.json.

Папка проекта задаётся переменной окружения MONTAGE_PROJECT (по умолчанию — текущая папка).
В ней лежат source/ (исходники), work/ (промежуточные файлы), output/ (результат), assets/ (шрифт, логотипы, звуки)
и project.json — всё, что относится к конкретному ролику: файлы камер, офсеты, вырезки, фразы-триггеры, бренд."""
import json, os
from pathlib import Path

PROJECT = Path(os.environ.get("MONTAGE_PROJECT", ".")).resolve()
P = str(PROJECT) + "/"
CFG = json.load(open(PROJECT / "project.json", encoding="utf-8"))

CAMS = CFG["cameras"]                                  # {"A": {"file":..., "offset":0.0, "role":"wide"}, ...}
OFF = {c: float(v["offset"]) for c, v in CAMS.items()}  # время в файле камеры = время мультикама + offset
def cam_file(c): return P + CAMS[c]["file"]
for d in ("work", "work/render", "work/preview", "output/graphics"):
    (PROJECT / d).mkdir(parents=True, exist_ok=True)
