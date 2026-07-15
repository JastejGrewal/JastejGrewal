"""Synthetic labeled dataset of skeleton windows for the action model.

Phase 0 bootstraps from synthetic data (blueprint §4.5): we script the
concealment signature (reach → stow at hip → dwell) as the positive class and a
spread of innocuous motions as negatives, then apply heavy domain randomization
(position, scale, timing, per-keypoint noise) so the model learns gesture shape
rather than the exact synthetic geometry. Swapping in real UCF-Crime / staged
footage later is a matter of replacing this generator — the featurization,
model, and training loop are unchanged.

Label convention: 1 = concealment gesture, 0 = innocuous. Employee restocking
has the *same* kinematics as concealment, so it is a POSITIVE here — the rule
engine suppresses employees downstream (§3.4); the action model only judges the
gesture.
"""

from __future__ import annotations

import numpy as np

from sentinel.edge.pipeline.types import Keypoint, N_KEYPOINTS, PoseSample

from .features import window_to_features


def _person(cx: float, cy: float, s: float, right_wrist: tuple[float, float]) -> list[tuple[float, float]]:
    kp = [(0.0, 0.0)] * N_KEYPOINTS
    kp[Keypoint.LEFT_SHOULDER] = (cx - 0.03 * s, cy - 0.06 * s)
    kp[Keypoint.RIGHT_SHOULDER] = (cx + 0.03 * s, cy - 0.06 * s)
    kp[Keypoint.LEFT_WRIST] = (cx - 0.04 * s, cy)
    kp[Keypoint.RIGHT_WRIST] = right_wrist
    kp[Keypoint.LEFT_HIP] = (cx - 0.02 * s, cy + 0.04 * s)
    kp[Keypoint.RIGHT_HIP] = (cx + 0.02 * s, cy + 0.04 * s)
    return kp


def _wrist_trajectory(kind: str, t: float, cx: float, cy: float, s: float, rng) -> tuple[float, float]:
    """Right-wrist position at phase t in [0,1] for a given gesture kind."""
    neutral = (cx + 0.04 * s, cy)
    reach_out = (cx + 0.04 * s + 0.20 * s, cy - 0.02 * s)
    hip = (cx + 0.02 * s, cy + 0.04 * s)  # stow target

    if kind == "conceal":
        # reach for the first ~40%, then stow at hip and dwell.
        if t < 0.4:
            a = t / 0.4
            return (neutral[0] + a * (reach_out[0] - neutral[0]),
                    neutral[1] + a * (reach_out[1] - neutral[1]))
        return (hip[0] + rng.normal(0, 0.004 * s), hip[1] + rng.normal(0, 0.004 * s))
    if kind == "browse":
        # reach out, then return to neutral carry (never near hip).
        a = np.sin(t * np.pi)  # 0 -> 1 -> 0
        return (neutral[0] + a * (reach_out[0] - neutral[0]),
                neutral[1] + a * (reach_out[1] - neutral[1]))
    if kind == "idle":
        return (neutral[0] + rng.normal(0, 0.006 * s), neutral[1] + rng.normal(0, 0.006 * s))
    if kind == "reach_return":
        # reach up (e.g. top shelf) and back — high extent, no hip dwell.
        a = np.sin(t * np.pi)
        return (neutral[0] + a * 0.12 * s, neutral[1] - a * 0.18 * s)
    raise ValueError(kind)


_POSITIVE = ("conceal",)
_NEGATIVE = ("browse", "idle", "reach_return")


def _make_window(kind: str, window_size: int, rng, noise: float = 0.006) -> list[PoseSample]:
    cx = rng.uniform(0.2, 0.8)
    cy = rng.uniform(0.4, 0.6)
    s = rng.uniform(0.7, 1.4)          # apparent size
    phase0 = rng.uniform(0.0, 0.3)     # where in the gesture the window starts
    span = rng.uniform(0.7, 1.0)
    samples = []
    for i in range(window_size):
        t = min(1.0, phase0 + span * i / max(1, window_size - 1))
        wrist = _wrist_trajectory(kind, t, cx, cy, s, rng)
        kp = _person(cx, cy, s, wrist)
        # per-keypoint sensor noise
        kp = [(x + rng.normal(0, noise * s), y + rng.normal(0, noise * s)) for (x, y) in kp]
        samples.append(PoseSample(track_id=0, ts=i / 10.0, keypoints=kp))
    return samples


def generate_dataset(
    n_per_class: int, window_size: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return (X [N, T, F] float32, y [N] int64), balanced across classes."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n_per_class):
        pos_kind = rng.choice(_POSITIVE)
        X.append(window_to_features(_make_window(pos_kind, window_size, rng), window_size))
        y.append(1)
        neg_kind = rng.choice(_NEGATIVE)
        X.append(window_to_features(_make_window(neg_kind, window_size, rng), window_size))
        y.append(0)
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int64)


def golden_set(window_size: int, n_per_class: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """The frozen evaluation set (blueprint §4.2).

    Built from a FIXED seed and never touched by the feedback loop, so a
    retrained model must beat baseline on stable, uncontaminated data — the
    primary guard against the loop grading its own homework.
    """
    return generate_dataset(n_per_class=n_per_class, window_size=window_size, seed=20240601)
