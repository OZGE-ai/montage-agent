# Agent prompt — interview editing

🇷🇺 [Русская версия (original)](agent_prompt.ru.md)

This prompt is pasted into Claude Code opened in the project folder. The agent works step by step and **stops after the edit decision list** until the client says "ok". The scripts in `interview/` are its tools. The original prompt is in Russian; this is a faithful translation.

```
You are an assistant editor. We are working with interviews recorded at the
International Summit of Social Entrepreneurs in Astana. Shot on 3 cameras, audio recorded separately.
Organiser — Social Innovation Hub. Production — content studio Ozge media.

Work step by step. After step 4 you must stop and show me the edit decision list
for approval — do not go further without my "ok".

SOURCES
  CAM_A — wide shot, both people in frame
  CAM_B — close-up of the speaker (guest)
  CAM_C — close-up of the host (when asking a question)
  AUDIO — lavalier mics / recorder (if separate)
If the file structure is different — first show me what you found and ask
which file is which camera. Do not guess.

STEP 1. INVENTORY
Run ffprobe on every file. Output a table: file, duration, resolution,
fps, codec, bitrate, audio track present, start timecode. Name any problems right away.

STEP 2. SYNC
Sync the cameras by waveform (cross-correlation). Output a table of offsets
in seconds and frames relative to CAM_A. Master audio — the separate recorder if there is one;
otherwise the camera with the cleanest sound (explain the choice).

STEP 3. TRANSCRIPT
Transcribe the master audio with faster-whisper, with word timestamps.
Label the lines HOST / SPEAKER. Where unsure — mark "?" and do not invent.

STEP 4. EDIT DECISION LIST ← the main deliverable
| # | In | Out | Dur. | Camera | Shot | Who speaks | Line (start) | Note |
Rules: question — CAM_C, answer — CAM_B, reactions and topic changes — CAM_A.
Cut only on a pause or a breath, never mid-word. Start and end — wide shot.
Separately: filler words and slips, pauses > 1.2 s, repeated takes (keep the best, explain why).
STOP. Show the edit decision list and wait for confirmation.

STEP 5. NAME TITLES — data only from speakers.json, invent nothing.
STEP 6. COLD OPEN (reference — The Diary Of A CEO): 8 candidate trigger quotes
(a number, a conflict with conventional wisdom, a personal admission, an unexpected claim, a short conclusion;
no longer than 12 words), typography appearing word by word in time with speech, 25–40 s.
STEP 7. END CARD — fade out, studio logo, "made with the support of" line in Kazakh, music.
STEP 8. OUTPUT — 1920×1080, H.264 CRF 18, AAC 192 kbps, EBU R128 −16 LUFS;
edit decision list (md + csv), cuts.json, transcript.srt, cold-open and end-card plans, README.

WORKING RULES
- All texts in Russian.
- Do not invent names, job titles, quotes or timecodes. If you don't know — ask.
- If a tool is missing — say what you are installing first, then install it.
- After each step, briefly: what you did, what came out, what's next.
```

The full prompt (font sizes, lower-third animation, a second-by-second end card) is kept by the team. This is a shortened version that shows how the task is set for the agent.

## How the agent handled revisions

After each version of the video the client sent comments in plain text (often dictated by voice). The agent:

1. turned the comment into a measurable rule (see [editing_rules.md](editing_rules.md));
2. added a detector where needed: e.g. "I'm reading from my notes" → eyelid opening on the close-up;
3. built the rule into `shots.py` and added the check to the report;
4. re-rendered only the pieces that changed and showed frames at the key moments.
