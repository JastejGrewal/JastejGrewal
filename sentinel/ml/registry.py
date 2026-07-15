"""Model registry, golden-set evaluation, and gated promotion (blueprint §4.2).

A file-backed stand-in for MLflow: versioned ONNX artifacts + a JSON index with
metrics and lineage, plus a `production` pointer. Promotion is GATED — a
candidate must beat the incumbent on the frozen golden set and not regress the
false-positive rate — the primary defense against the feedback loop drifting.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class EvalMetrics:
    accuracy: float
    precision: float
    recall: float
    false_positive_rate: float
    n: int

    def to_dict(self) -> dict:
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "false_positive_rate": self.false_positive_rate,
            "n": self.n,
        }


def evaluate_onnx(model_path: str, X: np.ndarray, y: np.ndarray, threshold: float = 0.5) -> EvalMetrics:
    """Evaluate an ONNX action model on labeled windows."""
    import onnxruntime as ort

    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    probs = sess.run(None, {name: X.astype(np.float32)})[0][:, 1]
    pred = (probs >= threshold).astype(np.int64)

    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    acc = (tp + tn) / max(1, len(y))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    fpr = fp / max(1, fp + tn)
    return EvalMetrics(round(acc, 4), round(precision, 4), round(recall, 4), round(fpr, 4), len(y))


@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def golden_gate(
    candidate: EvalMetrics,
    baseline: EvalMetrics | None,
    min_accuracy: float = 0.9,
    max_fpr_increase: float = 0.02,
) -> GateResult:
    """Decide whether a candidate may be promoted.

    - It must clear an absolute accuracy floor (a model worse than this never
      ships regardless of the incumbent).
    - Against an existing baseline it must not lose accuracy and must not
      increase the false-positive rate beyond tolerance (wrongful-accusation
      risk, blueprint §5/§10).
    """
    reasons: list[str] = []
    if candidate.accuracy < min_accuracy:
        reasons.append(f"accuracy {candidate.accuracy} below floor {min_accuracy}")
    if baseline is not None:
        if candidate.accuracy < baseline.accuracy:
            reasons.append(
                f"accuracy {candidate.accuracy} < baseline {baseline.accuracy}"
            )
        if candidate.false_positive_rate > baseline.false_positive_rate + max_fpr_increase:
            reasons.append(
                f"FPR {candidate.false_positive_rate} exceeds baseline "
                f"{baseline.false_positive_rate} + {max_fpr_increase}"
            )
    return GateResult(passed=not reasons, reasons=reasons)


class ModelRegistry:
    def __init__(self, root: str):
        self.root = Path(root)
        (self.root / "models").mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        if not self._index_path.exists():
            self._write_index({"versions": [], "production": None})

    def _read_index(self) -> dict:
        return json.loads(self._index_path.read_text())

    def _write_index(self, index: dict) -> None:
        self._index_path.write_text(json.dumps(index, indent=2))

    def register(
        self,
        onnx_path: str,
        metrics: EvalMetrics,
        lineage: dict,
        stage: str = "candidate",
        now: float | None = None,
    ) -> str:
        index = self._read_index()
        version = f"action-v{len(index['versions']) + 1}"
        dest = self.root / "models" / f"{version}.onnx"
        shutil.copyfile(onnx_path, dest)
        index["versions"].append(
            {
                "version": version,
                "path": str(dest),
                "stage": stage,
                "metrics": metrics.to_dict(),
                "lineage": lineage,
                "created_ts": now if now is not None else time.time(),
            }
        )
        self._write_index(index)
        return version

    def get(self, version: str) -> dict | None:
        for v in self._read_index()["versions"]:
            if v["version"] == version:
                return v
        return None

    def list_versions(self) -> list[dict]:
        return self._read_index()["versions"]

    def production_version(self) -> str | None:
        return self._read_index()["production"]

    def production(self) -> dict | None:
        prod = self.production_version()
        return self.get(prod) if prod else None

    def promote(self, version: str) -> None:
        index = self._read_index()
        if not any(v["version"] == version for v in index["versions"]):
            raise KeyError(version)
        for v in index["versions"]:
            if v["version"] == version:
                v["stage"] = "production"
            elif v["stage"] == "production":
                v["stage"] = "archived"
        index["production"] = version
        self._write_index(index)
