"""Проверка перед сдачей — раздел 9 инструкции, машинная часть.

    .venv/bin/python tools/final_check.py

Смотрит готовые файлы в final/: кадры против длительности, громкость и
тру-пик, последнюю реплику субтитров против финальной плашки, и ищет в
субтитрах слова из выброшенных кусков. Остальное (прослушать вырезки,
посмотреть ролик целиком) — глазами и ушами.
"""
import csv, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLUG = json.loads((ROOT / "lesson.json").read_text(encoding="utf-8"))["slug"]
AKIMAT = 8.0
ok = True


def say(good, text):
    global ok
    ok = ok and good
    print(("  ок  " if good else "  ✗   ") + text)


def probe(path, *entries):
    out = subprocess.run(["ffprobe", "-v", "error", *entries, "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.split()
    return out


print("кадры против длительности")
for name in (f"{SLUG}.mp4", f"{SLUG}_subs.mp4"):
    p = ROOT / "final" / name
    if not p.exists():
        say(False, f"{name} — нет файла"); continue
    nb = int(probe(p, "-select_streams", "v:0", "-show_entries", "stream=nb_frames")[0])
    du = float(probe(p, "-show_entries", "format=duration")[0])
    say(abs(nb - du * 25) < 3, f"{name}: {nb} кадров при {du:.2f} с")

print("\nгромкость")
r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(ROOT / f"final/{SLUG}.mp4"),
                    "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
lufs = re.findall(r"I:\s+(-?\d+\.\d+) LUFS", r)
peak = re.findall(r"Peak:\s+(-?\d+\.\d+) dBFS", r)
if lufs:
    v = float(lufs[-1]); say(-17.0 <= v <= -15.0, f"интегральная громкость {v} LUFS (серия идёт на −16)")
if peak:
    v = float(peak[-1]); say(v <= -1.4, f"тру-пик {v} dBTP (не выше −1,4)")

print("\nсубтитры")
# Проверки ниже читают готовый ролик. Если его нет — выходим с внятным
# сообщением, а не трассировкой: урок 05, 14.09 — mp4 унесли из final/,
# и скрипт падал IndexError на пустом ответе ffprobe.
if not (ROOT / f"final/{SLUG}.mp4").exists():
    print("  — пропущено: нет final/" + SLUG + ".mp4")
    print("\nИТОГ: ПРОВЕРКА НЕ ДОВЕДЕНА — ролика нет в final/")
    raise SystemExit(1)
srt = (ROOT / f"final/{SLUG}.srt").read_text(encoding="utf-8")
times = re.findall(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)", srt)
last = max(int(t[4]) * 3600 + int(t[5]) * 60 + int(t[6]) + int(t[7]) / 1000 for t in times)
du = float(probe(ROOT / f"final/{SLUG}.mp4", "-show_entries", "format=duration")[0])
say(last <= du - AKIMAT + 0.1,
    f"последняя реплика кончается на {last:.2f} с, плашка акимата с {du - AKIMAT:.2f} с")

# слова из выброшенных кусков не должны всплыть в субтитрах
keeps = [(float(r["начало"]), float(r["конец"]))
         for r in csv.DictReader(open(ROOT / "keeps.csv", encoding="utf-8"))] \
    if (ROOT / "keeps.csv").exists() else []
if keeps:
    d = json.load(open(ROOT / "work/transcript.json", encoding="utf-8"))
    words = [w for s in d["segments"] for w in s["words"] if w["w"].strip()]
    dropped = " ".join(w["w"] for w in words
                       if not any(s <= w["s"] <= e for s, e in keeps))
    marks = ["четвертый слайд", "еще раз", "по времени нормально",
             "impact measure", "Подписывайтесь"]
    ru = (ROOT / f"final/{SLUG}_ru.srt").read_text(encoding="utf-8").lower()
    found = [m for m in marks if m.lower() in ru and m.lower() in dropped.lower()]
    say(not found, "в русских субтитрах нет фраз из выброшенных дублей"
        + (f": найдено {found}" if found else ""))

print("\nфайлы")
for name in (f"{SLUG}.mp4", f"{SLUG}_subs.mp4", f"{SLUG}.srt", f"{SLUG}_ru.srt"):
    say((ROOT / "final" / name).exists(), f"final/{name}")

print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ЗАМЕЧАНИЯ")
sys.exit(0 if ok else 1)
