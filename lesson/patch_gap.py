"""Разовая заплатка: whisper проглотил 640-668 с («Главный вывод»).
Перерасшифровываем окно и вставляем сегменты в work/transcript.json.
Окно и границы замены заданы ниже; после правки скрипт больше не нужен.
"""
import json, pathlib, subprocess
from faster_whisper import WhisperModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
A, B = 638.0, 673.0          # окно перерасшифровки
LO, HI = 638.0, 672.4        # какие сегменты заменяем

W = str(ROOT / "work/_patch.wav")
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(A), "-t", str(B - A),
                "-i", str(ROOT / "work/asr.wav"), "-y", W], check=True)
m = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cpu",
                 compute_type="int8", cpu_threads=4)
seg, _ = m.transcribe(W, language="ru", word_timestamps=True, vad_filter=False, beam_size=3)

new = []
for s in seg:
    words = [{"w": w.word, "s": round(A + w.start, 2), "e": round(A + w.end, 2),
              "p": w.probability} for w in s.words]
    if not words:
        continue
    new.append({"start": words[0]["s"], "end": words[-1]["e"],
                "text": s.text, "words": words})

d = json.load(open(ROOT / "work/transcript.json", encoding="utf-8"))
old = [s for s in d["segments"] if LO <= s["start"] < HI]
keep = [s for s in d["segments"] if not (LO <= s["start"] < HI)]
d["segments"] = sorted(keep + new, key=lambda s: s["start"])
json.dump(d, open(ROOT / "work/transcript.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("убрано", len(old), "· добавлено", len(new), "· всего", len(d["segments"]))
for s in new:
    print(f"[{s['start']:7.2f}] {s['text'].strip()}")
