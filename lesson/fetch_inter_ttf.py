"""Качает Inter в TTF — Pillow не умеет woff2, а весь текст на видео рисуем Pillow."""
import pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "fonts"; OUT.mkdir(exist_ok=True)
# старый User-Agent → Google Fonts отдаёт ttf вместо woff2
UA = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"


def get(url, ua=UA):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": ua}), timeout=60).read()


css = get("https://fonts.googleapis.com/css?family=Inter:400,600,700,800,900"
          "&subset=cyrillic,cyrillic-ext,latin,latin-ext").decode()
for w, url in re.findall(r"font-weight:\s*(\d+);.*?url\((https://[^)]+\.ttf)\)", css, re.S):
    p = OUT / f"Inter-{w}.ttf"
    p.write_bytes(get(url))
    print("→", p.name, p.stat().st_size // 1024, "КБ")
if not list(OUT.glob("*.ttf")):
    raise SystemExit("ttf не отдали, смотри ответ Google Fonts")
