"""Шаг 7. Сборка композиций по montage.csv → work/seg/*.mov → work/body.mov.

Видео собираем по кускам, звук берём одной дорожкой из clean.mov и подкладываем
в самом конце — так видео и звук физически не могут разъехаться.

Каждый кусок берётся с запасом XF/2 с обеих сторон, стыки идут кросс-фейдом
7 кадров: сумма длительностей после xfade равна сумме кусков, хронометраж цел.
Любой статичный слайд едет 100 → 104 % за время показа.
"""
import csv, json, math, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEG = ROOT / "work/seg"; SEG.mkdir(parents=True, exist_ok=True)
FPS = 25
# ⚠️ XF обязан совпадать с XF в assemble.py: здесь кусок берётся с запасом
# XF/2 с каждой стороны, там этим запасом делается кросс-фейд. Разойдутся —
# переход съест речь. Правка заказчика 14.09: 0.50 → 0.84 (21 кадр).
XF = 0.84    # переход между раскладками
LT_IN, LT_OUT = 5.4, 17.4       # плашка «имя + должность», один раз
# Урок 06: «меня зовут…» на 5,4 с; держим 12,0 с — в плашке четыре строки
# (имя и три регалии), меньше не прочитать. Спикер представляется до 44 с.
# Урок 05: «меня зовут…» на 8,6 с, держали 11,4 с.
# Урок 03: спикер представляется сам («С вами Стас Аппазов», 8.3 с) —
# плашка встаёт на имя и держится, пока он называет агентство.

SPK = dict(x=80, y=190, w=760, h=690)
# Урок 02, третья редакция кадра — «экран пополам» по ТЗ заказчика.
#
# Урок 06: студия ТА ЖЕ, что в уроках 03 и 05 (кадр из финала урока 03 это
# подтверждает: те же рейки и тот же торшер), но кадр другой — в 06 в него
# попали микрофон на стойке слева и ноутбук на столе, а общий тон теплее.
# Камера та же, 2560x1440/30/HEVC.
# Лицо на x≈910 (мерено по семи кадрам всей записи: 894–929, среднее 905),
# макушка на y≈318. Светлая полоса стены слева кончается на x≈90,
# бамбук справа начинается с x≈1742.
#
# ⚠️ Стена деревянная и тёплая по цвету — маска кожи из grade_check.py
# ловит её вместе с лицом. Для этой студии маска переписана, см. сам скрипт.
#
# Режим А (спикер один в кадре): лицо строго по центру.
# Правка заказчика 14.09 — «взять кадр дальше, но чтобы сидела по центру».
# Окно раздвинуто до упора: 2 × 910 = 1820, левый край уходит в 0. Дальше
# двигать нельзя — лицо уедет из центра. Проверено стоп-кадром: слева и
# справа симметрично встают растения, снизу видны руки и ноутбук.
# Увеличение упало с ×1.20 до ×1.055 — картинка почти в родном разрешении
# и сама по себе резче. Высота 1024 (16:9), над головой 102 px воздуха.
CENTER = "crop=1820:1024:0:216,scale=1920:1080:flags=lanczos"

# Раскладка «пополам»: слева видео спикера во всю высоту, без карточки,
# без скруглений и без зелёной подложки; справа — поле презентации целиком.
HALF = dict(w=960, h=1080)
# Левая половина 960x1080 — это 8:9. По высоте кадра берём всю картинку
# (1440), значит ширина 1280; x0 = 910 − 640 = 270 — лицо ровно по центру
# половины, правый край 1550 не доходит до бамбука (1742).
SPK_CROP = "crop=1280:1440:270:0"

# Крупный план (режим Д) заказчиком отменён — режимы В, Г, Д не используются,
# слайд всегда в карточке справа. Цели урока 01 убраны, чтобы чужие
# таймкоды не подхватились по совпадению.
D_TARGET = {}
D_ZOOM = 1.6


def load_timemap():
    tm = json.load(open(ROOT / "work/timemap.json"))
    keeps = tm["keeps"]

    def m(t):
        """исходное время → время в clean.mov

        Кусок, содержащий t, ищется первым проходом: порядок кусков задаёт
        монтажный лист (урок 05), и он не обязан возрастать по исходнику.
        """
        for k in keeps:
            s, e = k["src"]
            if s <= t <= e:
                return k["out"] + (t - s)
        # вне кусков — прижимаем к ближайшей по исходнику границе (см. subs.py)
        best, bd = None, None
        for k in keeps:
            s, e = k["src"]
            d = s - t if t < s else t - e
            if bd is None or d < bd:
                best, bd = k, d
        if best is not None:
            s, e = best["src"]
            return best["out"] if t < s else best["out"] + (e - s)
        last = keeps[-1]
        return last["out"] + (last["src"][1] - last["src"][0])
    return tm, m


def zoom_expr(n, z0, z1):
    """плавный проезд по кадрам 0..n-1"""
    return f"{z0}+({z1}-{z0})*on/{max(n - 1, 1)}"


def slide_input_args(row, dur):
    """Аргументы входа для слайда: секвенция инфографики или статичный PNG.

    Инфографика — это тот же слайд заказчика, отрендеренный по кадрам с
    анимацией его собственных элементов. Кадров хватает только на анимацию,
    дальше держим последний — элемент появился и остаётся до конца показа.
    """
    name = row["слайд"]
    anim = ROOT / f"slides/anim/{name}"
    if row["инфографика"] == "да" and anim.exists():
        frames = sorted(anim.glob("*.png"))
        hold = max(0.0, dur - len(frames) / FPS)
        return (["-framerate", str(FPS), "-i", str(anim / "%04d.png")],
                f"tpad=stop_mode=clone:stop_duration={hold:.3f},")
    return (["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}",
             "-i", str(ROOT / f"slides/{name}.png")], "")


def build_slide_input(slide, w, h, n, mode, target=None):
    """PNG слайда → фильтр, дающий поток w×h на n кадров с движением."""
    if mode == "Д":
        (x0, y0), (x1, y1) = target
        # держим кадр в границах картинки
        cx = f"({x0}+({x1}-{x0})*on/{max(n-1,1)})"
        cy = f"({y0}+({y1}-{y0})*on/{max(n-1,1)})"
        return (f"scale={w*2}:{h*2},setsar=1,"
                f"zoompan=z={D_ZOOM}:d=1:s={w}x{h}:fps={FPS}:"
                f"x='clip(iw*{cx}-(iw/zoom/2),0,iw-iw/zoom)':"
                f"y='clip(ih*{cy}-(ih/zoom/2),0,ih-ih/zoom)'")
    z = zoom_expr(n, 1.0, 1.04)
    return (f"scale={w*2}:{h*2},setsar=1,"
            f"zoompan=z='{z}':d=1:s={w}x{h}:fps={FPS}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")


def main():
    tm, m = load_timemap()
    rows = [r for r in csv.DictReader(open(ROOT / "montage.csv", encoding="utf-8"))
            if r["начало"] != "—"]
    clean = str(ROOT / "work/clean.mov")
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    upto = int(sys.argv[2]) if len(sys.argv) > 2 else None

    plan = []
    for i, r in enumerate(rows):
        a, b = m(float(r["начало"])), m(float(r["конец"]))
        # последний ряд держит «Рақмет» дольше, чем длится исходник: карта времени
        # упирается в конец clean.mov, поэтому длительность берём из листа напрямую.
        # Слайд генерится из PNG, звук добьём тишиной при сборке.
        if i < len(rows) - 1:
            b = min(b, tm["duration"])
        else:
            b = a + (float(r["конец"]) - float(r["начало"]))
        plan.append((i, r, a, b))

    for i, r, a, b in plan:
        if only is not None and not (only <= i <= (upto if upto is not None else only)):
            continue
        mode = r["режим кадра"][0]
        slide = r["слайд"]
        pad_l = XF / 2 if i > 0 else 0.0
        pad_r = XF / 2 if i < len(plan) - 1 else 0.0
        s, e = max(0.0, a - pad_l), b + pad_r
        if i < len(plan) - 1:
            e = min(tm["duration"], e)
        n = max(1, round((e - s) * FPS))
        out = SEG / f"{i:03d}.mov"

        ins = ["-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", clean]
        fc = [f"[0:v]fps={FPS},{CENTER},setsar=1[spk];"]
        cur = "spk"

        if mode in "ВГД":
            sl_ins, hold = slide_input_args(r, e - s)
            ins += sl_ins
            if mode == "Д":
                tgt = D_TARGET.get(round(float(r["начало"]), 2))
                if tgt is None:
                    print(f"! нет цели крупного плана для {r['начало']}, беру центр")
                    tgt = ((0.5, 0.5), (0.5, 0.5))
                mv = build_slide_input(slide, 1920, 1080, n, "Д", tgt)
            else:
                mv = build_slide_input(slide, 1920, 1080, n, "В")
            fc = [f"[1:v]{hold}{mv}[sl];"]
            cur = "sl"
        elif mode == "Е":
            panel = ROOT / f"slides/panel/{slide}"
            frames = sorted(panel.glob("*.png"))
            hold = max(0.0, (e - s) - len(frames) / FPS)
            ins += ["-i", str(ROOT / "overlays/bg_right.png"),
                    "-framerate", str(FPS), "-i", str(panel / "%04d.png")]
            fc = [
                f"[0:v]fps={FPS},{SPK_CROP},scale={HALF['w']}:{HALF['h']}:"
                f"flags=lanczos,setsar=1,pad=1920:1080:0:0:black[base];",
                "[base][1:v]overlay=0:0[bg1];",
                f"[2:v]tpad=stop_mode=clone:stop_duration={hold:.3f},"
                f"fps={FPS},format=rgba[pnl];",
                f"[bg1][pnl]overlay={HALF['w']}:0[out];",
            ]
            cur = "out"
        elif mode == "Б":   # не используется: лист переведён на «пополам»
            sl_ins, hold = slide_input_args(r, e - s)
            ins += (["-i", str(ROOT / "overlays/bg_b.png"),
                     "-i", str(ROOT / "overlays/mask_speaker.png"),
                     "-i", str(ROOT / "overlays/slidecard_under.png")]
                    + sl_ins
                    + ["-i", str(ROOT / "overlays/mask_slide.png"),
                       "-i", str(ROOT / "overlays/slidecard_over.png")])
            fc = [
                f"[0:v]fps={FPS},{SPK_CROP},scale={SPK['w']}:{SPK['h']},setsar=1[sc];",
                "[2:v]format=gray[msk];[sc][msk]alphamerge[scr];",
                f"[1:v][scr]overlay={SPK['x']}:{SPK['y']}[bg1];",
                "[bg1][3:v]overlay=0:0[bg2];",
                f"[4:v]{hold}{build_slide_input(slide,SLD_IMG['w'],SLD_IMG['h'],n,'Б')}[slz];",
                "[5:v]format=gray[msl];[slz][msl]alphamerge[slr];",
                f"[bg2][slr]overlay={SLD_IMG['x']}:{SLD_IMG['y']}[bg3];",
                "[bg3][6:v]overlay=0:0[out];",
            ]
            cur = "out"

        # плашка «имя + должность» — один раз, поверх режима А
        if float(r["начало"]) <= LT_IN < float(r["конец"]):
            k = ins.count("-i")  # номер следующего входа
            # именно -loop: одиночный кадр не имеет длительности, и fade по alpha
            # оставил бы плашку прозрачной на весь кусок
            ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{e - s:.3f}",
                    "-i", str(ROOT / "overlays/lower_third.png")]
            t0, t1 = m(LT_IN) - s, m(LT_OUT) - s
            fc.append(
                f"[{k}:v]format=rgba,fade=t=in:st={t0:.2f}:d=0.28:alpha=1,"
                f"fade=t=out:st={t1-0.28:.2f}:d=0.28:alpha=1[lt];"
                f"[{cur}][lt]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})'[ltd];")
            cur = "ltd"

        fc_s = "".join(fc).rstrip(";")
        cmd = (["ffmpeg", "-y", "-hide_banner", "-v", "error"] + ins +
               ["-filter_complex", fc_s, "-map", f"[{cur}]", "-frames:v", str(n),
                # crf 18 + preset fast вместо crf 16 + veryfast: куски — это
                # промежуточное звено, финал всё равно собирается в crf 18,
                # а preset fast при том же качестве заметно экономнее по битрейту.
                # На диске это разница ~900 МБ против ~530 МБ, что здесь решает.
                "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                "-pix_fmt", "yuv420p", "-an", str(out)])
        subprocess.run(cmd, check=True)
        print(f"{i:03d} {mode} {slide:>3} {e-s:6.2f}с → {out.name}", flush=True)


if __name__ == "__main__":
    main()
