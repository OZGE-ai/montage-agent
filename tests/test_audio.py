# -*- coding: utf-8 -*-
"""Проверки звуковой части агента на синтетическом сигнале (без реальных записей).

    python -m pytest tests/ -q
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "interview"))
from sync import offset                                     # noqa: E402
from hesitations import SR as HSR, detect_runs, hesitation_candidates   # noqa: E402

rng = np.random.default_rng(0)


def speechlike(seconds, sr, seed=1):
    """Шумоподобный сигнал со слоговой модуляцией ~5 Гц — достаточно «уникальный» для корреляции."""
    r = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 5.1 * t + r.uniform(0, 6)) ** 2
    return (r.standard_normal(len(t)) * env).astype(np.float32)


@pytest.mark.parametrize("true_offset", [7.928, -9.094, 0.0, 2.5])
def test_camera_offset_is_found(true_offset):
    sr = 8000
    ref = speechlike(120, sr)                                # «камера A»
    shift = int(round(true_offset * sr))
    if shift >= 0:                                           # камера включена раньше: в её файле тот же звук позже
        tgt = np.concatenate([speechlike(true_offset, sr, seed=7)[:shift], ref])
    else:
        tgt = ref[-shift:]
    tgt = tgt + 0.3 * rng.standard_normal(len(tgt)).astype(np.float32)   # у второй камеры свой шум
    found, quality = offset(ref, tgt, 40, 70, sr=sr)
    assert abs(found - true_offset) < 1.0 / sr * 2           # точность — пара сэмплов
    assert quality > 5


def vowel(seconds, f0=180.0, jitter=0.0, sr=HSR):
    """Гласный звук: гармоники основного тона; jitter — насколько «гуляет» тон (живая речь)."""
    t = np.arange(int(seconds * sr)) / sr
    f = f0 * (1 + jitter * np.sin(2 * np.pi * 6 * t))
    ph = 2 * np.pi * np.cumsum(f) / sr
    return sum(np.sin(k * ph) / k for k in range(1, 8)).astype(np.float32) * 0.2


def test_steady_hesitation_is_detected_and_lively_speech_is_not():
    sr = HSR
    gap = np.zeros(int(0.3 * sr), np.float32)
    # ровное «э-э-э» 0,6 с → должно попасть в кандидаты
    uh = vowel(0.6)
    # «живая речь»: короткие слоги с меняющимся тоном и паузами между ними
    syllables = np.concatenate([np.concatenate([vowel(0.12, f0=150 + 40 * np.sin(i), jitter=0.12), np.zeros(int(0.05 * sr), np.float32)]) for i in range(12)])
    noise = 0.002 * rng.standard_normal(int(0.5 * sr)).astype(np.float32)
    signal = np.concatenate([noise, syllables, gap, uh, gap, syllables, noise])
    runs, p25 = detect_runs(signal)
    uh_start = (len(noise) + len(syllables) + len(gap)) / sr
    cands = hesitation_candidates(runs, max(p25, 1e-3) * 1.5)
    assert any(abs(c["t0"] - uh_start) < 0.1 and c["d"] >= 0.5 for c in cands), (cands, runs)
    assert all(c["d"] >= 0.30 for c in cands)
