"""Шаг 6. Инфографика — анимированная версия того, что уже есть на слайде.

Слайд заказчика не переделываем: рендерим ЕГО ЖЕ разметку с его же CSS,
только на каждом кадре выставляем элементам состояние по прогрессу.
Получается секвенция PNG на время анимации; дальше в compose держим
последний кадр до конца показа слайда.

Правила: одна анимация на слайд, 0,4–0,8 с на появление, ease-out,
без отскоков и поворотов, элемент появился — остаётся. Больше семи
элементов — выходят группами, а не по одному.
"""
import pathlib, re, shutil, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "slides/anim"
FPS = 25

# слайд → (тип анимации, длительность секвенции в секундах)
PLAN = {
    "s04": ("chips", 1.8),
    "s06": ("chips", 1.6),
    "s08": ("chips", 1.2),
    "s12": ("cards", 2.6),
    "s15": ("stats", 1.8),
    "s16": ("stats", 1.8),
    "s17": ("bars", 1.8),
    "s18": ("grid9", 2.6),
    "s19": ("cards", 2.2),
    "s20": ("cards", 2.2),
}

JS = r"""
window.__init = (kind) => {
  const S = document.currentSlide;
  const q = (sel) => Array.from(S.querySelectorAll(sel));
  let items = [];
  if (kind === 'bars')  items = q('.barrow .fill');
  else if (kind === 'stats') items = q('.stat');
  else if (kind === 'chips') items = q('.chip');
  else items = q('.card');

  // запоминаем исходное состояние — к нему и придём
  window.__items = items.map(el => {
    const cs = getComputedStyle(el);
    const n = el.querySelector('.n');
    return {
      el, n,
      width: el.style.width || null,
      num: n ? n.textContent : null,
      bar: el.querySelector('.bar'),
      bg: cs.backgroundColor, bc: cs.borderColor,
      inner: Array.from(el.querySelectorAll('.k,.t,.d'))
                  .map(x => ({x, c: getComputedStyle(x).color})),
    };
  });
  window.__kind = kind;
  return items.length;
};

const ease = x => 1 - Math.pow(1 - x, 3);
const mix = (a, b, t) => {
  const pa = a.match(/[\d.]+/g).map(Number), pb = b.match(/[\d.]+/g).map(Number);
  const c = [0,1,2].map(i => Math.round(pa[i] + (pb[i] - pa[i]) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
};

window.__setP = (p) => {
  const it = window.__items, kind = window.__kind, N = it.length;
  // больше семи элементов — выпускаем группами
  const groups = N > 7 ? Math.ceil(N / Math.ceil(N / 4)) : 1;
  const per = kind === 'bars' ? 0.04 : (N > 7 ? 0.16 : 0.22);   // задержка
  const dur = kind === 'bars' ? 0.6 : 0.5;                       // появление
  const span = per * (N > 7 ? Math.ceil(N / groups) : N) + dur;

  it.forEach((o, i) => {
    const slot = N > 7 ? Math.floor(i / Math.ceil(N / groups)) : i;
    const t0 = per * slot;
    const k = ease(Math.min(1, Math.max(0, (p * span - t0) / dur)));

    if (kind === 'bars') {
      o.el.style.width = (parseFloat(o.width) * k) + '%';
      return;
    }
    if (kind === 'stats') {
      o.el.style.opacity = k;
      if (o.bar) o.bar.style.width = (64 * k) + 'px';
      if (o.n && o.num) {
        // счётчик только там, где число — «№52-VII» и «2023 → 2025» не крутим
        const m = o.num.match(/^([^\d]*)(\d+)([^\d]*)$/);
        o.n.textContent = (m && m[2].length <= 4)
          ? m[1] + Math.round(parseInt(m[2]) * k) + m[3]
          : o.num;
      }
      return;
    }
    o.el.style.opacity = k;
    o.el.style.transform = `translateY(${20 * (1 - k)}px)`;
    if (kind === 'grid9' && o.bg !== 'rgb(255, 255, 255)') {
      // активные блоки заливаются песочным после появления
      const f = ease(Math.min(1, Math.max(0, (p * span - t0 - dur) / 0.5)));
      o.el.style.backgroundColor = mix('rgb(255,255,255)', o.bg, f);
      o.el.style.borderColor = mix('rgb(225,223,216)', o.bc, f);
      o.inner.forEach(({x, c}) => { x.style.color = mix('rgb(99,99,94)', c, f); });
    }
  });
};
"""


def main():
    html = (ROOT / "deck/presentation.html").read_text(encoding="utf-8")
    inter = (ROOT / "inter.css").read_text(encoding="utf-8")
    html, n = re.subn(r"@import url\('https://fonts\.googleapis\.com/[^']+'\);", inter, html)
    assert n == 1
    # аббревиатура везде кириллицей; прочие ASI — внутри base64-картинок
    html = html.replace("\u00b7 ASI", "\u00b7 \u0410\u0421\u0418")
    html = html.replace("</head>", "<style>.toolbar{display:none!important}"
                                   "body{background:#fff}.deck{gap:0;padding:0}</style></head>")

    only = sys.argv[1:] or list(PLAN)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5)
        pg.set_content(html, wait_until="load")
        pg.wait_for_timeout(1200)
        pg.add_script_tag(content=JS)
        for name in only:
            kind, dur = PLAN[name]
            idx = int(name[1:])
            d = OUT / name
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
            cnt = pg.evaluate(
                "([i,k]) => { document.currentSlide = "
                "document.querySelectorAll('section.slide')[i-1];"
                " return window.__init(k); }", [idx, kind])
            el = pg.query_selector_all("section.slide")[idx - 1]
            frames = round(dur * FPS)
            for f in range(frames):
                pg.evaluate("p => window.__setP(p)", f / (frames - 1))
                el.screenshot(path=str(d / f"{f:04d}.png"))
            print(f"{name}: {kind}, {cnt} элементов, {frames} кадров ({dur:.1f} с)")
        b.close()


if __name__ == "__main__":
    main()
