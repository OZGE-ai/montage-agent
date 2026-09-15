"""Шаг 7. Статичные плашки и подложки композиций → overlays/*.png (1920x1080).

Всё, что не двигается, печём один раз в PNG: фон режима Б, тень и обводка
карточки слайда, подпись под слайдом, плашка «имя + должность», маски скругления.
Ничего не заходит ниже y=880 — там зона субтитров.
"""
import pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "overlays"; OUT.mkdir(exist_ok=True)
INTER = (ROOT / "inter.css").read_text(encoding="utf-8")

GREEN, BEIGE, SAND, LSAND = "#0E1D18", "#F1F1EF", "#A98457", "#C6A275"

# Урок 02. Брендовая обвязка серии (строка в углу кадра, плашка акимата)
# остаётся казахской, как в уроке 01, — по решению заказчика вид серии
# из 10 роликов единый. Всё, что называет спикера, набрано по-русски:
# формулировку прислал заказчик именно в таком виде.
# Урок 03: регалии взяты со слайда 2 дека спикера (deck/presentation.pdf).
# Урок 05: там же, слайд 2 — «Асель Аймушева, MBA». В плашку взяты три
# должности; строка «Эксперт в области ESG, устойчивого развития,
# коммуникаций и развития сообществ» в плашку не влезает — она уходит на
# панель s02. Членство в проф. ассоциациях и проектном офисе — тоже туда.
# Правка заказчика 14.09: «Основатель» → «Сооснователь». Вслух про Positive
# Impact она говорит «основатель» (12,4 с), а «сооснователь» — про Ассоциацию
# выпускников (16,7 с); в деке на слайде 2 стоит «Основатель». Поставлено по
# прямому указанию заказчика.
SPEAKER_NAME = "Асель Аймушева, MBA"
SPEAKER_ROLE = "Сооснователь агентства Positive Impact"
SPEAKER_ROLE2 = "Исполнительный директор Ассоциации выпускников NU GSB"
SPEAKER_ROLE3 = "Ментор ЕБРР, SIA Kazakhstan, Technovations Girls"
# короткая подпись под карточкой слайда — в строку, капсом
SPEAKER_CAPTION = "Асель Аймушева · Positive Impact"
# Строку «Әлеуметтік кәсіпкерлік» над именем заказчик снял (урок 03).
EYEBROW = ""

# геометрия режима Б (ТЗ), высота карточки спикера 690 вместо 700 —
# иначе она заходит на 10 px в зону субтитров
SPK = dict(x=80, y=190, w=760, h=690, r=26)
# Правая карточка теперь всегда 948x690 — той же высоты, что карточка
# спикера. Раньше в режиме Б слайд 948x533 заканчивался на y=723, а слева
# картинка шла до 880, и низ кадра выглядел недобранным. Слайд ложится
# ВНУТРЬ карточки с отступом, под ним — подпись.
SLD = dict(x=892, y=190, w=948, h=690, r=26)
SLD_IMG = dict(x=916, y=214, w=900, h=506, r=14)

# узор из презентации: дуотон тёмных слайдов + фирменная геометрия
DUOTONE = ("radial-gradient(120% 90% at 78% 18%, rgba(31,109,74,.55) 0%, rgba(14,29,24,0) 62%),"
           "radial-gradient(90% 80% at 12% 88%, rgba(24,84,58,.45) 0%, rgba(14,29,24,0) 60%),"
           f"linear-gradient(160deg,#12271F 0%,#0B1712 60%,{GREEN} 100%)")
PATTERN = """<svg viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice"
 style="position:absolute;inset:0;width:100%;height:100%">
<g stroke="rgba(255,255,255,.045)" stroke-width="50" fill="none" stroke-linecap="square">
<path d="M1140 -120 L1770 510 M1770 -120 L1140 510 M1350 450 L1980 1080 M1980 450 L1350 1080"/>
</g>
<circle cx="1515" cy="495" r="495" fill="none" stroke="rgba(255,255,255,.032)" stroke-width="68"/>
</svg>"""

BASE = f"""{INTER}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1920px;height:1080px;background:transparent;
 font-family:'Inter',system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.f{{position:relative;width:1920px;height:1080px;overflow:hidden}}
"""

PAGES = {}

# ——— фон правой половины (раскладка «экран пополам») ———
# Слева идёт видео спикера во всю высоту, без карточки и без подложки.
# Справа — поле презентации: только фирменный градиент, на нём панель.
PAGES["bg_right"] = f"""<div class="f">
  <div style="position:absolute;left:960px;top:0;width:960px;height:1080px;
     background:{GREEN}">
    <div style="position:absolute;inset:0;background:{DUOTONE}"></div>
  </div>
</div>"""

# ——— титульная заставка урока ———
# Заказчик: на титульном листе только тема, подзаголовок дека не нужен,
# и сам лист — в зелёном фирменном цвете серии, а не в красном деке спикера.
LESSON_TITLE1 = "БИЗНЕС-МОДЕЛИ"
LESSON_TITLE2 = "И УСТОЙЧИВОСТЬ"
# Кегль заставки — под самую длинную строку. В уроке 03 («БРЕНДИНГ» /
# «2026–2030») влезало 150 px; в уроке 05 «ПРЕДПРИНИМАТЕЛЬСТВО» — 19 знаков,
# на 150 px строка уезжает за правый край. Поле под текст: 1920 − 160 слева
# − 160 справа = 1600 px. Мерить рендером, а не на глаз.
LESSON_TITLE_PX = 150
PAGES["intro"] = f"""<div class="f" style="background:{GREEN}">
  <div style="position:absolute;inset:0;background:{DUOTONE}"></div>
  <div style="position:absolute;left:160px;top:50%;transform:translateY(-50%)">
    <div style="font-size:{LESSON_TITLE_PX}px;font-weight:900;line-height:0.98;color:#fff;
       letter-spacing:-.02em;white-space:nowrap">{LESSON_TITLE1}</div>
    <div style="font-size:{LESSON_TITLE_PX}px;font-weight:900;line-height:1.0;color:{LSAND};
       letter-spacing:-.02em;white-space:nowrap">{LESSON_TITLE2}</div>
    <div style="margin-top:44px;width:220px;height:6px;background:{SAND};
       border-radius:3px"></div>
  </div>
</div>"""

# ——— фон режима Б ———
# Брендовую строчку «Әлеуметтік инноваторлар қауымдастығы · АСИ» в левом
# верхнем углу заказчик снял: ролик делается по заказу акимата, логотипа
# ассоциации в кадре быть не должно. Фон остаётся чистым дуотоном.
PAGES["bg_b"] = f"""<div class="f" style="background:{GREEN}">
  <div style="position:absolute;inset:0;background:{DUOTONE}"></div>
</div>"""

# ——— тень под карточкой слайда (ложится ПОД слайд) ———
PAGES["slidecard_under"] = f"""<div class="f">
  <div style="position:absolute;left:{SLD['x']}px;top:{SLD['y']}px;
     width:{SLD['w']}px;height:{SLD['h']}px;border-radius:{SLD['r']}px;
     background:rgba(255,255,255,.035);
     box-shadow:0 26px 70px rgba(0,0,0,.45)"></div>
</div>"""

# ——— обводка карточки + подпись под слайдом (ложится ПОВЕРХ слайда) ———
PAGES["slidecard_over"] = f"""<div class="f">
  <div style="position:absolute;left:{SLD['x']}px;top:{SLD['y']}px;
     width:{SLD['w']}px;height:{SLD['h']}px;border-radius:{SLD['r']}px;
     border:1px solid rgba(255,255,255,.12)"></div>
  <div style="position:absolute;left:{SLD_IMG['x']}px;
     top:{SLD_IMG['y']+SLD_IMG['h']+34}px;width:{SLD_IMG['w']}px;
     font-size:15px;font-weight:800;letter-spacing:.20em;color:{SAND};
     text-transform:uppercase;text-align:center">{SPEAKER_CAPTION}</div>
</div>"""

# ——— только подпись, без карточки: для режима Е (текст справа без слайда) ———
PAGES["caption_only"] = f"""<div class="f">
  <div style="position:absolute;left:{SLD['x']}px;top:{SLD['y']+SLD['h']+38}px;
     font-size:15px;font-weight:800;letter-spacing:.20em;color:{SAND};
     text-transform:uppercase">{SPEAKER_CAPTION}</div>
</div>"""

# ——— плашка «имя + должность» для режима А, один раз на 5–6 сек ———
PAGES["lower_third"] = f"""<div class="f">
  <div style="position:absolute;left:80px;top:672px;max-width:900px;
     background:rgba(10,20,16,.72);backdrop-filter:blur(6px);
     padding:26px 40px 28px;border-radius:20px;border-left:5px solid {SAND}">
    <div style="font-size:56px;font-weight:900;line-height:1.02;
       color:#fff;letter-spacing:-.01em">{SPEAKER_NAME}</div>
    <div style="margin-top:12px;font-size:25px;font-weight:600;line-height:1.34;
       color:rgba(255,255,255,.80)">{SPEAKER_ROLE}</div>
    <div style="margin-top:4px;font-size:25px;font-weight:600;line-height:1.34;
       color:rgba(255,255,255,.66)">{SPEAKER_ROLE2}</div>
    <div style="margin-top:4px;font-size:25px;font-weight:600;line-height:1.34;
       color:rgba(255,255,255,.66)">{SPEAKER_ROLE3}</div>
  </div>
</div>"""

# ——— подложка панели режима Е ———
# Раньше текст панели висел в пустоте: содержание занимало верхнюю треть,
# а под ним оставалась половина экрана голого градиента. Теперь у панели
# есть своя карточка — та же геометрия, что у карточки спикера, и та же
# обводка, что у карточки слайда. Композиция читается как две карточки.
PAGES["panelcard_over"] = f"""<div class="f">
  <div style="position:absolute;left:{SLD['x']}px;top:{SLD['y']}px;
     width:{SLD['w']}px;height:{SLD['h']}px;border-radius:{SLD['r']}px;
     border:1px solid rgba(255,255,255,.12)"></div>
</div>"""

# ——— маски скругления для alphamerge (белое = видно) ———
PAGES["mask_speaker"] = (f"""<div style="width:{SPK['w']}px;height:{SPK['h']}px;background:#000">
  <div style="width:100%;height:100%;background:#fff;border-radius:{SPK['r']}px"></div></div>""",
  SPK["w"], SPK["h"])
PAGES["mask_slide"] = (f"""<div style="width:{SLD_IMG['w']}px;height:{SLD_IMG['h']}px;background:#000">
  <div style="width:100%;height:100%;background:#fff;border-radius:{SLD_IMG['r']}px"></div></div>""",
  SLD_IMG["w"], SLD_IMG["h"])


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, body in PAGES.items():
            if isinstance(body, tuple):
                body, w, h = body
            else:
                w, h = 1920, 1080
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg.set_content(f"<!doctype html><meta charset='utf-8'><style>{BASE}</style>{body}")
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(OUT / f"{name}.png"), omit_background=True)
            pg.close()
            print("→", name)
        b.close()


if __name__ == "__main__":
    main()
