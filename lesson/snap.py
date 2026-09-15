"""Ручные вырезки: из грубых границ по словам → точные по уровню звука.
a — конец последнего оставляемого слова, b — начало следующего оставляемого.
Режем внутри: от первой тишины после a до последней тишины перед b,
оставляя по KEEP/2 дыхания с каждой стороны.

    .venv/bin/python tools/snap.py 122.54 126.74"""
import sys, math, wave, array, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
w = wave.open(str(ROOT / 'work/detect.wav')); SR = w.getframerate()
pcm = array.array('h'); pcm.frombytes(w.readframes(w.getnframes()))
def db(t0, t1):
    s = pcm[int(t0*SR):int(t1*SR)]
    if not s: return -99
    r = math.sqrt(sum(x*x for x in s)/len(s)); return 20*math.log10(r/32768) if r else -99
# уровень речи — из вывода cuts.py («при речи -19.3»), под каждый урок свой
SPEECH = -19.3; THR = SPEECH - 20; WIN = 0.02; KEEP = 0.34
def snap(a, b):
    # вперёд от a: первое окно тишины, после которого 3 окна подряд тихие
    t = a - 0.10; qa = None
    while t < a + 0.8:
        if all(db(t+i*WIN, t+(i+1)*WIN) < THR for i in range(4)): qa = t; break
        t += WIN
    t = b + 0.10; qb = None
    while t > b - 0.8:
        if all(db(t-(i+1)*WIN, t-i*WIN) < THR for i in range(4)): qb = t; break
        t -= WIN
    return qa, qb
def prof(t0, t1):
    out=[]; t=t0
    while t<t1:
        d=db(t,t+0.04); out.append('#' if d>=SPEECH-6 else ('+' if d>=THR else '.')); t+=0.04
    return ''.join(out)
if __name__ == '__main__':
    a, b = float(sys.argv[1]), float(sys.argv[2])
    qa, qb = snap(a, b)
    ca = (qa + KEEP/2) if qa is not None else None
    cb = (qb - KEEP/2) if qb is not None else None
    print(f"{a:.2f}->{b:.2f}  тишина после a: {qa}  до b: {qb}  → вырезка {ca and round(ca,2)} – {cb and round(cb,2)}")
    print("  ", prof(a-0.6, a+0.6), "|", prof(b-0.6, b+0.6))
