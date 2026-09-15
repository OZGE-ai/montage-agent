"""Предложения с таймкодами → work/sentences.json — заготовка под перевод.

Субтитры на другой язык переводим целыми предложениями, а не репликами:
реплика — обрывок фразы, пословный перевод обрывков нечитаем. Этот скрипт
собирает предложения из пословной расшифровки и выбрасывает те, что целиком
попали в вырезки. Перевод кладётся в work/kk.json — список строк той же
длины и в том же порядке, — после чего tools/subs_kk_build.py режет их
на реплики и раздаёт время.
"""
import csv, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
d = json.load(open(ROOT / "work/transcript.json", encoding="utf-8"))
# Границы реплик whisper помечаем, чтобы резать предложения и там, где он
# забыл точку. Урок 06: в пяти местах точки нет, и подряд склеивались четыре
# фразы — предложения по 34 и 43 с. Субтитры из такого блока разъезжаются:
# subs_kk_build раздаёт время кускам пропорционально длине, а внутри блока
# лежат паузы. Режем по границе реплики, но только когда предыдущее слово
# не кончается запятой (иначе разорвём фразу пополам) и следующее начинается
# с прописной.
words, brk = [], set()
for s_ in d["segments"]:
    ws = [w for w in s_["words"] if w["w"].strip()]
    if not ws:
        continue
    if words:
        brk.add(len(words))
    words += ws

TAIL = (",", "–", "-", ":", ";", "(")
sent, cur = [], []
for i, w in enumerate(words):
    t = w["w"].strip()
    if (cur and i in brk
            and not cur[-1]["w"].strip().endswith(TAIL)
            and t[:1].isupper()):
        sent.append(cur); cur = []
    cur.append(w)
    if t.endswith((".", "!", "?", "…")):
        sent.append(cur); cur = []
if cur:
    sent.append(cur)
txt = lambda ws: re.sub(r"\s+", " ", "".join(x["w"] for x in ws).strip())
# Урок 05: куски мастера заданы keeps.csv (часть записи — неудачные дубли и
# разговор с группой, их нет в cuts.csv). Тогда «вырезка» — это всё, что НЕ
# попало в куски, иначе в заготовку под перевод уедут фразы из выброшенных
# дублей. Обычный урок keeps.csv не имеет и читает cuts.csv как раньше.
_kf = ROOT / "keeps.csv"
if _kf.exists():
    _keeps = sorted((float(r["начало"]), float(r["конец"]))
                    for r in csv.DictReader(open(_kf, encoding="utf-8")))
    _end = max(w["e"] for w in words) + 1.0
    cuts, _t = [], 0.0
    for _a, _b in _keeps:
        if _a > _t:
            cuts.append((_t, _a))
        _t = max(_t, _b)
    if _t < _end:
        cuts.append((_t, _end))
else:
    cuts = [(float(r["начало"]), float(r["конец"]))
            for r in csv.DictReader(open(ROOT / "cuts.csv", encoding="utf-8"))]


def alive(t0, t1):
    """Уцелевшие куски предложения после вырезок.

    Реплика идёт от первого уцелевшего куска до последнего: вырезка ВНУТРИ
    предложения ничего не портит (subs.py сожмёт время по timemap), а вот
    вырезанные начало или хвост надо отрезать и от реплики. Если предложение
    вырезано почти целиком — реплики нет; если уцелел кусок речи, реплика
    нужна, иначе кусок останется без субтитров (урок 03: после вырезки
    оговорки «мы первые…» звучало ещё 8 с «и теперь мы полноценно…»).
    Такие предложения помечены в выводе: переводить только уцелевшее.
    """
    parts, t = [], t0
    for a, b in sorted(cuts):
        if b <= t0 or a >= t1:
            continue
        if a > t:
            parts.append((t, min(a, t1)))
        t = max(t, b)
    if t < t1:
        parts.append((t, t1))
    return parts


out, clipped = [], []
for sn in sent:
    a, b, text = sn[0]["s"], sn[-1]["e"], txt(sn)
    parts = [q for q in alive(a, b) if q[1] - q[0] >= 0.35]
    # огрызки короче 0,35 с не считаются: от «Итого, мы ещё аккредитованы…»
    # после вырезки остаётся 0,15 с — это не речь, а край стыка
    if sum(y - x for x, y in parts) < 0.8:
        continue
    a2, b2 = parts[0][0], parts[-1][1]
    if a2 > a + 0.3 or b2 < b - 0.3:
        clipped.append((len(out), a2, b2, text))
    out.append((a2, b2, text))

json.dump(out, open(ROOT / "work/sentences.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"предложений: {len(out)}, знаков: {sum(len(t) for *_, t in out)}")
if clipped:
    print(f"\nурезаны вырезками — переводить только уцелевшую часть: {len(clipped)}")
    for i, a, b, t in clipped:
        print(f"  #{i} {a:.2f}–{b:.2f} ({b-a:.1f} с): {t[:110]}")
print("перевод положить в work/kk.json — список из", len(out), "строк")
