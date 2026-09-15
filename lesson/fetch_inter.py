"""Собирает inter.css — @font-face с woff2, вшитыми как base64.
Из сети шрифт при рендере может не подтянуться, поэтому вшиваем заранее.
"""
import base64, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS_URL = ("https://fonts.googleapis.com/css2?"
           "family=Inter:wght@400;500;600;700;800;900&display=block")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")  # без него отдадут ttf


def get(url):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()


css = get(CSS_URL).decode()
# оставляем только кириллицу и latin — остальные подмножества ролику не нужны
blocks = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{[^}]+\})", css)
keep = {"cyrillic", "cyrillic-ext", "latin", "latin-ext"}
out = []
for subset, block in blocks:
    if subset not in keep:
        continue
    url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
    b64 = base64.b64encode(get(url)).decode()
    out.append(re.sub(r"url\(https://[^)]+\.woff2\)",
                      f"url(data:font/woff2;base64,{b64})", block))
    w = re.search(r"font-weight:\s*(\d+)", block).group(1)
    print(f"→ {subset} {w}")

(ROOT / "inter.css").write_text("\n".join(out), encoding="utf-8")
print("inter.css:", (ROOT / "inter.css").stat().st_size // 1024, "КБ,",
      len(out), "начертаний")
