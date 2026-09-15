"""Казахские субтитры → docs/subs_kk.tsv.

Заказчик попросил субтитры на казахском, хотя спикер говорит по-русски.
Переводим не по репликам, а по предложениям (work/sentences.json →
work/kk.json): реплика — это обрывок фразы, и пословный перевод обрывков
даёт нечитаемый казахский. Готовое предложение режем на куски ≤60 знаков
по границам слов, время предложения раздаём кускам пропорционально длине.

Перевод сделан не носителем языка — вычитать обязательно, спорные термины
перечислены в docs/glossary.txt.
"""
import json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAXLEN = 60
# язык перевода аргументом: kk (речь русская) или ru (речь казахская)
LANG = sys.argv[1] if len(sys.argv) > 1 else "kk"
ru = json.load(open(ROOT / "work/sentences.json", encoding="utf-8"))
kk = json.load(open(ROOT / f"work/{LANG}.json", encoding="utf-8"))
assert len(ru) == len(kk), f"предложений {len(ru)}, переводов {len(kk)}"


def chunks(text):
    """Фраза → куски ≤MAXLEN по границам слов, примерно равной длины."""
    if len(text) <= MAXLEN:
        return [text]
    n = math.ceil(len(text) / MAXLEN)
    target = len(text) / n
    words, out, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        # закрываем кусок, если он уже около цели и слово его перетянет
        if cur and (len(cand) > MAXLEN or
                    (len(cur) >= target * 0.8 and len(cand) > target * 1.15
                     and len(out) < n - 1)):
            out.append(cur); cur = w
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


# Пустая строка перевода — «слить с предыдущим»: огрызок вроде отдельного
# «бизнес.» переводится вместе с соседним предложением, а его время
# достаётся предыдущему (урок 03, 366,5 с).
pairs = []
for (a, b, _), text in zip(ru, kk):
    if not text.strip() and pairs:
        pairs[-1] = (pairs[-1][0], b, pairs[-1][2])
    elif text.strip():
        pairs.append((a, b, text))

rows = []
for a, b, text in pairs:
    parts = chunks(text)
    total = sum(len(p) for p in parts)
    t = a
    for p in parts:
        share = (b - a) * len(p) / total
        rows.append((t, min(b, t + share), p))
        t += share

out = ROOT / f"docs/subs_{LANG}.tsv"
with open(out, "w", encoding="utf-8") as f:
    f.write("# Қазақша субтитрлер урока (lesson.json). Таймкоды — ИСХОДНИКА,\n"
            "# tools/subs.py kk переносит их в вычищенный таймлайн.\n"
            "# Формат: начало<TAB>конец<TAB>текст. Одна строка, максимум 60 знаков.\n"
            "# Перевод с русского сделан не носителем языка — ВЫЧИТАТЬ.\n")
    for a, b, t in rows:
        f.write(f"{a:.2f}\t{b:.2f}\t{t}\n")

print(f"реплик: {len(rows)}, самая длинная {max(len(t) for *_, t in rows)} знаков")
print(f"короче 1.2 с: {sum(1 for a, b, _ in rows if b - a < 1.2)} (subs.py растянет)")
