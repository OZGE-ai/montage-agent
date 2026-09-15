"""Шаг 6. Черновик субтитров НА ЯЗЫКЕ РЕЧИ → docs/subs_<речь>.tsv.

В уроке 01 спикер говорил по-казахски и шаг 6 был ручным переводом.
Урок 02 идёт по-русски — субтитры это та же речь, поэтому реплики
нарезаются механически из work/transcript.json.

Режем не «набил 60 символов — обрыв», а по смыслу: сначала фраза целиком,
и только длинную фразу делим на равные куски, выбирая место разрыва
поближе к запятой или тире. Так не остаётся висячих хвостов вроде
одинокого слова «повторить.» отдельной репликой.

Файл всё равно нужно вычитать глазами: whisper ошибается в именах,
названиях и числах.
"""
import json, math, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAXLEN = 60
D = json.load(open(ROOT / "work/transcript.json", encoding="utf-8"))

words = [w for s in D["segments"] for w in s["words"] if w["w"].strip()]

# ——— 1. собираем фразы: до конца предложения ———
phrases, cur = [], []
for w in words:
    cur.append(w)
    if w["w"].strip().endswith((".", "!", "?", "…")):
        phrases.append(cur); cur = []
if cur:
    phrases.append(cur)


def text_of(ws):
    return re.sub(r"\s+", " ", "".join(w["w"] for w in ws).strip())


def split_even(ws):
    """Фразу длиннее MAXLEN — на n примерно равных кусков по границам слов."""
    t = text_of(ws)
    if len(t) <= MAXLEN:
        return [ws]
    n = math.ceil(len(t) / MAXLEN)
    target = len(t) / n
    out, start = [], 0
    for k in range(1, n):
        ideal = target * k
        best, best_cost = None, None
        for i in range(start + 1, len(ws)):
            pos = len(text_of(ws[start:i]))
            if pos == 0:
                continue
            # штраф за отклонение от идеальной точки; пунктуация — скидка
            cost = abs(pos - (ideal - len(text_of(ws[:start]))))
            if ws[i - 1]["w"].strip().endswith((",", ";", ":", "—", "–")):
                cost -= 14
            if len(text_of(ws[start:i])) > MAXLEN:
                break
            if best_cost is None or cost < best_cost:
                best, best_cost = i, cost
        if best is None or best <= start:
            continue
        out.append(ws[start:best]); start = best
    out.append(ws[start:])
    # страховка: если кусок всё же длиннее MAXLEN, дорезаем жадно
    fixed = []
    for ch in out:
        while len(text_of(ch)) > MAXLEN:
            i = len(ch) - 1
            while i > 1 and len(text_of(ch[:i])) > MAXLEN:
                i -= 1
            fixed.append(ch[:i]); ch = ch[i:]
        if ch:
            fixed.append(ch)
    return fixed


lines = []
for ph in phrases:
    for ch in split_even(ph):
        if ch:
            lines.append((ch[0]["s"], ch[-1]["e"], text_of(ch)))

# Язык речи берём из lesson.json: для русской речи это subs_ru.tsv, для
# казахской — subs_kk.tsv. Раньше имя было зашито как subs_ru, и на уроке
# с казахской речью казахский текст лёг бы в файл «русских» субтитров.
import json as _json
_speech = _json.loads((ROOT / "lesson.json").read_text(encoding="utf-8"))["speech"]
out = ROOT / f"docs/subs_{_speech}.tsv"
with open(out, "w", encoding="utf-8") as f:
    f.write("# Субтитры на языке речи (lesson.json → speech). Таймкоды — ИСХОДНИКА,\n"
            "# tools/subs.py переносит их в вычищенный таймлайн и добавляет заставку.\n"
            "# Формат: начало<TAB>конец<TAB>текст. Одна строка, максимум 60 символов.\n"
            "# Собрано tools/subs_from_transcript.py из пословной расшифровки —\n"
            "# вычитать глазами: имена, названия и числа whisper пишет с ошибками.\n")
    for a, b, t in lines:
        f.write(f"{a:.2f}\t{b:.2f}\t{t}\n")

print(f"реплик: {len(lines)}, самая длинная {max(len(t) for *_, t in lines)} символов")
print(f"короче 15 символов: {sum(1 for *_, t in lines if len(t) < 15)}")
print(f"короче 1.2 с: {sum(1 for a,b,_ in lines if b-a < 1.2)} (subs.py растянет)")
