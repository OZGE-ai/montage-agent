"""Шаг 8. Финальная плашка «при поддержке акимата» → work/akimat.mov (5.5 с, 25 fps).

Раскадровка из ТЗ:
  0,0–0,2  кросс-фейд из последнего кадра урока (делается при сборке, фон уже на месте)
  0,2–1,0  герб проявляется, масштаб 96 → 100 %, ease-out
  0,6–1,4  текст проявляется со сдвигом снизу вверх 24 px
  1,2–1,8  линия раскрывается из центра в обе стороны, подпись проявляется
  1,8–4,5  держим статично
  4,5–5,5  затемнение в чёрный

Герба Астаны в согласованном виде нет — место под него зарезервировано,
файл подставляется в docs/gerb.png и подхватывается автоматически.
"""
import base64, pathlib, shutil, subprocess
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRAMES = ROOT / "work/akimat_frames"
INTER = (ROOT / "inter.css").read_text(encoding="utf-8")
FPS, DUR = 25, 8.0   # заказчик просил задержать плашку дольше
N = round(FPS * DUR)

GREEN, SAND, LSAND = "#0E1D18", "#A98457", "#C6A275"
LINE1 = "Астана қаласы әкімдігінің"
LINE2 = "қолдауымен жасалды"
# Подпись студии заказчик снял.
SIGN = ""
# Трек под CC BY 4.0 — указание автора обязательно по лицензии.
# Подробности и способы убрать строку: docs/music_license.txt.
# Если docs/music.mp3 нет, строка не печатается.
# Указание автора по CC BY 4.0 заказчик убрал с экрана — оно уходит
# в описание ролика, готовый текст лежит в docs/music_credit_for_description.txt.
MUSIC_CREDIT = ""

GERB = ROOT / "docs/gerb.png"
GERB_B64 = (base64.b64encode(GERB.read_bytes()).decode() if GERB.exists() else None)

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


def ease_out(x):
    """ease-out cubic, без отскоков"""
    return 1 - (1 - x) ** 3


def seg(t, t0, t1):
    if t <= t0:
        return 0.0
    if t >= t1:
        return 1.0
    return ease_out((t - t0) / (t1 - t0))


def frame_html(t):
    g = seg(t, 0.2, 1.0)          # герб
    x = seg(t, 0.6, 1.4)          # текст
    l = seg(t, 1.2, 1.8)          # линия и подпись
    fade = 0.0 if t < DUR - 1.0 else min(1.0, (t - (DUR - 1.0)) / 1.0)  # затемнение

    # Пока герба нет, пустую рамку НЕ рисуем и место под неё не резервируем:
    # в сдаточном ролике пунктирный квадрат выглядит недоделкой. Плашка
    # центрируется флексом, поэтому с приходом docs/gerb.png вёрстка
    # соберётся обратно сама, править ничего не придётся.
    gerb = (f'<img src="data:image/png;base64,{GERB_B64}" style="height:210px;'
            f'display:block;margin:0 auto">' if GERB_B64 else "")

    sign_html = (f'<div style="margin-top:36px;opacity:{l:.4f};font-size:15px;'
                 f'font-weight:700;letter-spacing:.26em;'
                 f'color:rgba(255,255,255,.62)">{SIGN}</div>') if SIGN else ""

    return f"""<div style="position:absolute;inset:0;background:{GREEN}">
  <div style="position:absolute;inset:0;background:{DUOTONE}"></div>
  <div style="position:absolute;inset:0;display:flex;flex-direction:column;
       align-items:center;justify-content:center;text-align:center">
    {f'<div style="opacity:{g:.4f};transform:scale({0.96 + 0.04 * g:.4f});margin-bottom:54px">{gerb}</div>' if gerb else ""}
    <div style="opacity:{x:.4f};transform:translateY({24 * (1 - x):.2f}px)">
      <div style="font-size:64px;font-weight:900;line-height:1.12;color:{LSAND};
           letter-spacing:-.01em">{LINE1}</div>
      <div style="font-size:64px;font-weight:900;line-height:1.12;color:#fff;
           letter-spacing:-.01em">{LINE2}</div>
    </div>
    <div style="margin-top:44px;width:{320 * l:.1f}px;height:3px;background:{SAND}"></div>
    {sign_html}
    <div style="margin-top:{36 if not SIGN else 14}px;opacity:{l * 0.75:.4f};
         font-size:12px;font-weight:600;letter-spacing:.06em;
         color:rgba(255,255,255,.42)">{MUSIC_CREDIT}</div>
  </div>
  <div style="position:absolute;inset:0;background:#000;opacity:{fade:.4f}"></div>
</div>"""


def main():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)
    css = (INTER + "*{margin:0;padding:0;box-sizing:border-box}"
           "html,body{width:1920px;height:1080px;overflow:hidden;"
           "font-family:'Inter',system-ui,sans-serif;-webkit-font-smoothing:antialiased}")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        for i in range(N):
            t = i / FPS
            pg.set_content(f"<!doctype html><meta charset='utf-8'><style>{css}</style>"
                           f"{frame_html(t)}")
            if i == 0:
                pg.wait_for_timeout(400)
            pg.screenshot(path=str(FRAMES / f"{i:04d}.png"))
        b.close()
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-v", "error", "-framerate", str(FPS),
         "-i", str(FRAMES / "%04d.png"), "-c:v", "libx264", "-crf", "16",
         "-preset", "medium", "-pix_fmt", "yuv420p", str(ROOT / "work/akimat.mov")],
        check=True)
    print(f"akimat.mov: {N} кадров, {N/FPS:.2f} с"
          + ("" if GERB_B64 else "  ⚠ БЕЗ ГЕРБА — место зарезервировано"))


if __name__ == "__main__":
    main()
