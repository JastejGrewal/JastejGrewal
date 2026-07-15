"""Skeleton featurization: PoseSample window -> fixed [T, F] feature array.

Shared by dataset generation, training, and inference so the exact same
transform runs in all three (a classic source of train/serve skew otherwise).
Pure numpy — no torch — so the inference path (OnnxActionClassifier) needs only
onnxruntime, not the training stack.

Preprocessing is the standard skeleton-action recipe: make each frame
translation- and scale-invariant by centering on the shoulder midpoint and
scaling by shoulder width, so the model learns *gesture shape*, not where in
frame the person stands or how big they appear.
"""

from __future__ import annotations

import numpy as np

from sentinel.edge.pipeline.types import Keypoint, N_KEYPOINTS, PoseSample

# Feature layout per frame: N_KEYPOINTS normalized (x, y) pairs.
N_FEATURES = N_KEYPOINTS * 2
_MIN_SCALE = 1e-3


def _normalize_frame(keypoints: list[tuple[float, float]]) -> list[float]:
    ls = keypoints[Keypoint.LEFT_SHOULDER]
    rs = keypoints[Keypoint.RIGHT_SHOULDER]
    center = ((ls[0] + rs[0]) / 2.0, (ls[1] + rs[1]) / 2.0)
    scale = max(_MIN_SCALE, float(np.hypot(ls[0] - rs[0], ls[1] - rs[1])))
    out: list[float] = []
    for (x, y) in keypoints:
        out.append((x - center[0]) / scale)
        out.append((y - center[1]) / scale)
    return out


def window_to_features(samples: list[PoseSample], window_size: int) -> np.ndarray:
    """Map a pose window to a [window_size, N_FEATURES] float32 array.

    Windows shorter than window_size are left-padded by repeating the first
    frame; longer windows keep their most recent window_size frames.
    """
    if not samples:
        return np.zeros((window_size, N_FEATURES), dtype=np.float32)

    frames = [_normalize_frame(s.keypoints) for s in samples[-window_size:]]
    if len(frames) < window_size:
        frames = [frames[0]] * (window_size - len(frames)) + frames
    return np.asarray(frames, dtype=np.float32)
