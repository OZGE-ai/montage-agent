# -*- coding: utf-8 -*-
"""Шаг 8б. Плашки ФИО: PNG с альфой, 1920×1080 и 1080×1920, два варианта подложки (плашка / растушёвка).
Данные — только из speakers.json (name, title, slug), ничего не додумывается."""
import json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from common import CFG, P
ROOT = P
FONT = ROOT + CFG["brand"]["font"]
RED = tuple(CFG["brand"]["red"]) + (255,)

def font(size, weight):
    f = ImageFont.truetype(FONT, size); f.set_variation_by_name(weight); return f

def tracked(draw, xy, text, f, fill, track):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + track
    return x

def tracked_len(text, f, track): return sum(f.getlength(c) for c in text) + track * (len(text) - 1)

def wrap(text, f, maxw):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if f.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = word
    return lines + [cur]

def render(sp, W, H, left, bottom, variant, maxw):
    name = sp["name"].upper(); fn = font(52 if W > H else 50, b"ExtraBold"); ft = font(30, b"Medium")
    track = 0.02 * fn.size
    tlines = wrap(sp["title"], ft, maxw)
    name_w = tracked_len(name, fn, track)
    asc_n = fn.getbbox("ДЙ")[1]; name_h = fn.getbbox("ДЖЩ")[3] - asc_n
    gap1, line_h, gap2 = 22, 4, 22
    t_top_off = ft.getbbox("Д")[1]; t_line = 42
    title_h = t_line * (len(tlines) - 1) + (ft.getbbox("Дд")[3] - t_top_off)
    content_w = max(name_w, max(ft.getlength(l) for l in tlines), 80)
    content_h = name_h + gap1 + line_h + gap2 + title_h
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pad_x, pad_y = 36, 30
    if variant == "plate":
        bx0 = left; by1 = H - bottom
        bx1 = bx0 + content_w + 2 * pad_x; by0 = by1 - content_h - 2 * pad_y
        plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle([bx0, by0, bx1, by1], radius=4, fill=(0, 0, 0, int(255 * 0.55)))
        img = Image.alpha_composite(img, plate)
        cx, cy = bx0 + pad_x, by0 + pad_y
    else:  # мягкая растушёвка снизу
        gh = int(content_h + bottom + 260)
        grad = Image.new("L", (1, gh))
        for y in range(gh):
            p = y / (gh - 1); grad.putpixel((0, y), int(255 * 0.72 * (p ** 1.6)))
        g = Image.new("RGBA", (W, gh), (0, 0, 0, 255)); g.putalpha(grad.resize((W, gh)))
        img.alpha_composite(g, (0, H - gh))
        cx, cy = left, H - bottom - content_h
    d = ImageDraw.Draw(img)
    # тень для читаемости без плашки
    if variant == "gradient":
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        tracked(sd, (cx + 2, cy - asc_n + 2), name, fn, (0, 0, 0, 150), track)
        for i, l in enumerate(tlines): sd.text((cx + 2, cy + name_h + gap1 + line_h + gap2 - t_top_off + i * t_line + 2), l, font=ft, fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(4))); d = ImageDraw.Draw(img)
    tracked(d, (cx, cy - asc_n), name, fn, (255, 255, 255, 255), track)
    ly = cy + name_h + gap1
    d.rectangle([cx, ly, cx + 79, ly + line_h - 1], fill=RED)
    for i, l in enumerate(tlines):
        d.text((cx, ly + line_h + gap2 - t_top_off + i * t_line), l, font=ft, fill=(255, 255, 255, int(255 * 0.8)))
    return img

sps = json.load(open(ROOT + CFG["speakers"], encoding="utf-8"))
out = ROOT + "output/graphics/"
for sp in sps:
    for variant in ("plate", "gradient"):
        render(sp, 1920, 1080, 120, 140, variant, 1500).save(f"{out}lower_third_{sp['slug']}_{variant}.png")
        render(sp, 1080, 1920, 80, 420, variant, 1080 - 80 - 80 - 72).save(f"{out}lower_third_{sp['slug']}_{variant}_vertical.png")
print("ok")
