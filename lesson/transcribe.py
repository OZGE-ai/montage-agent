"""Шаг 2. Расшифровка с пословными таймкодами.
Звук берём почти сырой (work/asr.wav = highpass 80 Гц): whisper обучен на живой речи,
обработанную дорожку он разбирает хуже.
"""
import json, re, sys, time, pathlib
from faster_whisper import WhisperModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIO = str(ROOT / "work/asr.wav")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "large-v3"
# Урок 02 идёт по-русски (дек русский, детект языка 0.999 ru).
# В уроке 01 было "kk" — язык задаётся вторым аргументом.
LANG = sys.argv[2] if len(sys.argv) > 2 else "ru"

# hotwords ОТКЛЮЧЕНЫ. С длинным списком модель пересказывала сам глоссарий;
# с коротким — вставила «Қасым-Жомарт» в чужое место и проглотила 20–46 с
# вместе с представлением спикера. Без подсказок расшифровка полная,
# а термины и имена правим при вычитке и переводе.
HOTWORDS = ""

t0 = time.time()
# 4 потока = только производительные ядра M1; на 8 потоках часть работы
# уезжает на энергоэффективные и всё считается медленнее
model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=4)
segments, info = model.transcribe(
    AUDIO,
    language=LANG,
    beam_size=3,
    word_timestamps=True,
    vad_filter=False,
    condition_on_previous_text=False,
    hotwords=HOTWORDS,
)
print(f"model={MODEL} lang={info.language} p={info.language_probability:.2f} "
      f"dur={info.duration:.1f}", flush=True)

out = []
with open(ROOT / "raw/transcript.txt", "w", encoding="utf-8") as f:
    for s in segments:
        f.write(f"[{s.start:7.2f} -> {s.end:7.2f}] {s.text.strip()}\n")
        print(f"[{s.start:7.2f}] {s.text.strip()}", flush=True)
        out.append({
            "start": s.start, "end": s.end, "text": s.text,
            "words": [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability}
                      for w in (s.words or [])],
        })

json.dump({"model": MODEL, "language": info.language, "duration": info.duration,
           "segments": out},
          open(ROOT / "work/transcript.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"DONE in {time.time()-t0:.0f}s, {len(out)} segments", flush=True)
