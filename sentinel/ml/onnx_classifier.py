"""OnnxActionClassifier: the learned action model at inference time.

Implements the same `ActionClassifier` protocol as the kinematic stand-in
(sentinel/edge/pipeline/action.py), so the orchestrator uses a trained model
by construction — `EdgePipeline(action=OnnxActionClassifier(path, window_size))`
— with no pipeline changes. Runs on onnxruntime only (no torch on the edge).
"""

from __future__ import annotations

import numpy as np

from sentinel.edge.pipeline.action import ActionScore
from sentinel.edge.pipeline.types import PoseSample

from .features import window_to_features


class OnnxActionClassifier:
    def __init__(self, model_path: str, window_size: int, min_window: int = 8):
        try:
            import onnxruntime as ort
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("OnnxActionClassifier requires onnxruntime: pip install '.[ml]'") from e
        self._sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self._input = self._sess.get_inputs()[0].name
        self.window_size = window_size
        self.min_window = min_window

    def score_window(self, samples: list[PoseSample]) -> ActionScore | None:
        if len(samples) < self.min_window:
            return None
        feats = window_to_features(samples, self.window_size)[None, ...]  # [1, T, F]
        prob = self._sess.run(None, {self._input: feats.astype(np.float32)})[0]
        concealment_prob = float(prob[0, 1])  # class 1 = concealment
        return ActionScore(
            track_id=samples[0].track_id,
            score=round(concealment_prob, 4),
            window_start_ts=samples[0].ts,
            window_end_ts=samples[-1].ts,
            features={"model": 1.0, "concealment_prob": round(concealment_prob, 4)},
        )
