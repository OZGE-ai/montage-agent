"""Подмешать музыку под заставку и финальную плашку в ГОТОВЫЙ ролик.

Нужно, когда пересобирать нечего или незачем: видеопоток копируется
как есть (-c:v copy), перекодируется только звук. Минута вместо часов,
и картинка не теряет качества на повторном сжатии.

    .venv/bin/python tools/add_music.py final/<slug>.mp4 [ещё файлы…]
    → рядом появится <slug>_music.mp4

Раскладка по времени — как в assemble.py: заставка INTRO секунд в начале,
плашка акимата в конце, её длительность читается из work/akimat.mov.
"""
import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MUSIC = ROOT / "docs/music.mp3"
INTRO = 3.5
XF = 0.50             # как в assemble.py
INTRO_TAIL = 1.2      # за столько музыка заставки уходит под речь
LEAD = 1.0            # за столько входит музыка под плашкой


def dur(p):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip())


def main():
    assert MUSIC.exists(), f"нет {MUSIC}"
    ak = dur(ROOT / "work/akimat.mov")
    for src in map(pathlib.Path, sys.argv[1:]):
        total = dur(src)
        out = src.with_name(src.stem + "_music" + src.suffix)
        i_len = INTRO + XF / 2 + INTRO_TAIL
        m_start, m_len = total - ak - LEAD, LEAD + ak
        fc = (f"[1:a]atrim=0:{i_len:.3f},asetpts=PTS-STARTPTS,"
              f"loudnorm=I=-22:TP=-2:LRA=11,afade=t=in:st=0:d=0.5,"
              f"afade=t=out:st={i_len - INTRO_TAIL:.3f}:d={INTRO_TAIL}[min];"
              f"[2:a]atrim=0:{m_len:.3f},asetpts=PTS-STARTPTS,"
              f"loudnorm=I=-20:TP=-2:LRA=11,afade=t=in:st=0:d=0.8,"
              f"afade=t=out:st={m_len - 1.0:.3f}:d=1.0,"
              f"adelay={int(m_start*1000)}|{int(m_start*1000)}[mout];"
              f"[0:a][min][mout]amix=inputs=3:duration=first:normalize=0[a]")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-v", "error",
                        "-i", str(src), "-i", str(MUSIC), "-i", str(MUSIC),
                        "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)],
                       check=True)
        print(f"{out.name}: музыка 0–{i_len:.2f} и {m_start:.2f}–{total:.2f} с")


if __name__ == "__main__":
    main()
