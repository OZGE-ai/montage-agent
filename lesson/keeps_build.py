"""Шаг 6.5 (урок 05). Собирает keeps.csv — куски мастера В ЗАДАННОМ ПОРЯДКЕ.

Обычно куски мастера — это просто дополнение к cuts.csv, и порядок задан
исходником. Урок 05: спикер переснимала блок и просила взять последний дубль,
а по теме он стоял в середине. Урок 06: порядок возрастающий, но концовку
спикер пересняла трижды — блоки перечислены здесь явно, чтобы выбор дубля
был виден. Вырезки пауз из cuts.csv вычитаются внутри каждого блока.

    .venv/bin/python tools/keeps_build.py       # → keeps.csv

Разбор дублей и почему выбраны именно эти блоки — docs/dubli.md.
"""
import csv, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (начало, конец, что это). Границы сняты tools/snap.py — обе в тишине.
BLOCKS = [
    (4.03, 692.97, "весь урок: представление, определение, бизнес-модель, источники дохода, импакт, риски, пять условий, главный вывод"),
    (757.79, 769.60, "финальная фраза и приглашение — дубль 3, последний"),
]


def main():
    cuts = [(float(r["начало"]), float(r["конец"]))
            for r in csv.DictReader(open(ROOT / "cuts.csv", encoding="utf-8"))]
    out, total = [], 0.0
    for a, b, what in BLOCKS:
        inner = sorted(c for c in cuts if c[0] >= a and c[1] <= b)
        t = a
        for ca, cb in inner:
            if ca > t:
                out.append((t, ca, what))
            t = cb
        if t < b:
            out.append((t, b, what))
        kept = sum(e - s for s, e, _ in out) - total
        total += kept
        print(f"{a:8.2f}–{b:7.2f}  вырезок {len(inner):2d}  осталось {kept:6.2f} с  — {what}")
    out = [(s, e, w) for s, e, w in out if e - s > 0.05]
    with open(ROOT / "keeps.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["начало", "конец", "блок"])
        for s, e, what in out:
            w.writerow([f"{s:.2f}", f"{e:.2f}", what])
    print(f"\nkeeps.csv: {len(out)} кусков, {total:.2f} с "
          f"({int(total // 60)}:{total % 60:04.1f}) + заставка 3,5 с + плашка акимата 8 с")


if __name__ == "__main__":
    main()
