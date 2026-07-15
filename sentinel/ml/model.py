"""Trainable temporal action model + training + ONNX export.

A small 1D temporal CNN over the [T, F] skeleton feature window — the Phase 1
stand-in for a full ST-GCN/PoseC3D, sharing the exact interface so the heavy
model drops in later without touching the pipeline. Trains in seconds on CPU.

torch is an optional (training-time) dependency; inference uses the exported
ONNX via onnxruntime (see onnx_classifier.py), so edge boxes never need torch.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .features import N_FEATURES


def _require_torch():
    try:
        import torch
        import torch.nn as nn
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("training requires torch: pip install '.[ml]'") from e
    return torch, nn


def build_model(window_size: int, n_features: int = N_FEATURES):
    torch, nn = _require_torch()

    class TemporalActionNet(nn.Module):
        """Conv1d over time (channels = per-frame features) -> 2-class logits."""

        def __init__(self, n_features: int, window_size: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(n_features, 32, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(32, 32, kernel_size=3, padding=1),
                nn.ReLU(),
            )
            self.head = nn.Linear(32, 2)

        def forward(self, x):
            # x: [B, T, F] -> conv wants [B, F, T]
            x = x.transpose(1, 2)
            x = self.net(x)
            # Global average over time; mean exports to a clean ONNX ReduceMean
            # (AdaptiveAvgPool1d trips the opset version converter).
            x = x.mean(dim=-1)
            return self.head(x)

    return TemporalActionNet(n_features, window_size)


@dataclass
class TrainReport:
    epochs: int
    train_loss: float
    val_accuracy: float


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    window_size: int,
    epochs: int = 40,
    lr: float = 1e-3,
    val_split: float = 0.2,
    seed: int = 0,
):
    """Train and return (model, TrainReport). Deterministic given seed."""
    torch, nn = _require_torch()
    torch.manual_seed(seed)

    n = len(X)
    idx = np.random.default_rng(seed).permutation(n)
    n_val = int(n * val_split)
    val_idx, train_idx = idx[:n_val], idx[n_val:]

    Xt = torch.tensor(X)
    yt = torch.tensor(y)
    model = build_model(window_size)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()

    last_loss = 0.0
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        logits = model(Xt[train_idx])
        loss = loss_fn(logits, yt[train_idx])
        loss.backward()
        opt.step()
        last_loss = float(loss.item())

    model.eval()
    with torch.no_grad():
        preds = model(Xt[val_idx]).argmax(1)
        val_acc = float((preds == yt[val_idx]).float().mean().item()) if n_val else float("nan")

    return model, TrainReport(epochs=epochs, train_loss=last_loss, val_accuracy=val_acc)


def export_onnx(model, window_size: int, path: str) -> str:
    """Export the trained model to ONNX (softmax appended for calibrated probs)."""
    torch, nn = _require_torch()

    class WithSoftmax(nn.Module):
        def __init__(self, base):
            super().__init__()
            self.base = base
            self.softmax = nn.Softmax(dim=1)

        def forward(self, x):
            return self.softmax(self.base(x))

    wrapped = WithSoftmax(model).eval()
    dummy = torch.zeros(1, window_size, N_FEATURES, dtype=torch.float32)
    torch.onnx.export(
        wrapped,
        dummy,
        path,
        input_names=["window"],
        output_names=["prob"],
        dynamic_axes={"window": {0: "batch"}, "prob": {0: "batch"}},
        opset_version=17,
    )
    # The exporter may spill weights to an external `.data` sidecar; re-save with
    # everything inline so the single .onnx file is self-contained (the registry
    # copies only the .onnx, and edge boxes pull one file).
    import onnx

    onnx.save_model(onnx.load(path), path, save_as_external_data=False)
    _cleanup_external_data(path)
    return path


def _cleanup_external_data(path: str) -> None:
    import os

    sidecar = path + ".data"
    if os.path.exists(sidecar):
        os.remove(sidecar)
