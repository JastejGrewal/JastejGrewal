"""Train the initial (Phase 0) action model and register it as production.

    python -m sentinel.ml.train_cli --registry ./model_registry

Trains on the synthetic dataset, evaluates on the frozen golden set, registers
the version with lineage, and (if it clears the absolute accuracy floor)
promotes it to production so edge boxes can pull it.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from .dataset import generate_dataset, golden_set
from .registry import ModelRegistry, evaluate_onnx, golden_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train + register the action model")
    parser.add_argument("--registry", default="./model_registry")
    parser.add_argument("--window-size", type=int, default=20)
    parser.add_argument("--per-class", type=int, default=600)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    from .model import export_onnx, train_model

    X, y = generate_dataset(args.per_class, args.window_size, seed=args.seed)
    model, report = train_model(X, y, args.window_size, epochs=args.epochs, seed=args.seed)
    print(f"trained: val_accuracy={report.val_accuracy:.3f} train_loss={report.train_loss:.4f}")

    Xg, yg = golden_set(args.window_size)
    registry = ModelRegistry(args.registry)
    with tempfile.TemporaryDirectory() as tmp:
        onnx_path = str(Path(tmp) / "model.onnx")
        export_onnx(model, args.window_size, onnx_path)
        metrics = evaluate_onnx(onnx_path, Xg, yg)
        print(f"golden-set metrics: {metrics.to_dict()}")

        gate = golden_gate(metrics, baseline=None)
        version = registry.register(
            onnx_path, metrics,
            lineage={"n_synthetic": len(X), "synthetic_seed": args.seed,
                     "val_accuracy": report.val_accuracy, "parent": None},
        )
        print(f"registered {version}")
        if gate.passed:
            registry.promote(version)
            print(f"promoted {version} to production")
        else:
            print(f"NOT promoted: {gate.reasons}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
