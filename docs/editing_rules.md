# Editing rules: where they came from

🇷🇺 [Русская версия](editing_rules.ru.md)

Each rule is a real comment from the client on a version of the interview, turned by the agent into a condition it can check.

| Version | Client comment (close to verbatim) | Agent rule | Where in code |
|---|---|---|---|
| v1 → v2 | "Remove the pauses, the uh, um, err throughout the video" | Pauses > 0.4 s → ~0.25 s; steady voicing ≥ 0.3 s (hesitation) → 0.2 s | `edit.py`, `hesitations.py` |
| v1 → v2 | "Wrong repetitions have to go too" | The agent reads the verbatim transcript and marks false starts and repetitions; the script checks the text at every cut | `project.json → edits`, `edit.py` |
| v1 → v2 | "Choose the camera by the speaker's gaze — he should be looking into the shot, not past it" | Head turn + iris position on every camera (MediaPipe) | `gaze.py` |
| v1 → v2 | "The cold open should be dynamic, with music; the title card not on black but on event footage" | Short transitions between quotes, title over event footage, live *küy* (dombra music) recorded at the summit | `graphics.py`, `render.py` |
| v2 → v3 | "Start with the quote with the number, then the conflict quote" | Quote order is set in `triggers_order` | `project.json` |
| v2 → v3 | "When I introduce the guest I speak to the centre camera — the introduction should be on the centre camera" | The host's introduction runs entirely on the wide shot | `shots.py` |
| v2 → v3 | "The *körpe* should only be in the wide shot; speakers in close-up, without the *körpe*" | Medium shots cropped from the wide camera are banned; the host's close-up is cropped to exclude the decor | `shots.py`, `CROP["C"]` |
| v2 → v3 | "The ending shouldn't be black — blue background, the hub's line and Ozge media" | Dissolve to blue, logos | `graphics.py → render_outro` |
| v3 → v4 | "Take the music from the screen recording; between quotes — a whoosh, not a black insert" | Transition + synthesised whoosh, client's music | `render.py`, `sfx.py` |
| v3 → v4 | "When I'm reading the questions, my eyes must not be in the wide shot — I'm always listening to the guest" | Wide shot is banned if the host is reading (eyelid opening < 0.30) for > 10 % of the shot | `gaze.py eyes`, `shots.py → reading_frac` |
| v3 → v4 | "Sharp close–wide–close transitions — that's not right, everything should be smooth" | No punch-ins; every cut is a 0.2–0.3 s dissolve; fewer wide shots | `render.py` |
| v3 → v4 | "At the end the guest is talking but the host is on screen" | A close-up never runs across a change of speaker; checked in the report | `shots.py` |
| v3 → v4 | "The hub's line bigger, Ozge media smaller, the hub's logo on top" | End-card layout | `graphics.py` |
| v4 → v5 | "The zoom transitions are ugly — make the trigger titles crisp, don't smear them" | Hard cuts between quotes (`TD = 0`); the whoosh carries the energy instead of a zoom | `render.py` |

## Checks `shots.py` prints after every build

- close-up of the wrong speaker for more than 1 s — must be empty;
- wide shots where the host is reading for more than 15 % of the time — must be empty;
- shot length: minimum, median, maximum;
- number of camera changes and cuts inside shots.
