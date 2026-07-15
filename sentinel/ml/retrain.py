"""Retraining pipeline: feedback -> labeled data -> train -> golden gate.

Closes the loop (blueprint §4.2). Confirmed alerts and false alarms carry the
skeleton trace that produced them; each becomes one labeled window. We merge
that human-labeled production data with the synthetic base set (so early rounds
with little feedback still train a sane model), retrain, evaluate on the FROZEN
golden set, and gate promotion against the incumbent.

Guardrails enforced here (blueprint §4.2):
- only explicitly human-confirmed labels enter the set ('unsure' is dropped);
- the golden set is never sourced from feedback;
- a candidate is registered but only promoted if it clears the golden gate.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .dataset import generate_dataset, golden_set
from .features import window_to_features
from .registry import EvalMetrics, ModelRegistry, evaluate_onnx, golden_gate

_VERDICT_LABEL = {"confirmed": 1, "false_alarm": 0}  # 'unsure' intentionally absent


def labeled_windows_from_feedback(
    labeled_events: list[dict], window_size: int
) -> tuple[np.ndarray, np.ndarray]:
    """Turn feedback-labeled events (with pose_trace) into (X, y)."""
    from sentinel.edge.pipeline.types import PoseSample

    X, y = [], []
    for ev in labeled_events:
        label = _VERDICT_LABEL.get(ev.get("verdict"))
        trace = ev.get("pose_trace")
        if label is None or not trace:
            continue
        samples = [
            PoseSample(track_id=0, ts=i / 10.0, keypoints=[(p[0], p[1]) for p in frame])
            for i, frame in enumerate(trace)
        ]
        X.append(window_to_features(samples, window_size))
        y.append(label)
    if not X:
        return np.empty((0, window_size, window_to_features([], window_size).shape[1]), np.float32), np.empty((0,), np.int64)
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int64)


@dataclass
class RetrainReport:
    version: str | None
    promoted: bool
    candidate_metrics: dict
    baseline_metrics: dict | None
    gate_reasons: list[str]
    n_feedback: int
    n_synthetic: int
    val_accuracy: float


def retrain(
    store,
    registry: ModelRegistry,
    window_size: int,
    synthetic_per_class: int = 400,
    epochs: int = 80,
    seed: int = 0,
    auto_promote: bool = True,
) -> RetrainReport:
    """Run one retraining round and gate the result against the golden set."""
    from .model import export_onnx, train_model

    feedback_events = store.labeled_examples()
    Xf, yf = labeled_windows_from_feedback(feedback_events, window_size)
    Xs, ys = generate_dataset(synthetic_per_class, window_size, seed=seed)

    if len(Xf):
        X = np.concatenate([Xs, Xf], axis=0)
        y = np.concatenate([ys, yf], axis=0)
    else:
        X, y = Xs, ys

    model, train_report = train_model(X, y, window_size, epochs=epochs, seed=seed)

    Xg, yg = golden_set(window_size)
    with tempfile.TemporaryDirectory() as tmp:
        onnx_path = str(Path(tmp) / "candidate.onnx")
        export_onnx(model, window_size, onnx_path)
        candidate_metrics = evaluate_onnx(onnx_path, Xg, yg)

        prod = registry.production()
        baseline_metrics = (
            EvalMetrics(**{k: prod["metrics"][k] for k in
                           ("accuracy", "precision", "recall", "false_positive_rate", "n")})
            if prod else None
        )
        gate = golden_gate(candidate_metrics, baseline_metrics)

        version = registry.register(
            onnx_path,
            candidate_metrics,
            lineage={
                "n_feedback": int(len(Xf)),
                "n_synthetic": int(len(Xs)),
                "synthetic_seed": seed,
                "parent": registry.production_version(),
                "val_accuracy": train_report.val_accuracy,
            },
        )

    promoted = False
    if gate.passed and auto_promote:
        registry.promote(version)
        promoted = True

    return RetrainReport(
        version=version,
        promoted=promoted,
        candidate_metrics=candidate_metrics.to_dict(),
        baseline_metrics=baseline_metrics.to_dict() if baseline_metrics else None,
        gate_reasons=gate.reasons,
        n_feedback=int(len(Xf)),
        n_synthetic=int(len(Xs)),
        val_accuracy=train_report.val_accuracy,
    )
