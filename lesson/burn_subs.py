"""Версия ролика с вшитыми субтитрами.

ffmpeg в этой сборке без libass — фильтров subtitles/ass/drawtext нет,
поэтому реплики рисуем playwright'ом тем же Inter, что и остальная графика,
собираем дорожку с альфой и накладываем одним проходом.

Позиция по ТЗ: одна строка, 38 px, 72 px от нижнего края — то есть внутри
зоны субтитров y 880–1080, где графики нет.
"""
import pathlib, re, shutil, subprocess, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
import json as _json
_L = _json.loads((ROOT / "lesson.json").read_text(encoding="utf-8"))
SLUG = _L["slug"]
SRT = ROOT / f"final/{SLUG}.srt"
SRC = ROOT / f"final/{SLUG}.mp4"
OUT = ROOT / f"final/{SLUG}_subs.mp4"
PNG = ROOT / "work/subs_png"
FPS = 25
SIZE, BOTTOM = 38, 72


def parse():
    def t(x):
        h, m, rest = x.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for block in SRT.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.split("\n")
        a, b = lines[1].split(" --> ")
        cues.append((t(a), t(b), " ".join(lines[2:]).strip()))
    return cues


def render(cues):
    if PNG.exists():
        shutil.rmtree(PNG)
    PNG.mkdir(parents=True)
    inter = (ROOT / "inter.css").read_text(encoding="utf-8")
    css = (inter + "*{margin:0;padding:0}"
           "html,body{width:1920px;height:1080px;background:transparent;"
           "font-family:'Inter',system-ui,sans-serif;-webkit-font-smoothing:antialiased}"
           f".s{{position:absolute;left:0;right:0;bottom:{BOTTOM}px;text-align:center;"
           "padding:0 160px}"
           f".s span{{display:inline-block;font-size:{SIZE}px;font-weight:700;"
           "line-height:1.3;color:#fff;white-space:nowrap;"
           "text-shadow:0 2px 10px rgba(0,0,0,.9),0 0 30px rgba(0,0,0,.75),"
           "0 0 3px rgba(0,0,0,.9)}")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        pg.set_content(f"<!doctype html><meta charset='utf-8'><style>{css}</style>"
                       "<div class='s'><span id='t'></span></div>")
        pg.wait_for_timeout(400)
        for i, (_, _, text) in enumerate(cues):
            pg.eval_on_selector("#t", "(e,v)=>e.textContent=v", text)
            pg.screenshot(path=str(PNG / f"{i:04d}.png"), omit_background=True)
        pg.eval_on_selector("#t", "e=>e.textContent=''")
        pg.screenshot(path=str(PNG / "blank.png"), omit_background=True)
        b.close()
    print(f"нарисовано реплик: {len(cues)}")


def build_track(cues, total):
    """Склеиваем дорожку с альфой: реплика — свой кадр, пауза — пустой."""
    lines, t = [], 0.0
    blank = (PNG / "blank.png").as_posix()
    for i, (a, b, _) in enumerate(cues):
        if a - t > 0.001:
            lines.append(f"file '{blank}'\nduration {a - t:.3f}")
        lines.append(f"file '{(PNG / f'{i:04d}.png').as_posix()}'\nduration {b - a:.3f}")
        t = b
    if total - t > 0.001:
        lines.append(f"file '{blank}'\nduration {total - t:.3f}")
    lines.append(f"file '{blank}'")
    lst = ROOT / "work/subs_concat.txt"
    lst.write_text("\n".join(lines), encoding="utf-8")
    track = ROOT / "work/subs_track.mov"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-r", str(FPS), "-c:v", "qtrle", "-pix_fmt", "argb", str(track)],
        check=True)
    print("дорожка субтитров:", track.stat().st_size // 1024 // 1024, "МБ")
    return track


def main():
    cues = parse()
    total = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(SRC)], capture_output=True, text=True).stdout.strip())
    render(cues)
    track = build_track(cues, total)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-v", "warning", "-stats",
         "-i", str(SRC), "-i", str(track),
         "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[v]",
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "18",
         "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "copy", "-movflags", "+faststart", str(OUT)], check=True)
    print("готово:", OUT)


if __name__ == "__main__":
    main()
