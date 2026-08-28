"""Detecção de batidas e impactos da trilha escolhida (aula 013).

A aula diz: "nessa batida forte tem que acontecer alguma coisa". Este módulo transforma isso
em números para a etapa 7 — `bpm`, `beats` (a grade do ritmo) e `impacts` (as batidas fortes).

Sem librosa: o ffmpeg decodifica a trilha para PCM mono float32 e o numpy faz o resto
(envelope de energia → autocorrelação para o tempo → grade de batidas → picos). É determinístico:
a mesma trilha produz sempre o mesmo `beats.json`.
"""
from __future__ import annotations

import logging
import math
import tempfile
import time
from pathlib import Path

import numpy as np

from ..common import ffmpeg as ff

log = logging.getLogger("studio.music")

SR = 22050
HOP = 512
K = 1.5
MIN_GAP = 0.5          # segundos entre dois impactos ("algo acontece" não é a cada frame)
BPM_RANGE = (60, 200)
MIN_SECONDS = 4.0      # abaixo disso não há ritmo a estimar
SNAP_S = 0.06          # ±60 ms de ajuste da batida ao pico local
SMOOTH_TAPS = 5        # janelas suavizadas antes da autocorrelação (~116 ms)
TEMPO_CENTER = 120.0   # prior de tempo: bpm mais provável numa trilha de anúncio
TEMPO_SPREAD = 0.9     # largura do prior, em oitavas
DECODE_TIMEOUT = 120


def decode_pcm(path: str | Path, sr: int = SR) -> np.ndarray:
    """PCM mono float32 na taxa `sr`, via ffmpeg. RuntimeError se o ffmpeg não estiver disponível."""
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "track.f32le"
        ff.run(["-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", str(raw)], timeout=DECODE_TIMEOUT)
        y = np.fromfile(raw, dtype="<f4")
    return np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def onset_envelope(y: np.ndarray, sr: int = SR, hop: int = HOP) -> np.ndarray:
    """Energia RMS por janela → diferença positiva (onde a energia SOBE) → normalizado em [0, 1]."""
    n = int(len(y) // hop)
    if n < 2:
        return np.zeros(0, dtype=np.float32)
    rms = np.sqrt(np.mean(np.square(y[: n * hop].reshape(n, hop).astype(np.float64)), axis=1))
    env = np.maximum(0.0, np.diff(rms, prepend=rms[0]))
    peak = float(env.max())
    return (env / peak if peak > 0 else env).astype(np.float32)


def _smooth(env: np.ndarray, taps: int = SMOOTH_TAPS) -> np.ndarray:
    """Alarga os picos do envelope (~116 ms) antes da autocorrelação: sem isso, um período que não
    cai em número inteiro de janelas casa melhor com o DOBRO do período e o bpm sai pela metade."""
    if env.size < taps or taps < 2:
        return env.astype(np.float64)
    w = np.hanning(taps + 2)[1:-1]
    return np.convolve(env.astype(np.float64), w / w.sum(), mode="same")


def _tempo_prior(bpm: float) -> float:
    """Peso log-normal centrado em 120 bpm: desempata erro de oitava (60 vs 120) como o ouvido faz."""
    return float(np.exp(-0.5 * (np.log2(bpm / TEMPO_CENTER) / TEMPO_SPREAD) ** 2))


def estimate_bpm(env: np.ndarray, sr: int = SR, hop: int = HOP, bpm_range: tuple[int, int] = BPM_RANGE) -> float | None:
    """Tempo por autocorrelação do envelope, restrita a `bpm_range`. None quando não há periodicidade."""
    if env.size < 8:
        return None
    smooth = _smooth(env)
    x = smooth - smooth.mean()
    if not np.any(x):
        return None
    ac = np.correlate(x, x, mode="full")[env.size - 1:]
    if ac[0] <= 0:
        return None
    ac = ac / ac[0]
    fps = sr / hop
    lo = max(1, int(math.floor(60.0 / bpm_range[1] * fps)))
    hi = min(int(math.ceil(60.0 / bpm_range[0] * fps)), ac.size - 2)
    if hi <= lo:
        return None
    weighted = np.array([ac[lag] * _tempo_prior(60.0 * fps / lag) for lag in range(lo, hi + 1)])
    # pico local (proeminência) em vez do máximo bruto: evita casar com um lag vizinho por acaso
    peaks = [i for i in range(1, weighted.size - 1) if weighted[i] >= weighted[i - 1] and weighted[i] >= weighted[i + 1]]
    idx = max(peaks, key=lambda i: weighted[i]) if peaks else int(np.argmax(weighted))
    best = lo + idx
    if ac[best] <= 0:
        return None
    # interpolação parabólica: a resolução de um lag inteiro erraria o bpm em vários pontos
    a, b, c = float(ac[best - 1]), float(ac[best]), float(ac[best + 1])
    denom = a - 2 * b + c
    shift = float(np.clip(0.5 * (a - c) / denom, -0.5, 0.5)) if denom != 0 else 0.0
    bpm = 60.0 * fps / (best + shift)
    if not (bpm_range[0] <= bpm <= bpm_range[1]):
        return None
    return round(bpm, 1)


def track_beats(env: np.ndarray, bpm: float, sr: int = SR, hop: int = HOP, duration: float | None = None) -> list[float]:
    """Grade de período 60/bpm alinhada ao maior pico do primeiro período, cada batida ajustada ao pico local."""
    if env.size == 0 or not bpm:
        return []
    fps = sr / hop
    period = 60.0 / bpm * fps
    snap = max(1, int(round(SNAP_S * fps)))
    first = max(1, min(env.size, int(math.ceil(period))))
    start = int(np.argmax(env[:first]))
    limit = duration if duration else env.size / fps
    beats: list[float] = []
    i = 0
    while True:
        center = int(round(start + i * period))
        if center > env.size - 1:
            break
        lo, hi = max(0, center - snap), min(env.size, center + snap + 1)
        idx = lo + int(np.argmax(env[lo:hi]))
        t = round(idx * hop / sr, 3)
        if 0 <= t <= limit and (not beats or t > beats[-1]):
            beats.append(t)
        i += 1
    return beats


def pick_impacts(env: np.ndarray, beats: list[float], sr: int = SR, hop: int = HOP,
                 k: float = K, min_gap: float = MIN_GAP) -> list[float]:
    """Batidas cujo envelope passa de `mean + k*std` — o "algo acontece" da aula — espaçadas por `min_gap`."""
    if env.size == 0 or not beats:
        return []
    thr = float(env.mean()) + k * float(env.std())
    tol = hop / sr   # a grade tem resolução de um hop; não descartar por causa dela
    out: list[float] = []
    for t in beats:
        idx = min(env.size - 1, max(0, int(round(t * sr / hop))))
        if float(env[idx]) < thr:
            continue
        if out and t - out[-1] < min_gap - tol:
            continue
        out.append(t)
    return out


def analyze(path: str | Path, sr: int = SR, hop: int = HOP, k: float = K, min_gap: float = MIN_GAP,
            bpm_range: tuple[int, int] = BPM_RANGE) -> dict:
    """{'bpm', 'beats', 'impacts', 'duration', 'analysis_ms'} — o contrato lido pela etapa 7."""
    t0 = time.perf_counter()
    y = decode_pcm(path, sr)
    duration = round(len(y) / sr, 3)
    try:
        probed = float(ff.probe(path).get("duration") or 0)
        if probed > 0:
            duration = round(probed, 3)
    except RuntimeError:
        pass
    empty = {"bpm": None, "beats": [], "impacts": [], "duration": duration}
    if len(y) < MIN_SECONDS * sr or not np.any(y):
        log.info("beats skipped reason=track_too_short_or_silent duration=%s", duration)
        return {**empty, "analysis_ms": int((time.perf_counter() - t0) * 1000)}
    env = onset_envelope(y, sr, hop)
    bpm = estimate_bpm(env, sr, hop, bpm_range)
    if bpm is None:
        return {**empty, "analysis_ms": int((time.perf_counter() - t0) * 1000)}
    beats = track_beats(env, bpm, sr, hop, duration)
    impacts = pick_impacts(env, beats, sr, hop, k, min_gap)
    ms = int((time.perf_counter() - t0) * 1000)
    log.info("beats bpm=%s beats=%d impacts=%d ms=%d", bpm, len(beats), len(impacts), ms)
    return {"bpm": bpm, "beats": beats, "impacts": impacts, "duration": duration, "analysis_ms": ms}
