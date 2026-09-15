"""Шаги 6–8, финал. Заставка + тело урока + плашка акимата → final/<slug>.mp4 (slug — в lesson.json)

Видео: заставка (титульный слайд 3,5 с) → куски из work/seg/ через кросс-фейд
7 кадров → плашка акимата с кросс-фейдом 0,2 с из последнего кадра урока.
Звук: тишина под заставкой + дорожка из clean.mov + добивка тишиной под
хвостом «Рақмет» + музыка под плашкой.

Музыка входит за 1 секунду ДО плашки и гаснет ровно с затемнением: файл берётся
из docs/music.mp3, если его нет — плашка идёт без музыки и об этом говорится вслух.
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEG = ROOT / "work/seg"
FPS = 25
XF = 0.84    # переход между раскладками: 21 кадр. Было 12 —
             # заказчик просил плавнее переключение кадров,
             # заказчик просил плавнее, резких смен быть не должно
INTRO = 3.5          # заставка
AK_XF = 0.5          # кросс-фейд в плашку — тоже мягче (было 0,2)
MUSIC_LEAD = 1.0     # музыка входит за секунду до плашки
INTRO_MUSIC_TAIL = 1.2  # за столько музыка заставки уходит под речь
import json as _json
_L = _json.loads((ROOT / "lesson.json").read_text(encoding="utf-8"))
SLUG = _L["slug"]
OUT = ROOT / f"final/{SLUG}.mp4"


def dur(path):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip())


def main():
    segs = sorted(SEG.glob("*.mov"))
    assert segs, "нет кусков в work/seg — сначала tools/compose.py"
    lens = [dur(s) for s in segs]
    # у каждого куска по XF/2 запаса с обеих сторон, кроме краёв
    body = sum(lens) - XF * (len(segs) - 1)
    # Звук урока можно брать из мастера, а можно из отдельной дорожки
    # work/clean_audio.wav. Второй вариант нужен, когда на диске нет места
    # держать 4K-мастер (8+ ГБ) до конца сборки: после compose видео мастера
    # больше не требуется, а звук — требуется, и он весит ~130 МБ.
    clean_a_src = (ROOT / "work/clean_audio.wav" if (ROOT / "work/clean_audio.wav").exists()
                   else ROOT / "work/clean.mov")
    clean_a = dur(clean_a_src)
    ak = dur(ROOT / "work/akimat.mov")
    music = ROOT / "docs/music.mp3"

    # заставка: своя зелёная плашка серии (overlays/intro.png), а если её нет —
    # титульный слайд дека, как в уроке 02
    intro_img = ROOT / "overlays/intro.png"
    if not intro_img.exists():
        intro_img = ROOT / "slides/s01.png"
    ins = ["-loop", "1", "-framerate", str(FPS), "-t", f"{INTRO + XF/2:.3f}",
           "-i", str(intro_img)]
    for s in segs:
        ins += ["-i", str(s)]
    ins += ["-i", str(ROOT / "work/akimat.mov"), "-i", str(clean_a_src)]
    if music.exists():
        # один и тот же файл заводим дважды: под заставку и под плашку.
        # Так проще, чем asplit, и каждой врезке можно задать свой фейд.
        ins += ["-i", str(music), "-i", str(music)]

    n_intro, n_seg0, n_ak, n_clean = 0, 1, 1 + len(segs), 2 + len(segs)
    n_mus_in, n_mus_out = 3 + len(segs), 4 + len(segs)

    fc = []
    # заставка: титульный слайд с медленным наездом, из чёрного
    ni = round((INTRO + XF / 2) * FPS)
    fc.append(f"[{n_intro}:v]scale=3840:2160,setsar=1,"
              f"zoompan=z='1+0.04*on/{ni-1}':d=1:s=1920x1080:fps={FPS}:"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
              f"fade=t=in:st=0:d=0.5,settb=1/{FPS},format=yuv420p,setsar=1[intro];")

    # xfade требует одинаковую временную базу у обоих входов, иначе цепочка
    # разваливается на первом же стыке — приводим все куски к 1/25
    NORM = f"fps={FPS},settb=1/{FPS},format=yuv420p,setsar=1"
    for k in range(len(segs)):
        fc.append(f"[{n_seg0+k}:v]{NORM}[s{k}];")
    fc.append(f"[{n_ak}:v]{NORM}[akv];")

    cur, acc = "intro", INTRO
    for k in range(len(segs)):
        nxt = f"b{k}"
        fc.append(f"[{cur}][s{k}]xfade=transition=fade:duration={XF}:"
                  f"offset={acc - XF/2:.3f}[{nxt}];")
        acc += lens[k] - XF / 2 - (XF / 2 if k < len(segs) - 1 else 0)
        cur = nxt
    fc.append(f"[{cur}][akv]xfade=transition=fade:duration={AK_XF}:"
              f"offset={acc - AK_XF:.3f}[vout];")
    total = acc + ak - AK_XF

    # звук
    pad = max(0.0, acc - INTRO - clean_a)
    fc.append(f"[{n_clean}:a]adelay={int(INTRO*1000)}|{int(INTRO*1000)},"
              f"apad=pad_dur={pad + ak:.3f}[sp];")
    if music.exists():
        # ——— музыка под заставкой: звучит с первого кадра и уходит,
        # когда начинается речь, иначе она лезет под приветствие
        i_len = INTRO + XF / 2 + INTRO_MUSIC_TAIL
        fc.append(f"[{n_mus_in}:a]atrim=0:{i_len:.3f},asetpts=PTS-STARTPTS,"
                  f"loudnorm=I=-22:TP=-2:LRA=11,"
                  f"afade=t=in:st=0:d=0.5,"
                  f"afade=t=out:st={i_len - INTRO_MUSIC_TAIL:.3f}:"
                  f"d={INTRO_MUSIC_TAIL:.3f}[mus_in];")
        # ——— музыка под финальной плашкой
        m_start = acc - MUSIC_LEAD
        m_len = MUSIC_LEAD + ak
        fc.append(f"[{n_mus_out}:a]atrim=0:{m_len:.3f},asetpts=PTS-STARTPTS,"
                  f"loudnorm=I=-20:TP=-2:LRA=11,"
                  f"afade=t=in:st=0:d=0.8,"
                  f"afade=t=out:st={m_len - 1.0:.3f}:d=1.0,"
                  f"adelay={int(m_start*1000)}|{int(m_start*1000)}[mus_out];"
                  f"[sp][mus_in][mus_out]amix=inputs=3:duration=first:"
                  f"normalize=0[aout];")
        aout = "aout"
    else:
        aout = "sp"

    (ROOT / "work/filter_assemble.txt").write_text("".join(fc).rstrip(";"), encoding="utf-8")
    OUT.parent.mkdir(exist_ok=True)
    cmd = (["ffmpeg", "-y", "-hide_banner", "-v", "warning", "-stats"] + ins +
           ["-/filter_complex", str(ROOT / "work/filter_assemble.txt"),
            "-map", "[vout]", "-map", f"[{aout}]",
            "-c:v", "libx264", "-crf", "18", "-preset", "slow",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-t", f"{total:.3f}", str(OUT)])
    print(f"кусков: {len(segs)}, тело {body:.2f} с, итог {total:.2f} с "
          f"({total/60:.2f} мин)")
    if not music.exists():
        print("⚠ docs/music.mp3 нет — плашка идёт без музыки")
    subprocess.run(cmd, check=True)
    print("готово:", OUT)


if __name__ == "__main__":
    main()
