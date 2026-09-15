"""Шаг 9. Субтитры → final/<slug>.srt (главный язык) и final/<slug>_<язык>.srt

Источник — docs/subs_ru.tsv: «начало<TAB>конец<TAB>текст» в таймкодах ИСХОДНИКА.
Скрипт переносит их в вычищенный таймлайн через work/timemap.json, добавляет
сдвиг на заставку и проверяет правила ТЗ:
  • одна строка, никаких переносов
  • не длиннее 60 символов
  • не короче 1,2 с на экране
Реплики, попавшие целиком в вырезанный кусок, выбрасываются.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTRO = 3.5
MAXLEN, MINDUR = 60, 1.2
AKIMAT = 8.0    # финальная плашка — субтитры на неё не заходят
# Язык субтитров — аргумент: «ru» или «kk». Урок 02 сдаётся с казахскими
# (заказчик: спикер говорит по-русски, субтитры нужны казахские),
# русские остаются рабочей версией для вычитки.
import json as _json
_L = _json.loads((ROOT / "lesson.json").read_text(encoding="utf-8"))
SLUG = _L["slug"]
MAIN = _L["subs_main"]
LANG = sys.argv[1] if len(sys.argv) > 1 else MAIN
SRC = ROOT / f"docs/subs_{LANG}.tsv"
# главный язык — в файл без суффикса: его вжигает burn_subs.py
OUT = ROOT / (f"final/{SLUG}.srt" if LANG == MAIN else f"final/{SLUG}_{LANG}.srt")


def mapper():
    keeps = json.load(open(ROOT / "work/timemap.json"))["keeps"]

    def m(t):
        # Сначала ищем кусок, КОТОРЫЙ СОДЕРЖИТ t, и только потом решаем, что
        # время вырезано. Раньше проверки шли вперемешку в одном проходе, и это
        # работало, пока куски идут по возрастанию. На уроке 05 порядок задан
        # листом (последний дубль стоит в середине), и первая же проверка
        # «t < s» срабатывала на куске из другого блока — уцелевшие реплики
        # объявлялись вырезанными.
        for k in keeps:
            s, e = k["src"]
            if s <= t <= e:
                return k["out"] + (t - s), True
        # Время попало в вырезку. Прижимаем к БЛИЖАЙШЕЙ по исходнику границе
        # куска, а не к первому куску, который начинается позже: при
        # непоследовательных кусках (урок 05) «первый, кто начинается позже» —
        # это кусок из другого блока, и реплика улетала на десять минут назад.
        # Так в уроке 05 пропала строка «А можно ли социальному бизнесу выйти
        # на биржу?»: whisper поставил ей начало на 0,4 с раньше куска.
        best, bd = None, None
        for k in keeps:
            s, e = k["src"]
            d = s - t if t < s else t - e
            if bd is None or d < bd:
                best, bd = k, d
        s, e = best["src"]
        return (best["out"] if t < s else best["out"] + (e - s)), False
    return m


def ts(t):
    h, r = divmod(max(t, 0), 3600)
    mnt, s = divmod(r, 60)
    return f"{int(h):02d}:{int(mnt):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"


def main():
    m = mapper()
    rows, problems = [], []
    for ln, line in enumerate(SRC.read_text(encoding="utf-8").splitlines(), 1):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        a, b, text = line.split("\t", 2)
        text = " ".join(text.split())
        if len(text) > MAXLEN:
            problems.append(f"строка {ln}: {len(text)} символов — «{text}»")
        if "\\n" in text or "<br" in text:
            problems.append(f"строка {ln}: перенос строки, субтитр должен быть в одну")
        ta, oka = m(float(a))
        tb, okb = m(float(b))
        if not oka and not okb:
            continue                        # реплика целиком вырезана
        ta, tb = ta + INTRO, tb + INTRO
        if tb - ta < MINDUR:
            tb = ta + MINDUR
        rows.append((ta, tb, text))

    # Последняя реплика не должна заезжать на плашку акимата. Нижняя граница
    # известна только по готовому ролику: assemble.py склеивает куски
    # кросс-фейдами, и тело выходит на 0,4–0,5 с короче суммы кусков. Поэтому
    # subs.py в finish.sh идёт ПОСЛЕ assemble.py и берёт длительность финала.
    # Урок 05: без этого последняя реплика кончалась на 510,39 с при плашке
    # с 510,28 с — три кадра поверх уходящего кадра.
    fin = ROOT / f"final/{SLUG}.mp4"
    if fin.exists():
        import subprocess
        du = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", str(fin)],
                                  capture_output=True, text=True).stdout.strip())
        cap = du - AKIMAT
        rows = [(a, min(b, cap), t) for a, b, t in rows if a < cap]
        print(f"потолок по плашке акимата: {cap:.2f} с")

    rows.sort()
    for i in range(len(rows) - 1):          # не даём наезжать друг на друга
        if rows[i][1] > rows[i + 1][0]:
            rows[i] = (rows[i][0], rows[i + 1][0] - 0.04, rows[i][2])
    # подрезка соседом могла оставить конец раньше начала — такую реплику
    # плеер показывает мусором, поэтому выбрасываем
    bad = [r for r in rows if r[1] <= r[0]]
    rows = [r for r in rows if r[1] > r[0]]
    for a, b, t in bad:
        print(f"выброшена реплика с нулевой длиной: «{t}»")

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for i, (a, b, t) in enumerate(rows, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n")

    print(f"реплик: {len(rows)}, самая длинная {max(len(t) for *_, t in rows)} символов")
    if problems:
        print("\nнарушения правил:")
        for p in problems:
            print(" •", p)
        sys.exit(1)
    print("правила ТЗ соблюдены: одна строка, ≤60 символов, ≥1,2 с")


if __name__ == "__main__":
    main()
