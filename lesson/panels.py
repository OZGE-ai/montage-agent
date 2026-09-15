"""Режим Е — текст слайда справа, без самого слайда.

Плотные слайды (списки, таблица регионов, сетка мер) в карточке 948×533
превращаются в нечитаемую кашу: кегль 15 px после уменьшения даёт 11 px.
Поэтому берём с такого слайда только содержание и выкладываем его заново
крупно на фирменном фоне — панель 948×690 справа, спикер слева.

Содержание тянем из разметки заказчика, ничего не сочиняем.
Урок 02: дек пришёл PDF-ом, DOM'а нет, а текстовый слой PDF нечитаем
(один безымянный сабсет F1 без ToUnicode). Поэтому содержание лежит
в docs/slides_text.json — вычитано с картинки слайда.
Результат — секвенция PNG с альфой в slides/panel/<slide>/.
"""
import json, pathlib, re, shutil, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "slides/panel"
FPS = 25
# Правая половина экрана целиком: заказчик просил делить кадр пополам —
# слева видео спикера без подложек, справа полностью место презентации.
W, H = 960, 1080
SAND, LSAND = "#A98457", "#C6A275"

# слайд → длительность анимации в секундах
# Урок 06: дек к этой записи есть и совпадает с речью, панели s02…s12 взяты
# из него (в уроке 05 дек был от другого урока и панели набирались по речи).
# s01 — титул дека, не используется: заставка своя. s0X_N — тот же слайд
# с подсветкой пункта, о котором спикер говорит сейчас.
# Правка заказчика 14.09 «меньше резкой динамики»: выезд панелей замедлен
# в 1,35 раза (было 2.0–2.6 с). Длительность показа панели это не меняет —
# только скорость появления пунктов.
PLAN = {"s02": 3.5, "s02_a": 3.5,
        "s03_1": 3.0, "s03_2": 3.0, "s03_3": 3.0,
        "s04": 3.2,
        "s05_1": 3.0, "s05_2": 3.0,
        "s06_1": 3.2, "s06_2": 3.2, "s06_3": 3.2,
        "s07_1": 3.2, "s07_2": 3.2, "s07_3": 3.2,
        "s08": 3.2,
        "s09_1": 3.0, "s09_2": 3.0, "s09_3": 3.0,
        "s10_1": 3.5, "s10_2": 3.5, "s10_3": 3.5,
        "s11": 3.5, "s11_1": 3.5, "s11_2": 3.5, "s11_3": 3.5,
        "s12": 2.7, "s12_2": 2.7}
CONTENT = ROOT / "docs/slides_text.json"

EXTRACT = """(i) => {
  const S = document.querySelectorAll('section.slide')[i-1];
  const txt = (el) => el ? el.textContent.trim().replace(/\\s+/g, ' ') : '';
  const out = {title: txt(S.querySelector('.h2')),
               lead: txt(S.querySelector('.lead')), items: [], kind: ''};
  const bars = S.querySelectorAll('.barrow');
  const chips = S.querySelectorAll('.chip');
  const cards = S.querySelectorAll('.card');
  if (bars.length) {
    out.kind = 'bars';
    bars.forEach(b => out.items.push({
      name: txt(b.querySelector('.nm')),
      value: txt(b.querySelector('.vl')),
      pct: parseFloat(b.querySelector('.fill').style.width) || 0}));
  } else if (chips.length) {
    out.kind = 'chips';
    chips.forEach(c => out.items.push({
      name: txt(c), strike: c.classList.contains('strike'),
      sand: c.classList.contains('sand-chip')}));
  } else if (cards.length) {
    out.kind = 'cards';
    cards.forEach(c => out.items.push({
      k: txt(c.querySelector('.k')), t: txt(c.querySelector('.t')),
      d: txt(c.querySelector('.d')),
      active: (c.getAttribute('style') || '').includes('#A98457')}));
  }
  return out;
}"""


def logo_uri(it):
    """Кусок слайда с логотипами → PNG с альфой по яркости, data-URI."""
    import base64, io
    import numpy as np
    from PIL import Image
    im = Image.open(ROOT / f"slides/{it['slide']}.png").convert("RGB").crop(tuple(it["box"]))
    a = np.asarray(im).astype(float)
    lum = a[..., 0] * .3 + a[..., 1] * .59 + a[..., 2] * .11
    # фон слайда — чёрный с красным свечением (яркость до ~40), логотипы белые
    alpha = np.clip((lum - 45) / (200 - 45), 0, 1) * 255
    out = np.dstack([np.full(lum.shape, 255.0)] * 3 + [alpha]).astype("uint8")
    buf = io.BytesIO(); Image.fromarray(out, "RGBA").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def resolve(content, name):
    """Вариант панели: {"base": "s11", "active": [0]} — тот же слайд,
    подсвечен пункт, о котором сейчас говорит спикер."""
    import copy
    data = content[name]
    if "base" not in data:
        return data
    d = copy.deepcopy(content[data["base"]])
    for i, it in enumerate(d["items"]):
        it["active"] = i in data["active"]
    return d


def layout(data, k=1.0):
    """CSS и разметка панели под конкретное количество элементов.

    k — множитель кегля списка. Урок 06: на длинных подписях список вылезал
    за нижний отступ панели (150 px, там идут субтитры): панель регалий
    доезжала до y=1032 при полосе субтитров 963–1010, и последняя строка
    пряталась под субтитр. Заголовок и лид не масштабируем — они держат
    узнаваемость панели, ужимается только список. Подбор — в main().
    """
    n = len(data["items"])
    kind = data["kind"]
    two = n > 8 and kind != "pairs"  # больше восьми — в две колонки
    if kind == "bars":
        fs = 25 if n <= 12 else 20
        fs = max(14, round(fs * k))
        rows = "".join(
            f'<div class="it bar" data-i="{i}">'
            f'<span class="nm">{it["name"]}</span>'
            f'<span class="track"><span class="fill" data-w="{it["pct"]}"></span></span>'
            f'<span class="vl">{it["value"]}</span></div>'
            for i, it in enumerate(data["items"]))
    elif kind == "pairs":
        fs = 34 if n <= 6 else 28
        fs = max(14, round(fs * k))
        head = data.get("head", ["", ""])
        rows = (f'<div class="it pair hd" data-i="-1">'
                f'<span class="a">{head[0]}</span>'
                f'<span class="b">{head[1]}</span></div>'
                + "".join(
            f'<div class="it pair{" active" if it.get("active") else ""}" data-i="{i}">'
            f'<span class="a">{it["a"]}</span>'
            f'<span class="b">{it["b"]}</span></div>'
            for i, it in enumerate(data["items"])))
    elif kind == "logos":
        # стена логотипов со слайда: белое на чёрном → белое с альфой по яркости,
        # чтобы логотипы легли на фирменный градиент, а не чёрными прямоугольниками
        fs = 0
        # один кусок на панель — вписываем по высоте, логотипы вдвое крупнее;
        # несколько кусков — один масштаб на всех (ширина как доля от самого широкого)
        wmax = max(it["box"][2] - it["box"][0] for it in data["items"])
        one = len(data["items"]) == 1
        rows = "".join(f'<img class="it logo" data-i="{i}" src="{logo_uri(it)}"'
                       + ("" if one else
                          f' style="width:{100 * (it["box"][2] - it["box"][0]) / wmax:.1f}%"')
                       + ">"
                       for i, it in enumerate(data["items"]))
    elif kind == "chips":
        fs = 36 if n <= 8 else 30
        fs = max(14, round(fs * k))
        rows = "".join(
            f'<div class="it chip{" strike" if it["strike"] else ""}'
            f'{" sand" if it["sand"] else ""}" data-i="{i}">{it["name"]}</div>'
            for i, it in enumerate(data["items"]))
    else:
        # короткий список — крупнее: в панели 948×690 три пункта кеглем 24
        # оставляют две трети поля пустыми, а читаемость и есть смысл режима Е
        fs = 44 if n <= 3 else (36 if n <= 6 else (27 if n <= 10 else 21))
        fs = max(14, round(fs * k))
        rows = "".join(
            f'<div class="it card{" active" if it["active"] else ""}" data-i="{i}">'
            + (f'<span class="k">{it["k"]}</span>' if it["k"] else "")
            # заголовок и подпись пункта — в одной колонке справа от номера.
            # Раньше .d стояла третьим flex-элементом и уезжала вбок от .t —
            # в уроке 02 подписей не было, баг вылез на слайдах урока 03
            + f'<span class="body"><span class="t">{it["t"]}</span>'
            + (f'<span class="d">{it["d"]}</span>' if it["d"] and n <= 6 else "")
            + "</span></div>"
            for i, it in enumerate(data["items"]))

    css = f"""
.panel{{position:relative;width:{W}px;height:{H}px;padding:76px 56px 150px;
  display:flex;flex-direction:column;color:#fff}}
.ttl{{font-size:46px;font-weight:900;line-height:1.06;color:{LSAND};
  text-transform:uppercase;letter-spacing:-.01em}}
.lead{{margin-top:14px;font-size:22px;font-weight:600;color:rgba(255,255,255,.62)}}
.rule{{width:110px;height:4px;background:{SAND};border-radius:2px;margin:22px 0 26px}}
.list{{flex:1;min-height:0;align-content:space-evenly;display:{'grid' if two else 'flex'};
  {'grid-template-columns:1fr 1fr;column-gap:34px;' if two else 'flex-direction:column;'}
  {'row-gap:12px' if kind != 'chips' else 'row-gap:10px'};
  {'flex-direction:column;align-items:flex-start' if kind == 'chips' else ''};
  justify-content:space-evenly}}
.it.logo{{display:block;align-self:center;margin:0 auto;
  max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain}}
.it{{font-size:{fs}px;font-weight:700;line-height:1.25}}
.it.card{{display:flex;align-items:baseline;gap:14px;
  border-left:3px solid rgba(198,162,117,.55);padding:6px 0 6px 16px}}
.it.card.active{{border-left-color:{SAND};background:rgba(169,132,87,.18);
  border-radius:0 10px 10px 0}}
.it.card .k{{font-size:{max(12, fs-6)}px;font-weight:800;color:{LSAND};
  letter-spacing:.10em;flex:none}}
.it.card .body{{display:flex;flex-direction:column;min-width:0}}
.it.card .d{{display:block;font-size:{max(13, fs-5)}px;font-weight:500;
  color:rgba(255,255,255,.66);margin-top:5px}}
.it.chip{{border:1px solid rgba(255,255,255,.28);border-radius:999px;
  padding:9px 20px;font-weight:600;background:rgba(255,255,255,.07)}}
.it.chip.strike{{text-decoration:line-through;
  text-decoration-color:{SAND};text-decoration-thickness:2px;
  color:rgba(255,255,255,.62)}}
.it.chip.sand{{background:{SAND};border-color:{SAND}}}
.it.pair{{display:flex;align-items:center;gap:16px;font-weight:600;
  padding:9px 0 9px 14px;border-left:3px solid rgba(198,162,117,.35)}}
.it.pair .a,.it.pair .b{{flex:1 1 0;min-width:0}}
.it.pair .b{{color:rgba(255,255,255,.9)}}
.it.pair.hd{{font-size:{max(13, fs-6)}px;font-weight:800;letter-spacing:.08em;
  text-transform:uppercase;color:{LSAND};border-left-color:transparent;
  padding-bottom:2px}}
.it.pair.active{{border-left-color:{SAND};background:rgba(169,132,87,.18);
  border-radius:0 10px 10px 0}}
.it.pair.active .b{{color:#fff;font-weight:800}}
.it.bar{{display:flex;align-items:center;gap:12px;font-weight:600}}
.it.bar .nm{{width:{132 if two else 200}px;flex:none;
  color:rgba(255,255,255,.86);font-weight:600}}
.it.bar .track{{flex:1;height:7px;border-radius:4px;
  background:rgba(255,255,255,.13);overflow:hidden}}
.it.bar .fill{{display:block;height:100%;width:0;border-radius:4px;
  background:linear-gradient(90deg,{SAND},{LSAND})}}
.it.bar .vl{{width:46px;text-align:right;font-weight:800;color:#fff;flex:none}}
"""
    lead = f'<div class="lead">{data["lead"]}</div>' if data["lead"] else ""
    html = (f'<div class="panel"><div class="ttl">{data["title"]}</div>{lead}'
            f'<div class="rule"></div><div class="list">{rows}</div></div>')
    return css, html


JS = """
const ease = x => 1 - Math.pow(1 - x, 3);
window.__setP = (p) => {
  const it = [...document.querySelectorAll('.it')], N = it.length;
  const groups = N > 7 ? Math.ceil(N / 4) : N;      // выпускаем группами
  const per = N > 7 ? 0.16 : 0.20, dur = 0.45;
  const span = per * Math.min(groups, N) + dur;
  it.forEach((el, i) => {
    const slot = N > 7 ? Math.floor(i / Math.ceil(N / groups)) : i;
    const k = ease(Math.min(1, Math.max(0, (p * span - per * slot) / dur)));
    el.style.opacity = k;
    el.style.transform = `translateX(${70 * (1 - k)}px)`;
    const f = el.querySelector('.fill');
    if (f) f.style.width = (parseFloat(f.dataset.w) * k) + '%';
  });
};
"""


def main():
    inter = (ROOT / "inter.css").read_text(encoding="utf-8")
    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    only = sys.argv[1:] or list(PLAN)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for name in only:
            data = resolve(content, name)
            # Кегль списка подбираем так, чтобы он поместился в панель:
            # ниже 930 px начинается нижний отступ, с 963 идут субтитры.
            k = 1.0
            for k in (1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64):
                css, html = layout(data, k)
                base = (inter + "*{margin:0;padding:0;box-sizing:border-box}"
                        f"html,body{{width:{W}px;height:{H}px;background:transparent;"
                        "font-family:'Inter',system-ui,sans-serif;"
                        "-webkit-font-smoothing:antialiased}" + css)
                pg.set_content(f"<!doctype html><meta charset='utf-8'><style>{base}</style>{html}")
                # мерить только после загрузки Inter: на резервном шрифте
                # строки другой ширины, и подбор кегля выходит случайным
                pg.evaluate("() => document.fonts.ready")
                pg.wait_for_timeout(120)
                over = pg.evaluate(
                    "() => {const l=document.querySelector('.list');"
                    "return l.scrollHeight - l.clientHeight;}")
                if over <= 0:
                    break
            else:
                print(f"  ⚠️ {name}: не влезает даже на 0.64 кегля — сократить текст")
            if k < 1.0:
                print(f"  {name}: кегль списка ужат до {k:.2f} — длинные подписи")
            pg.add_script_tag(content=JS)
            pg.wait_for_timeout(300)

            d = OUT / name
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
            frames = round(PLAN[name] * FPS)
            for f in range(frames):
                pg.evaluate("p => window.__setP(p)", f / (frames - 1))
                pg.screenshot(path=str(d / f"{f:04d}.png"), omit_background=True)
            print(f"{name}: {data['kind']}, {len(data['items'])} элементов, "
                  f"{frames} кадров — «{data['title'][:44]}»")
        b.close()


if __name__ == "__main__":
    main()
