# -*- coding: utf-8 -*-
"""Шаг 4. Куда смотрят люди (MediaPipe FaceMesh, 3 кадра/с).

    python interview/gaze.py close   # крупные B и C: поворот головы + зрачки → work/gaze_B.json, work/gaze_C.json
    python interview/gaze.py wide    # общий план A: гость и ведущая отдельно → work/gaze_A.json
    python interview/gaze.py eyes    # ведущая на C: раскрытие век (читает с листа?) → work/eyes_C.json

Как это используется в shots.py:
  * взгляд в центральную камеру (A) → общий план, это «контакт со зрителем»;
  * взгляд на собеседника → крупный план говорящего;
  * ведущая читает с листа (веки опущены, раскрытие < 0.30) → общий план в этот момент не ставим."""
import json, subprocess, sys
import numpy as np, mediapipe as mp
from common import CFG, OFF, P, cam_file

FPS = 3


def frames(cam, t0, t1, vf, W, H):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-hwaccel", "videotoolbox", "-ss", str(t0 + OFF[cam]), "-t", str(t1 - t0), "-i", cam_file(cam),
                          "-vf", f"fps={FPS},{vf}scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: return
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)


def mesh(): return mp.solutions.face_mesh.FaceMesh(static_image_mode=False, max_num_faces=2, refine_landmarks=True, min_detection_confidence=0.3)


def head(L):
    eo_r, eo_l, ei_r, ei_l, nose = L[33], L[263], L[133], L[362], L[1]
    mid = (eo_r + eo_l) / 2; ed = np.linalg.norm(eo_l[:2] - eo_r[:2])
    yaw = float((nose[0] - mid[0]) / ed); pitch = float((nose[1] - mid[1]) / ed)
    ir = (L[468][0] - eo_r[0]) / (ei_r[0] - eo_r[0] + 1e-6); il = (L[473][0] - ei_l[0]) / (eo_l[0] - ei_l[0] + 1e-6)
    return dict(yaw=round(yaw, 3), pitch=round(pitch, 3), iris=round(float((ir + il) / 2 - 0.5), 3), size=round(float(ed), 1), cx=round(float(mid[0]), 1))


def landmarks(face, W, H): return np.array([[q.x * W, q.y * H, q.z * W] for q in face.landmark])


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "close"
    t0, t1 = 40.0, CFG["body"]["end_before_stop"] + 3
    if mode == "close":
        for cam in ("B", "C"):
            fm, res = mesh(), []
            for i, img in enumerate(frames(cam, t0, t1, "", 960, 540)):
                r = fm.process(img); t = round(t0 + i / FPS, 2)
                if not r.multi_face_landmarks: res.append(dict(t=t, found=False)); continue
                best = max(r.multi_face_landmarks, key=lambda f: abs(f.landmark[33].x - f.landmark[263].x))
                res.append(dict(t=t, found=True, **head(landmarks(best, 960, 540))))
            json.dump(res, open(P + f"work/gaze_{cam}.json", "w")); print(cam, len(res))
    elif mode == "wide":
        out = {}
        for who, (x, y, w, h) in CFG["face_regions_wide"].items():
            fm, res = mesh(), []
            for i, img in enumerate(frames("A", t0, t1, f"crop={w}:{h}:{x}:{y},", 960, 540)):
                r = fm.process(img); t = round(t0 + i / FPS, 2)
                if not r.multi_face_landmarks: res.append(dict(t=t, found=False)); continue
                res.append(dict(t=t, found=True, **head(landmarks(r.multi_face_landmarks[0], 960, 540))))
            out[who] = res; print(who, len(res))
        json.dump(out, open(P + "work/gaze_A.json", "w"))
    elif mode == "eyes":
        x, y, w, h = CFG["face_region_host_close"]; W, H = 880, 720
        fm, res = mesh(), []
        for i, img in enumerate(frames("C", t0, t1, f"crop={w}:{h}:{x}:{y},", W, H)):
            r = fm.process(img); t = round(t0 + i / FPS, 2)
            if not r.multi_face_landmarks: res.append(dict(t=t, found=False)); continue
            L = landmarks(r.multi_face_landmarks[0], W, H)[:, :2]
            def eye(up, lo, a, b): return np.linalg.norm(L[up] - L[lo]) / np.linalg.norm(L[a] - L[b])
            res.append(dict(t=t, found=True, open=round(float((eye(159, 145, 33, 133) + eye(386, 374, 362, 263)) / 2), 3)))
        json.dump(res, open(P + "work/eyes_C.json", "w")); print("eyes", len(res))
