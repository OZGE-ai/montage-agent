"""Шаг 4–5. Применяет cuts.csv → work/clean.mp4 (25 fps, с цветокором) + work/timemap.json.

Как прячем склейки:
  • если в этот момент по montage.csv на экране слайд без спикера (режимы В, Г) —
    прыжка не видно, ставим встык;
  • если спикер в кадре (А, Б) — кросс-фейд 5 кадров плюс зум-разрыв:
    соседние куски идут попеременно 100 % и 103 %;
  • звук всегда кросс-фейдом 70 мс, иначе на стыке щелчок.

Кросс-фейд не съедает хронометраж: каждый кусок берётся с запасом d/2 с обеих
сторон, поэтому сумма длительностей после xfade равна сумме исходных кусков —
видео и звук не разъезжаются.
"""
import csv, json, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
FPS = 25
DV = 0.32          # 8 кадров. Было 5; заказчик просил «меньше резкой
                   # динамики» — на длинном фейде склейка не дёргает
DA = 0.07          # 70 мс
ZOOM = 1.02        # зум-разрыв соседних кусков; 1.03 читался как рывок
# Урок 02 снят в 4K (3840x2160) вместо 1080p урока 01. Радиусы смягчения
# кожи заданы в пикселях, поэтому масштабируются по высоте кадра — иначе
# на 4K smartblur работает вчетверо слабее относительно размера лица.
def grade(h):
    k = h / 1080.0
    return (
    # лёгкое смягчение кожи: smartblur размывает только ровные участки,
    # контуры — волосы, глаза, фактура пиджака — остаются резкими
    f"smartblur=luma_radius={min(5.0, 2.4*k):.2f}:luma_strength=0.45:luma_threshold=-30:"
    f"chroma_radius={min(5.0, 2.0*k):.2f}:chroma_strength=0.45:chroma_threshold=-24,"
    # тени уводим в холод, средние тона снимают избыток красного с лица
    "colorbalance=rs=-0.05:gs=0.01:bs=0.06:rm=-0.07:gm=-0.01:bm=0.06:rh=-0.02:bh=0.02,"
    # мягкая S-кривая — глубина без потери деталей в тенях
    "curves=master='0/0 0.25/0.235 0.5/0.5 0.75/0.765 1/1',"
    # Урок 03: подъём яркости и гамма 1.10 сняты — студия и так светлая,
    # абажур торшера уходил в белое (0,9 % кадра выше 250), лицо светило 170.
    # Верх S-кривой смягчён с 0.785 до 0.765, иначе светлые места клиппуются.
    #
    # Урок 05: студия та же, но снято темнее — сырое лицо 133. Подъём
    # вернули (brightness=0.020, contrast=1.05, gamma=1.15), лицо стало 154.
    #
    # Урок 06: студия ДРУГАЯ и поставлена хорошо — сырое лицо 151–157 по
    # семи кадрам всей записи, то есть уже в норме 150–160. Цепочка урока 05
    # давала 176 и верх 5 % — 201, лицо выглядело выбеленным. Подъём снят
    # полностью, гамма чуть выше единицы — только чтобы S-кривая не съела
    # середину. Контраст трогать нельзя: стена тёмная, и уже contrast=1.02
    # загоняет в чёрное 3,4 % кадра при норме 3 %. Замер по 7 кадрам всей
    # записи: лицо 157, верх 5 % — 183, пересвет 0,00 %, чёрное 1,8 %.
    #
    # Правка заказчика 14.09: «добавить резкость, чуть насыщеннее».
    # Смягчение кожи ослаблено (0.62 → 0.45), насыщенность 1.06 → 1.14,
    # в конце цепочки — unsharp только по яркости (по цвету 0, иначе по краям
    # волос лезет цветная кайма). Выше 0.9 по unsharp не уходить: на коже
    #
    # Правка заказчика 14.09 (второй круг): «в уроке 03 сочнее». Замер на
    # кадре режима А, левая половина: урок 03 — 46 %, урок 06 на 1.14 — 40 %.
    # Поставлено 1.26 → 44 %. Выше не идти: на 1.32 замер ПАДАЕТ до 44,2 % —
    # каналы начинают клипповать. Кожа при этом не краснеет: 169,134,125 →
    # 171,133,122, сочнее становятся зелень и торшер, а не лицо.
    # Тем же числом правится просевшее лицо — широкий кадр
    # (1820x1024 вместо 1600x900) захватил больше тёмного фона.
    "eq=brightness=0:contrast=1.00:saturation=1.26:gamma=1.01,"
    "unsharp=5:5:0.75:5:5:0.0")


SRC = ROOT / "raw/speaker.mp4"


def probe():
    """длительность и размер кадра исходника"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(SRC)],
        capture_output=True, text=True).stdout.split()
    w, h = (int(x) for x in out[0].split(","))
    return float(out[1]), w, h


def speaker_visible_at(t, rows):
    """Виден ли спикер в кадре в момент t по монтажному листу."""
    for r in rows:
        if r["начало"] == "—":
            continue
        if float(r["начало"]) <= t < float(r["конец"]):
            # Без спикера в кадре только режимы В и Г — там прыжок не виден.
            # В режиме Е спикер остаётся в карточке слева, поэтому стык
            # такой же, как в А и Б: кросс-фейд, иначе на склейке дёрнет.
            return r["режим кадра"][0] not in "ВГ"
    return True


def main():
    dur, W, H = probe()
    GRADE = grade(H)
    montage = list(csv.DictReader(open(ROOT / "montage.csv", encoding="utf-8")))
    cuts = [(float(r["начало"]), float(r["конец"]))
            for r in csv.DictReader(open(ROOT / "cuts.csv", encoding="utf-8"))]

    # куски, которые остаются
    #
    # Обычный случай: куски — это дополнение к вырезкам, порядок задан самим
    # исходником. Урок 05: спикер переснимала блок про импакт-инвестирование
    # и просила взять последний дубль (794–914 с), а по теме он стоит в
    # середине — между «Даму» и биржей. Поэтому появился keeps.csv: если он
    # есть, куски берутся из него КАК НАПИСАНО, включая порядок. Всё, что
    # ниже по цепочке (стыки, timemap, compose.m, at.py), уже читает keeps
    # списком по порядку, так что перестановка проходит насквозь.
    kf = ROOT / "keeps.csv"
    if kf.exists():
        keeps = [(float(r["начало"]), float(r["конец"]))
                 for r in csv.DictReader(open(kf, encoding="utf-8"))]
        print(f"куски взяты из keeps.csv: {len(keeps)} шт., порядок задан листом")
    else:
        keeps, t = [], 0.0
        for a, b in cuts:
            if a > t:
                keeps.append((t, a))
            t = b
        if t < dur:
            keeps.append((t, dur))
    keeps = [(a, b) for a, b in keeps if b - a > 0.05]

    # у каждого стыка своя длительность перехода
    joins = [DV if speaker_visible_at(keeps[i][1], montage) else 0.0
             for i in range(len(keeps) - 1)]

    # Каждый кусок — ОТДЕЛЬНЫЙ вход со своим -ss/-t, а не ветка trim от [0:v].
    # 27 веток trim от одного входа заставляют ffmpeg держать в памяти кадры
    # для веток, которые дойдут до потребителя позже: на 1080p это переживаемо,
    # на 4K (12 МБ на кадр) видеопоток молча обрывается на середине —
    # звук доходит до конца, картинка кончается, ffmpeg выходит с кодом 0.
    # Со своим входом каждый кусок читается по требованию, память ограничена.
    seg_in, v, a = [], [], []
    n_audio = len(keeps)
    for i, (s, e) in enumerate(keeps):
        pad_l = joins[i - 1] / 2 if i > 0 else 0.0
        pad_r = joins[i] / 2 if i < len(joins) else 0.0
        vs, ve = max(0.0, s - pad_l), min(dur, e + pad_r)
        seg_in += ["-ss", f"{vs:.3f}", "-t", f"{ve - vs:.3f}", "-i", str(SRC)]
        z = ZOOM if i % 2 else 1.0
        zf = (f"scale=iw*{z}:ih*{z},crop={W}:{H}," if z != 1.0 else "")
        # settb обязателен: xfade требует одинаковой временной базы у обоих
        # входов. В уроке 01 исходник был 30 fps и фильтр fps= сам приводил
        # базу к 1/25; здесь съёмка уже 25 fps, fps= проходит насквозь, база
        # остаётся контейнерной 1/1000000 — и цепочка xfade разваливается.
        v.append(f"[{i}:v]setpts=PTS-STARTPTS,{zf}"
                 f"fps={FPS},settb=1/{FPS},{GRADE},setsar=1[v{i}];")
        aps_l = DA / 2 if i > 0 else 0.0
        aps_r = DA / 2 if i < len(keeps) - 1 else 0.0
        a.append(f"[{n_audio}:a]atrim={max(0.0, s - aps_l):.3f}:"
                 f"{min(dur, e + aps_r):.3f},asetpts=PTS-STARTPTS[a{i}];")

    # цепочка переходов
    chain, cur, acc = [], "v0", keeps[0][1] - keeps[0][0]
    for i, d in enumerate(joins):
        nxt = f"vx{i}"
        if d > 0:
            chain.append(f"[{cur}][v{i+1}]xfade=transition=fade:duration={d:.3f}:"
                         f"offset={acc - d/2:.3f},settb=1/{FPS}[{nxt}];")
        else:
            # concat сбрасывает временную базу выхода на контейнерную 1/1000000,
            # и следующий по цепочке xfade уже не сходится по базам — поэтому
            # база проставляется заново после каждого стыка, а не только у кусков.
            chain.append(f"[{cur}][v{i+1}]concat=n=2:v=1:a=0,settb=1/{FPS}[{nxt}];")
        acc += keeps[i + 1][1] - keeps[i + 1][0]
        cur = nxt
    achain, acur = [], "a0"
    for i in range(len(keeps) - 1):
        nxt = f"ax{i}"
        achain.append(f"[{acur}][a{i+1}]acrossfade=d={DA}:c1=tri:c2=tri[{nxt}];")
        acur = nxt

    fc = "".join(v + a + chain + achain).rstrip(";")
    (ROOT / "work/filter_clean.txt").write_text(fc, encoding="utf-8")

    cmd = (["ffmpeg", "-y", "-hide_banner", "-v", "warning", "-stats"] + seg_in +
          ["-i", str(ROOT / "work/clean48.wav"),
           "-/filter_complex", str(ROOT / "work/filter_clean.txt"),
           "-map", f"[{cur}]", "-map", f"[{acur}]",
           "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", "-ar", "48000",
           str(ROOT / "work/clean.mov")])
    print(f"кусков: {len(keeps)}, кросс-фейдов: {sum(1 for d in joins if d)}, "
          f"встык: {sum(1 for d in joins if not d)}")
    subprocess.run(cmd, check=True)

    # карта старое время → новое
    tm, out = [], 0.0
    for s, e in keeps:
        tm.append({"src": [round(s, 3), round(e, 3)], "out": round(out, 3)})
        out += e - s
    json.dump({"fps": FPS, "duration": round(out, 3), "keeps": tm},
              open(ROOT / "work/timemap.json", "w"), indent=1)
    print(f"clean.mov готов: {out:.2f} с")


if __name__ == "__main__":
    main()
