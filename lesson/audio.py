"""Шаг 2а. Три звуковые дорожки из raw/speaker.mp4.

В уроке 01 дорожки лежали в work/ и отдельным скриптом не собирались.
Здесь исходник другой (Sony 4K, PCM 48k стерео вместо AAC 44.1k), поэтому
цепочки выписаны явно — как описано в docs/pipeline.md:

  asr.wav     16k моно, highpass 80  — почти сырой, whisper обученному на
                                       живой речи обработка только мешает
  detect.wav  16k моно, +adeclip +afftdn — под поиск пауз: с чистым фоном
                                       порог -38 dB / 0.4 с работает
  clean48.wav 48k стерео, полная цепочка — идёт в мастер clean.mov

Компрессор есть только в clean48: он поднимает фон, и паузы по нему
уже не ищутся — за этим и нужна отдельная detect.wav.
"""
import pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "raw/speaker.mp4"
W = ROOT / "work"; W.mkdir(exist_ok=True)

HP = "highpass=f=80"
DENOISE = "adeclip,afftdn=nf=-28"
FULL = (f"{HP},{DENOISE},"
        "equalizer=f=220:t=q:w=1.2:g=-2,"      # подрезать бубнение стола
        "deesser=i=0.4,"
        "acompressor=threshold=-20dB:ratio=3:attack=8:release=180:makeup=2,"
        "loudnorm=I=-16:TP=-1.5:LRA=11")

JOBS = [("asr.wav",     ["-ac", "1", "-ar", "16000"], HP),
        ("detect.wav",  ["-ac", "1", "-ar", "16000"], f"{HP},{DENOISE}"),
        ("clean48.wav", ["-ac", "2", "-ar", "48000"], FULL)]

for name, args, af in JOBS:
    out = W / name
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-v", "warning", "-nostdin",
                    "-i", str(SRC), "-vn", "-af", af, *args,
                    "-c:a", "pcm_s16le", str(out)], check=True)
    print(f"{name}: {out.stat().st_size/1e6:.1f} МБ")
