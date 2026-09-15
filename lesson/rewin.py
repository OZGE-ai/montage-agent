"""Перерасшифровка коротких окон вокруг ручных вырезок — точнее границы слов.

    .venv/bin/python tools/rewin.py 119:129 615:633
"""
import sys, subprocess, pathlib
from faster_whisper import WhisperModel
ROOT = pathlib.Path(__file__).resolve().parent.parent
S = str(ROOT / 'work/_win.wav')
m=WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2",device="cpu",compute_type="int8",cpu_threads=4)
for arg in sys.argv[1:]:
    a,b=map(float,arg.split(':'))
    subprocess.run(["ffmpeg","-nostdin","-v","error","-ss",str(a),"-t",str(b-a),"-i",str(ROOT / "work/asr.wav"),"-y",S],check=True)
    seg,_=m.transcribe(S,language="ru",word_timestamps=True,vad_filter=False,beam_size=3)
    print(f"== {a}-{b}")
    print(' '.join(f"{w.word.strip()}@{a+w.start:.2f}-{a+w.end:.2f}" for s in seg for w in s.words))
