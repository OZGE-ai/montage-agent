"""Шаг 4. Список вырезок → cuts.csv.

Ищем по пословной расшифровке и сверяем с silencedetect по work/detect.wav
(порог подобран заново под вычищенный фон: -38 dB / 0.4 с).
"""
import array, csv, json, math, pathlib, re, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = json.load(open(ROOT / "work/transcript.json", encoding="utf-8"))

# Слова-заминки. «ну», «вот», «сондықтан», «яғни» бывают осмысленными —
# они помечаются как spot-check и требуют глазами посмотреть контекст.
HARD = {"ээ", "эээ", "мм", "ммм", "эм", "а-а", "аа", "э-э", "и-и", "ии",
        "это самое", "как бы", "жаңағы", "әні", "ә-ә"}
SOFT = {"ну", "вот", "значит", "то есть", "сондықтан", "яғни", "яки"}

# Урок 05, правка заказчика 14.09: «очень много пауз». Пороги ужаты —
# режем от 0,45 с и оставляем меньше: между фразами 0,22 с вместо 0,35,
# внутри фразы 0,12 вместо 0,20. Дыхание остаётся, стоять в тишине — нет.
PAUSE_MIN = 0.45        # длиннее — режем
KEEP_INSIDE = 0.12      # что оставить от паузы внутри фразы
KEEP_BETWEEN = 0.22     # между фразами: дыхание должно остаться
MIN_CUT = 0.10          # огрызки короче не режем — только щёлкнет


def norm(w):
    return re.sub(r"[^\w\-]", "", w.strip().lower())


class Level:
    """Уровень звука по участку. Нужен как предохранитель: если whisper
    не расслышал кусок речи, между словами образуется «пауза», которой на
    самом деле нет. Резать по ней — значит вырезать живую фразу."""

    def __init__(self, path, words):
        w = wave.open(str(path))
        self.sr = w.getframerate()
        self.pcm = array.array("h")
        self.pcm.frombytes(w.readframes(w.getnframes()))
        lv = sorted(self.db(x["s"], x["e"]) for x in words if x["e"] - x["s"] > 0.15)
        self.speech = lv[len(lv) // 2]

    def db(self, t0, t1):
        seg = self.pcm[int(t0 * self.sr):int(t1 * self.sr)]
        if not seg:
            return -99.0
        s = math.sqrt(sum(x * x for x in seg) / len(seg))
        return 20 * math.log10(s / 32768) if s > 0 else -99.0

    def quiet_run(self, t0, t1, win=0.04, margin=20.0):
        """Самый длинный по-настоящему тихий отрезок внутри промежутка.

        Резать можно только его: у края промежутка звук ещё есть — это
        затухание предыдущего слова и атака следующего, и если захватить их,
        согласные обрежутся. Всё, что громче порога и лежит островом
        посреди тишины, — возможная заминка «ээ», её отдаём человеку на слух.
        """
        n = max(1, int((t1 - t0) / win))
        db = [self.db(t0 + i * win, t0 + (i + 1) * win) for i in range(n)]
        q = [d < self.speech - margin for d in db]
        # Одиночный щелчок в 40–80 мс посреди тишины рвал тихий отрезок пополам,
        # и от паузы в 1,8 с срезалось 0,8 с вместо 1,6 — заказчик урока 05
        # именно это и назвал «очень много пауз». Перешагиваем короткие всплески,
        # если они не дотягивают до речи (speech − 10 дБ): настоящий согласный
        # такой длины стоит у края промежутка, а не посреди тишины.
        bridge = self.speech - 10.0
        i = 0
        while i < n:
            if q[i]:
                i += 1; continue
            j = i
            while j < n and not q[j]:
                j += 1
            if 0 < i and j < n and j - i <= 2 and max(db[i:j]) < bridge:
                for k in range(i, j):
                    q[k] = True
            i = max(j, i + 1)
        best = cur = None
        for i, v in enumerate(q + [False]):
            if v and cur is None:
                cur = i
            elif not v and cur is not None:
                if best is None or i - cur > best[1] - best[0]:
                    best = (cur, i)
                cur = None
        if best is None:
            return None
        return t0 + best[0] * win, t0 + best[1] * win

    def loud_island(self, t0, t1, win=0.04, margin=12.0):
        """Громкий остров посреди промежутка — не у краёв, а именно внутри."""
        n = max(1, int((t1 - t0) / win))
        db = [self.db(t0 + i * win, t0 + (i + 1) * win) for i in range(n)]
        thr = self.speech - margin
        idx = [i for i, d in enumerate(db) if d >= thr]
        if not idx:
            return None
        lo, hi = min(idx), max(idx) + 1
        if lo == 0 or hi == n:          # прилегает к слову — это само слово
            return None
        return t0 + lo * win, t0 + hi * win, max(db[lo:hi])


def silences():
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(ROOT / "work/detect.wav"),
         "-af", "silencedetect=n=-38dB:d=0.4", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    res, start = [], None
    for line in out.splitlines():
        if "silence_start" in line:
            start = float(line.split("silence_start:")[1])
        elif "silence_end" in line and start is not None:
            res.append((start, float(line.split("silence_end:")[1].split("|")[0])))
            start = None
    return res


def main():
    words = [(w, s) for s in D["segments"] for w in s["words"]]
    sil = silences()
    lvl = Level(ROOT / "work/detect.wav", [w for w, _ in words])
    rejected, listen = [], []

    def in_silence(t0, t1):
        return any(a - 0.15 <= t0 and t1 <= b + 0.15 for a, b in sil)

    cuts = []

    # 1. Паузы между словами
    for (w1, s1), (w2, s2) in zip(words, words[1:]):
        gap = w2["s"] - w1["e"]
        if gap <= PAUSE_MIN:
            continue
        # конец фразы: точка/воскл./вопрос на предыдущем слове или новый сегмент
        between = bool(re.search(r"[.!?…]\s*$", w1["w"])) or s1 is not s2
        keep = KEEP_BETWEEN if between else KEEP_INSIDE

        island = lvl.loud_island(w1["e"], w2["s"])
        if island:
            ia, ib, idb = island
            listen.append((ia, ib, idb, w1["w"].strip(), w2["w"].strip()))

        run = lvl.quiet_run(w1["e"], w2["s"])
        if run is None:
            rejected.append((w1["e"], w2["s"], lvl.db(w1["e"], w2["s"]),
                             "тишины нет вовсе"))
            continue
        qa, qb = run
        a, b = qa + keep / 2, qb - keep / 2
        if b - a < MIN_CUT:
            rejected.append((qa, qb, lvl.db(qa, qb),
                             f"тихого куска только {qb-qa:.2f} с"))
            continue
        why = ("пауза между фразами %.2f с (тишины %.2f), оставляю %.2f"
               % (gap, qb - qa, keep) if between else
               "пауза внутри фразы %.2f с (тишины %.2f), оставляю %.2f"
               % (gap, qb - qa, keep))
        if in_silence(w1["e"], w2["s"]):
            why += "; подтверждена silencedetect"
        cuts.append((a, b, why))

    # 2. Слова-заминки
    for i, (w, s) in enumerate(words):
        n = norm(w["w"])
        if n in HARD:
            cuts.append((w["s"] - 0.03, w["e"] + 0.03, f"заминка «{w['w'].strip()}»"))
        elif n in SOFT:
            ctx = " ".join(x["w"].strip() for x, _ in words[max(0, i - 3):i + 4])
            cuts.append((w["s"] - 0.03, w["e"] + 0.03,
                         f"ПРОВЕРИТЬ «{w['w'].strip()}» — бывает осмысленным; контекст: {ctx}"))

    # 3. Повторы подряд: «мы… мы делаем» → «мы делаем»
    for (w1, _), (w2, _) in zip(words, words[1:]):
        if norm(w1["w"]) and norm(w1["w"]) == norm(w2["w"]) and len(norm(w1["w"])) > 2:
            cuts.append((w1["s"] - 0.03, w1["e"] + 0.03,
                         f"повтор слова «{w1['w'].strip()}»"))

    cuts.sort()
    # склеиваем пересечения
    merged = []
    for a, b, why in cuts:
        if merged and a <= merged[-1][1] + 0.02:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b), merged[-1][2] + " + " + why)
        else:
            merged.append((a, b, why))

    with open(ROOT / "cuts.csv", "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["начало", "конец", "длительность", "причина"])
        for a, b, why in merged:
            wr.writerow([f"{a:.2f}", f"{b:.2f}", f"{b - a:.2f}", why])

    total = sum(b - a for a, b, _ in merged)
    dur = D["duration"]
    print(f"вырезок: {len(merged)}, суммарно {total:.1f} с "
          f"({total / dur * 100:.1f}% хронометража)")
    print(f"склеек на минуту: {len(merged) / (dur / 60):.1f} (красная черта — 40)")
    print(f"после чистки: {dur - total:.1f} с")
    if rejected:
        print(f"\nне режу — тишины недостаточно: {len(rejected)}")
        for a, b, d, why in rejected:
            print(f"  {a:7.2f}–{b:7.2f} ({b-a:.2f} с) {d:6.1f} dB — {why}")
    if listen:
        print(f"\nпослушать: звук посреди паузы, слов там нет — "
              f"возможно «ээ»: {len(listen)}")
        for a, b, d, p1, p2 in listen:
            print(f"  {a:7.2f}–{b:7.2f} ({b-a:.2f} с) {d:6.1f} dB "
                  f"при речи {lvl.speech:.1f} — между «{p1}» и «{p2}»")
    need = [c for c in merged if "ПРОВЕРИТЬ" in c[2]]
    if need:
        print(f"\nтребуют проверки глазами: {len(need)}")
        for a, b, why in need:
            print(f"  {a:7.2f} {why[:110]}")


if __name__ == "__main__":
    main()
