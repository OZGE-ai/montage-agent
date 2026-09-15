# -*- coding: utf-8 -*-
"""Шаг 9. Сборка ролика: перебивка (фразы-триггеры переходят «зумом» со звуком «чух», под ними музыка) → заставка на видео
мероприятия под күй → интервью (все склейки — мягкое растворение, плашки ФИО) → финал на синем.

    python interview/render.py --plan     # только посчитать план
    python interview/render.py            # собрать output/final.mp4 (готовые куски в work/render/seg пропускаются)

1920×1080, 30 fps, H.264 CRF 18, AAC 192 kbps, громкость EBU R128 −16 LUFS. Видео кодируется кусками и склеивается
без перекодирования; звук собирается одной дорожкой и нормализуется в два прохода (перед этим — мягкий лимитер)."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np, soundfile as sf
from common import CFG, OFF, P, cam_file

RR = P + "work/render/"; SEG = RR + "seg/"; os.makedirs(SEG, exist_ok=True)
FPS = CFG.get("fps", 30); SR = 48000; SPF = SR // FPS
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-r", str(FPS), "-an", "-video_track_timescale", "30000"]
CROP = CFG["crops"]
TRIGGER_CROP = "crop=2226:1252:334:40,scale=1920:1080:flags=lanczos,setsar=1"   # приближение 15 % — гость левее, справа место под текст
D_CAM, D_JUMP, D_TR, D_TITLE = 9, 6, 10, 8                                       # длина растворений/переходов в кадрах
MUS = CFG["music"]; EV = CFG["event_clips"]


def nfr(path): return int(subprocess.check_output(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path]).strip())
def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode: raise RuntimeError(" ".join(cmd)[:500] + "\n" + p.stderr[-1500:])
def done(path): return os.path.exists(path) and os.path.getsize(path) > 0


# ── куски перебивки и заставки ──
TRIG = {t["id"]: t for t in CFG["triggers"]}
ORDER = CFG["triggers_order"]
INTRO = [dict(name=f"i{k}_{tid}", kind="trigger", clip=TRIG[tid]["clip"][0], layer=RR + f"layer_{tid}.mov") for k, tid in enumerate(ORDER)]
INTRO += [dict(name="i8_expo", kind="event", ev="expo", layer_off=0), dict(name="i9_kuy", kind="event", ev="kuy", layer_off=EV["expo"]["frames"])]
TRANS = ["zoomin"] * len(ORDER) + ["fade"]; TD = [D_TR] * len(ORDER) + [D_TITLE]


def encode_intro_part(j):
    out = SEG + j["name"] + ".mp4"
    if done(out): return
    if j["kind"] == "trigger":
        n = nfr(j["layer"])
        cmd = ["ffmpeg", "-v", "error", "-y", "-hwaccel", "videotoolbox", "-ss", f"{j['clip'] + OFF['B']:.4f}", "-i", cam_file("B"), "-i", j["layer"],
               "-filter_complex", f"[0:v]fps={FPS},{TRIGGER_CROP}[v];[v][1:v]overlay=0:0:eof_action=pass,format=yuv420p[o]", "-map", "[o]", "-frames:v", str(n)]
    else:
        e = EV[j["ev"]]; n = e["frames"]
        cmd = ["ffmpeg", "-v", "error", "-y", "-hwaccel", "videotoolbox", "-ss", f"{e['start']:.3f}", "-i", P + e["file"],
               "-ss", f"{j['layer_off'] / FPS:.4f}", "-i", RR + "layer_title.mov",
               "-filter_complex", f"[0:v]fps={FPS},scale=1920:1080:flags=lanczos,setsar=1,eq=saturation=1.05[v];[v][1:v]overlay=0:0:eof_action=pass,format=yuv420p[o]",
               "-map", "[o]", "-frames:v", str(n)]
    run(cmd + X264 + [out])


def intro_layout():
    lens = [nfr(SEG + j["name"] + ".mp4") for j in INTRO]
    starts = [0]
    for i in range(1, len(INTRO)): starts.append(starts[-1] + lens[i - 1] - TD[i - 1])
    return lens, starts, starts[-1] + lens[-1]


def encode_intro():
    for j in INTRO: encode_intro_part(j)
    lens, starts, total = intro_layout(); out = SEG + "000_intro.mp4"
    if done(out): return total
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for j in INTRO: cmd += ["-i", SEG + j["name"] + ".mp4"]
    fc, last, acc = "", "0:v", lens[0]
    for i in range(1, len(INTRO)):
        fc += f"[{last}][{i}:v]xfade=transition={TRANS[i-1]}:duration={TD[i-1]/FPS:.4f}:offset={(acc - TD[i-1]) / FPS:.4f}[x{i}];"
        last = f"x{i}"; acc += lens[i] - TD[i - 1]
    run(cmd + ["-filter_complex", fc + f"[{last}]format=yuv420p[o]", "-map", "[o]", "-frames:v", str(total)] + X264 + [out])
    return total


# ── интервью ──
E = json.load(open(P + "work/shots.json")); pieces, pst, shots = E["pieces"], E["starts"], E["shots"]
body = []
for k, (a, b, cam) in enumerate(shots):
    bounds = sorted(set([a, b] + [j for j in pst[1:] if a + 0.01 < j < b - 0.01]))
    for x, y in zip(bounds, bounds[1:]):
        pk = max(0, int(np.searchsorted(pst, x + 1e-6)) - 1)
        body.append(dict(cam=cam, p0=x, p1=y, src=pieces[pk][0] + (x - pst[pk])))
speakers = {s["role_in_video"]: s["slug"] for s in json.load(open(P + CFG["speakers"], encoding="utf-8"))}
lts = []
c_shot = next(s for s in shots if s[2] == "C" and s[1] - s[0] >= 6.5); lts.append((speakers["host"], c_shot[0] + 1.0))
b_first = next(s for s in shots if s[2] == "B" and s[1] - s[0] >= 7.0 and s[0] > E["intro_end"]); lts.append((speakers["guest"], b_first[0] + 2.5))
b_rep = min((s for s in shots if s[2] == "B" and s[1] - s[0] >= 8), key=lambda s: abs(s[0] - 540)); lts.append((speakers["guest"], b_rep[0] + 1.5))
jobs, prev = [], None
for i, s in enumerate(body):
    f0, f1 = int(round(s["p0"] * FPS)), int(round(s["p1"] * FPS))
    if f1 <= f0: continue
    srct = s["src"] + (f0 / FPS - s["p0"])
    if prev is None:     # растворение из заставки: видео ансамбля продолжается
        xin = dict(file=P + EV["kuy"]["file"], ss=EV["kuy"]["start"] + EV["kuy"]["frames"] / FPS, vf="scale=1920:1080:flags=lanczos,setsar=1", d=D_CAM)
    else:
        xin = dict(file=cam_file(prev["cam"]), ss=prev["srct"] + prev["n"] / FPS + OFF[prev["cam"]], vf=CROP[prev["cam"]], d=D_CAM if prev["cam"] != s["cam"] else D_JUMP)
    ov = [(P + f"output/graphics/lower_third_{slug}_plate.png", st - f0 / FPS) for slug, st in lts if st - 0.5 < f1 / FPS and st + 5.0 > f0 / FPS]
    prev = dict(name=f"1{i:03d}", cam=s["cam"], n=f1 - f0, srct=srct, xin=xin, lts=ov); jobs.append(prev)
jobs[-1]["to_blue"] = True


def encode(j):
    out = SEG + j["name"] + ".mp4"
    if done(out): return j["name"], "skip"
    x, d = j["xin"], j["xin"]["d"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-hwaccel", "videotoolbox", "-ss", f"{x['ss']:.4f}", "-i", x["file"],
           "-hwaccel", "videotoolbox", "-ss", f"{j['srct'] + OFF[j['cam']]:.4f}", "-i", cam_file(j["cam"])]
    fc = (f"[0:v]fps={FPS},{x['vf']},trim=end_frame={d},setpts=PTS-STARTPTS,settb=AVTB[p];"
          f"[1:v]fps={FPS},{CROP[j['cam']]},setpts=PTS-STARTPTS,settb=AVTB[c];[p][c]xfade=transition=fade:duration={d / FPS:.4f}:offset=0[v0]")
    last = "v0"
    for k, (png, st) in enumerate(j["lts"]):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", png]
        fi = f"fade=t=in:st={st:.3f}:d=0.4:alpha=1," if st > -0.4 else ""
        fc += (f";[{2 + k}:v]format=rgba,{fi}fade=t=out:st={st + 5 - 0.3:.3f}:d=0.3:alpha=1[l{k}]"
               f";[{last}][l{k}]overlay=x='-80*pow(1-min(max((t-({st:.3f}))/0.4\\,0)\\,1)\\,3)':y=0:eof_action=pass[v{k + 1}]")
        last = f"v{k + 1}"
    if j.get("to_blue"):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", RR + "outro_blue_bg.png"]
        fc += f";[{2 + len(j['lts'])}:v]format=rgba,fade=t=in:st={max(j['n'] / FPS - 1.0, 0):.3f}:d=1.0:alpha=1[bg];[{last}][bg]overlay=0:0:eof_action=pass[vb]"; last = "vb"
    tmp = out + ".part.mp4"
    run(cmd + ["-filter_complex", fc + f";[{last}]format=yuv420p[o]", "-map", "[o]", "-frames:v", str(j["n"])] + X264 + [tmp])
    if nfr(tmp) != j["n"]: raise RuntimeError(f"{j['name']}: неверное число кадров")
    os.rename(tmp, out); return j["name"], "ok"


def build_audio(intro_total):
    A = sf.read(RR + "A48.wav", dtype="float32")[0]
    lens, starts, _ = intro_layout(); title_f = starts[len(ORDER)]
    outro_f = nfr(RR + "layer_outro.mov"); body_f = sum(j["n"] for j in jobs)
    total = (intro_total + body_f + outro_f) * SPF
    speech = np.zeros(total, np.float32); music = np.zeros(total, np.float32)
    XF = int(D_TR / FPS * SR)
    for j, s0, ln in zip(INTRO, starts, lens):                       # фразы перебивки
        if j["kind"] != "trigger": continue
        n = ln * SPF; x = A[int(round(j["clip"] * SR)):int(round(j["clip"] * SR)) + n].copy()
        k = int(0.03 * SR); x[:k] *= np.linspace(0, 1, k); x[-XF:] *= np.linspace(1, 0, XF); speech[s0 * SPF:s0 * SPF + n] += x
    M = sf.read(P + MUS["intro"]["file"], dtype="float32")[0]; M = M.mean(1) if M.ndim > 1 else M
    t0 = title_f * SPF; m = M[int(MUS["intro"]["start"] * SR):int(MUS["intro"]["start"] * SR) + t0 + int(0.6 * SR)]
    env = np.ones(len(m), np.float32); env[-int(0.6 * SR):] = np.linspace(1, 0, int(0.6 * SR)); env[:960] = np.linspace(0, 1, 960)
    music[:len(m)] += m * env * MUS["intro"]["gain"]
    CH = sf.read(P + MUS["transition_sfx"], dtype="float32")[0]
    for i in range(1, len(ORDER) + 1):                                # «чух» в середине каждого перехода
        s0 = int((starts[i] + TD[i - 1] / 2) / FPS * SR) - int(0.45 * SR); music[s0:s0 + len(CH)] += CH * (1.4 if i == len(ORDER) else 1.1)
    K = sf.read(P + MUS["kuy"], dtype="float32")[0]; K = K.mean(1) if K.ndim > 1 else K
    kk = K[int((EV["kuy"]["start"] - (starts[-1] - title_f) / FPS) * SR):]; L = min(len(kk), total - t0)   # күй синхронно с видео ансамбля
    kenv = np.ones(L, np.float32) * MUS["kuy_gain"]; kenv[:int(0.25 * SR)] *= np.linspace(0, 1, int(0.25 * SR)); music[t0:t0 + L] += kk[:L] * kenv
    pos = intro_total * SPF; body0 = pos; prev_end = None; X2 = int(0.02 * SR)
    for j in jobs:                                                     # интервью: кроссфейд 20 мс на каждой склейке
        n = j["n"] * SPF; s = int(round(j["srct"] * SR))
        if prev_end is not None and abs(s - prev_end) > 2:
            x = A[s - X2:s + n].copy(); c = np.cos(np.linspace(0, np.pi / 2, X2)); si = np.sin(np.linspace(0, np.pi / 2, X2))
            speech[pos - X2:pos] = speech[pos - X2:pos] * c + x[:X2] * si; speech[pos:pos + n] = x[X2:X2 + n]
        else:
            speech[pos:pos + n] = A[s:s + n]
        if j.get("to_blue"): k = SR; speech[pos + n - k:pos + n] *= np.linspace(1, 0, k) ** 2
        prev_end = s + n; pos += n
    tl = int(0.9 * SR); kt = kk[body0 - t0:body0 - t0 + tl]
    music[body0:body0 + len(kt)] = kt * np.linspace(MUS["kuy_gain"] * 0.3, 0, len(kt)); music[body0 + tl:pos] = 0
    o0 = pos - SR; on = total - o0                                     # финал: күй входит на растворении в синий
    om = K[int(MUS["outro_start"] * SR):int(MUS["outro_start"] * SR) + on]; om = np.pad(om, (0, max(0, on - len(om))))
    oenv = np.ones(on, np.float32) * MUS["outro_gain"]; oenv[:SR] *= np.linspace(0, 1, SR); fo = int(1.8 * SR); oenv[-fo:] *= np.linspace(1, 0, fo) ** 1.5
    music[o0:o0 + on] = om[:on] * oenv
    mix = (speech + music) * 10 ** (-9 / 20)
    ax = np.abs(mix); over = ax > 0.6; mix[over] = np.sign(mix[over]) * (0.6 + 0.2 * np.tanh((ax[over] - 0.6) / 0.2))
    sf.write(RR + "timeline.wav", np.stack([mix, mix], 1), SR, subtype="FLOAT")
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", RR + "timeline.wav", "-af", "highpass=f=60,loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    js = json.loads(p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1])
    af = (f"highpass=f=60,loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}"
          f":measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true,aresample={SR}")
    run(["ffmpeg", "-v", "error", "-y", "-i", RR + "timeline.wav", "-af", af, "-c:a", "aac", "-b:a", "192k", RR + "audio.m4a"])
    return js["input_i"], js["input_tp"]


if __name__ == "__main__":
    print(f"интервью: {len(jobs)} кусков, {sum(j['n'] for j in jobs) / FPS:.1f} с; плашки {[(s, round(t, 1)) for s, t in lts]}", flush=True)
    if "--plan" in sys.argv: sys.exit()
    if not done(RR + "A48.wav"):
        run(["ffmpeg", "-v", "error", "-y", "-i", cam_file("A"), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_f32le", RR + "A48.wav"])
    intro_total = encode_intro(); print("перебивка + заставка:", intro_total, "кадров", flush=True)
    if not done(SEG + "200_outro.mp4"): run(["ffmpeg", "-v", "error", "-y", "-i", RR + "layer_outro.mov", "-vf", "format=yuv420p"] + X264 + [SEG + "200_outro.mp4"])
    with ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "2"))) as ex:
        for k, (name, st) in enumerate(ex.map(encode, jobs), 1):
            if st != "skip" and k % 20 == 0: print(f"[{k}/{len(jobs)}] {name}", flush=True)
    print("звук до нормализации (LUFS, dBTP):", build_audio(intro_total), flush=True)
    with open(RR + "concat.txt", "w") as f:
        for name in ["000_intro"] + [j["name"] for j in jobs] + ["200_outro"]: f.write(f"file '{SEG}{name}.mp4'\n")
    out = P + "output/final.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", RR + "concat.txt", "-i", RR + "audio.m4a",
         "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", out])
    print("ГОТОВО", out, flush=True)
