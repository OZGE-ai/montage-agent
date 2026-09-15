"""Шаг 1. Рендер страниц deck/presentation.pdf в PNG 1920x1080.

Урок 02: заказчик прислал презентацию не HTML-деком, а PDF. Страницы уже
ровно 1920x1080 pt, поэтому масштаб 1.0 даёт пиксель в пиксель.

Текстовый слой PDF нечитаем: весь текст идёт одним безымянным сабсетом F1
без ToUnicode, кириллица извлекается мусором. Поэтому содержание слайдов
для режима Е (панели) берётся не из PDF, а из docs/slides_text.tsv —
вычитанного вручную по картинке.
"""
import pathlib
import pymupdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF = ROOT / "deck/presentation.pdf"
OUT = ROOT / "slides"; OUT.mkdir(exist_ok=True)

doc = pymupdf.open(PDF)
print("найдено страниц:", doc.page_count)
for i, page in enumerate(doc, 1):
    r = page.rect
    zoom = 1920.0 / r.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    assert (pix.width, pix.height) == (1920, 1080), f"стр {i}: {pix.width}x{pix.height}"
    pix.save(OUT / f"s{i:02d}.png")
print("готово:", len(list(OUT.glob("s*.png"))), "PNG")
