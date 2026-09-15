# -*- coding: utf-8 -*-
"""Шаг 2. Расшифровка мастер-звука (камера A) faster-whisper с пословными таймкодами — два прохода.

    python interview/transcribe.py            # обычный: work/transcript_raw.json (для разметки ВЕДУЩАЯ/СПИКЕР)
    python interview/transcribe.py verbatim   # дословный: work/words_verbatim.json (паразиты, повторы, оговорки)

На 8 ГБ RAM large-v3 свопится — берём large-v3-turbo. Hotwords не используем: на казахской/русской речи
они заставляют модель глотать куски. «Э-э» whisper не пишет даже в дословном режиме — их ищет hesitations.py."""
import json, subprocess, sys, time
from faster_whisper import WhisperModel
from common import CFG, P, cam_file

MODEL = "deepdml/faster-whisper-large-v3-turbo-ct2"
VERBATIM_PROMPT = "Ээ, ну, мм, значит, я... ээ... мы начали, ммм, в общем, аа, это самое, ээ, закон."

if __name__ == "__main__":
    verbatim = "verbatim" in sys.argv
    wav = P + "work/master_A_16k.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cam_file("A"), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
    m = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=4)
    t0 = time.time()
    kw = dict(language=CFG.get("language", "ru"), beam_size=5, word_timestamps=True, vad_filter=False)
    if verbatim: kw.update(initial_prompt=VERBATIM_PROMPT, condition_on_previous_text=True)
    else: kw.update(condition_on_previous_text=False)
    segs, info = m.transcribe(wav, **kw)
    res = []
    for s in segs:
        res.append({"id": s.id, "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
                    "words": [{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 3)} for w in s.words]})
        print(f"[{s.start:7.1f}] {s.text.strip()}", flush=True)
    if verbatim:
        words = [dict(w=w["w"], s=round(w["start"], 2), e=round(w["end"], 2)) for s in res for w in s["words"]]
        json.dump(words, open(P + "work/words_verbatim.json", "w"), ensure_ascii=False)
    else:
        json.dump({"language": kw["language"], "segments": res}, open(P + "work/transcript_raw.json", "w"), ensure_ascii=False, indent=1)
    print("готово за", round(time.time() - t0), "с")
