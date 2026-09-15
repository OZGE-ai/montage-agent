# -*- coding: utf-8 -*-
"""Шаг 8. Графика с альфа-каналом (QuickTime Animation .mov): фразы-триггеры, заставка поверх видео, финал.

    python interview/graphics.py t1 t2 t3 t4 title outro

Фразы-триггеры в стиле The Diary Of A CEO: фраза разбита на строки, ключевые слова ExtraBold крупно (акцент — красным),
служебные Light мельче; каждое слово проявляется в момент, когда его произносят (пословные таймкоды whisper).
Текст стоит на пустой половине кадра, правая половина чуть затемнена. Всё — из project.json → triggers / brand."""
import json, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import CFG, P

FPS, W, H = CFG.get("fps", 30), 1920, 1080
BR = CFG["brand"]; FONT = P + BR["font"]; RED = tuple(BR["red"])
Wd = json.load(open(P + "work/words_feat.json"))
SIZE = {"k": 90, "a": 90, "l": 44}
X0, XMAX, YC = 1110, 1850, 360


def font(size, weight):
    f = ImageFont.truetype(FONT, int(size)); f.set_variation_by_name(weight); return f
def ease_out(p): p = min(max(p, 0), 1); return 1 - (1 - p) ** 3
def writer(path, n):
    return subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS),
                             "-i", "-", "-frames:v", str(n), "-c:v", "qtrle", path], stdin=subprocess.PIPE)
def fade(img, k):
    x = img.copy(); x.putalpha(img.getchannel("A").point(lambda v: int(v * k))); return x


# ── фразы-триггеры ──
def build_phrase(ph):
    a, b = ph["clip"]
    queue = [w for w in Wd if w["end"] > a + 0.15 and w["start"] < b - 0.12 and w["w"] not in ("–", "—")]
    chunks, qi = [], 0
    for li, grp in enumerate(ph["layout"]):
        for gi in grp:
            text, st = ph["lines"][gi][:2]; sz = ph["lines"][gi][2] if len(ph["lines"][gi]) > 2 else SIZE[st]
            for tok in text.split():
                if tok == "—": t = chunks[-1][3] if chunks else 0.0
                else:
                    t = max(queue[qi]["start"] - a, 0.0); qi += 1
                    if tok.endswith("%") and len(tok) > 1: qi += 1          # whisper пишет «53» и «%» отдельно
                chunks.append([li, tok.upper(), st, t, sz])
    assert qi == len(queue), (ph["id"], "слов на экране", qi, "в речи", len(queue), [w["w"] for w in queue])
    lines = {}
    for c in chunks: lines.setdefault(c[0], []).append(c)
    placed, y = [], 0
    for li in sorted(lines):
        items = lines[li]
        width = sum(font(c[4], b"ExtraBold" if c[2] != "l" else b"Light").getlength(c[1] + " ") for c in items) - font(items[-1][4], b"Light").getlength(" ")
        scale = min(1.0, (XMAX - X0) / width); big = max(c[4] for c in items) * scale; x = X0
        for _, tok, st, t, sz in items:
            f = font(sz * scale, b"ExtraBold" if st != "l" else b"Light")
            placed.append(dict(st=st, tok=tok, f=f, x=x, y=y + (big - sz * scale) * 0.78 - f.getbbox("ДЙ")[1], t=t,
                               color=RED if st == "a" else (255, 255, 255)))
            x += f.getlength(tok + " ")
        y += big * 1.18
    top = max(80, min(YC - y / 2, 1000 - y))
    for p in placed: p["y"] += top
    return placed


def render_phrase(ph):
    placed = build_phrase(ph); a, b = ph["clip"]; n = int(round((b - a) * FPS))
    g = np.zeros((H, W, 4), np.uint8); g[..., 3] = (np.clip((np.arange(W) - 820) / (W - 1000), 0, 1) ** 1.1 * 0.72 * 255).astype(np.uint8)[None, :]
    base = Image.fromarray(g, "RGBA"); sprites = []
    for p in placed:
        bb = p["f"].getbbox(p["tok"]); im = Image.new("RGBA", (int(bb[2]) + 16, int(bb[3]) + 16), (0, 0, 0, 0))
        sh = im.copy(); ImageDraw.Draw(sh).text((6, 7), p["tok"], font=p["f"], fill=(0, 0, 0, 120))
        ImageDraw.Draw(im).text((4, 4), p["tok"], font=p["f"], fill=p["color"] + (255,)); sprites.append((Image.alpha_composite(sh, im), p))
    pr = writer(P + f"work/render/layer_{ph['id']}.mov", n)
    for fr in range(n):
        frame = base.copy()
        for im, p in sprites:
            k = ease_out((fr / FPS - p["t"]) / 0.18)
            if k > 0: frame.alpha_composite(fade(im, k), (int(p["x"] - 4), int(p["y"] - 4 + 14 * (1 - k))))
        pr.stdin.write(frame.tobytes())
    pr.stdin.close(); pr.wait(); return n


# ── заставка поверх видео мероприятия ──
def render_title(n=145):
    dur = n / FPS; f1 = font(58, b"ExtraBold"); f2 = font(32, b"Light"); L1, L2, L3 = BR["summit_title"]
    g = np.zeros((H, W, 4), np.uint8); g[..., 3] = (np.clip((np.arange(H) - 560) / (H - 700), 0, 1) ** 1.1 * 0.88 * 255).astype(np.uint8)[:, None]
    G = Image.fromarray(g, "RGBA"); txt = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(txt); y = 850
    for t_ in (L1, L2):
        x = (W - f1.getlength(t_)) / 2
        d.text((x + 3, y - f1.getbbox("Д")[1] + 3), t_, font=f1, fill=(0, 0, 0, 110)); d.text((x, y - f1.getbbox("Д")[1]), t_, font=f1, fill=(255, 255, 255, 255)); y += 74
    d.rectangle([(W - 80) // 2, y + 8, (W + 80) // 2 - 1, y + 11], fill=RED + (255,))
    d.text(((W - f2.getlength(L3)) / 2, y + 36 - f2.getbbox("А")[1]), L3, font=f2, fill=(255, 255, 255, 225))
    pr = writer(P + "work/render/layer_title.mov", n)
    for fr in range(n):
        t = fr / FPS; frame = Image.new("RGBA", (W, H), (0, 0, 0, 0)); frame.alpha_composite(fade(G, min(t / 0.25, 1)))
        kt = ease_out((t - 0.2) / 0.45) * min(max((dur - t) / 0.25, 0), 1)
        if kt > 0: frame.alpha_composite(fade(txt, kt), (0, int(18 * (1 - ease_out((t - 0.2) / 0.45)))))
        pr.stdin.write(frame.tobytes())
    pr.stdin.close(); pr.wait(); return n


# ── финал на синем: логотип партнёра, крупная строка, логотип студии ──
def blue_bg():
    yy, xx = np.mgrid[0:H, 0:W]
    k = np.clip(np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.45) / (H * 0.75)) ** 2), 0, 1) ** 1.2
    img = np.array([38, 76, 150])[None, None] * (1 - k[..., None]) + np.array([12, 32, 66])[None, None] * k[..., None]
    img += np.random.default_rng(3).normal(0, 1.2, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def render_outro(dur=6.5):
    n = int(round(dur * FPS)); bg = blue_bg(); bg.save(P + "work/render/outro_blue_bg.png")
    def logo(path, w):
        im = Image.open(P + path).convert("RGBA"); im = im.crop(im.getbbox()); return im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    top_logo, bottom_logo = logo(BR["outro_top_logo"], 300), logo(BR["outro_bottom_logo"], 200)
    f = font(62, b"SemiBold"); line = BR["outro_line"]
    while f.getlength(line) > W - 200: f = font(f.size - 2, b"SemiBold")
    asc = f.getbbox("Ә")[1]; th = f.getbbox("Әқ")[3] - asc
    top = (H - (top_logo.height + 56 + th + 70 + bottom_logo.height)) // 2; y2 = top + top_logo.height + 56
    L1 = Image.new("RGBA", (W, H), (0, 0, 0, 0)); L1.alpha_composite(top_logo, ((W - top_logo.width) // 2, top))
    L2 = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L2); x = (W - f.getlength(line)) / 2
    d.text((x + 2, y2 - asc + 3), line, font=f, fill=(0, 0, 0, 70)); d.text((x, y2 - asc), line, font=f, fill=(255, 255, 255, 255))
    L3 = Image.new("RGBA", (W, H), (0, 0, 0, 0)); L3.alpha_composite(bottom_logo, ((W - bottom_logo.width) // 2, y2 + th + 70))
    pr = writer(P + "work/render/layer_outro.mov", n)
    for fr in range(n):
        frame = bg.copy()
        for L, t0 in ((L1, 0.2), (L2, 0.7), (L3, 1.3)):
            k = ease_out((fr / FPS - t0) / 0.8)
            if k > 0: frame.alpha_composite(fade(L, k), (0, int(14 * (1 - k))))
        pr.stdin.write(frame.tobytes())
    pr.stdin.close(); pr.wait(); return n


if __name__ == "__main__":
    what = sys.argv[1:] or [p["id"] for p in CFG["triggers"]] + ["title", "outro"]
    for ph in CFG["triggers"]:
        if ph["id"] in what: print(ph["id"], render_phrase(ph), "кадров")
    if "title" in what: print("title", render_title())
    if "outro" in what: print("outro", render_outro())
