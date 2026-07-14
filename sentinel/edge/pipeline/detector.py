"""Stage A (detection half): pluggable person detectors.

The synthetic backend consumes ground-truth actors carried on the Frame and
is the default for tests/demo; the Ultralytics backend is import-guarded so
the core package never requires torch (blueprint: pluggable inference,
`pip install ".[ml]"` to enable real backends).
"""

from __future__ import annotations

from typing import Protocol

from .types import Detection, Frame


class Detector(Protocol):
    def detect(self, frame: Frame) -> list[Detection]: ...


class SyntheticDetector:
    """Emits detections straight from a synthetic frame's ground-truth actors.

    Stands in for the uniform/badge classifier by flagging actors whose id
    begins with `employee_prefix` as employees — the synthetic analogue of a
    visual uniform cue, keeping the identity-free contract (blueprint §3.4).
    """

    def __init__(self, confidence: float = 0.95, employee_prefix: str = "employee"):
        self.confidence = confidence
        self.employee_prefix = employee_prefix

    def detect(self, frame: Frame) -> list[Detection]:
        return [
            Detection(
                bbox=actor.bbox,
                confidence=self.confidence,
                is_employee=actor.actor_id.startswith(self.employee_prefix),
                actor_ref=actor,
            )
            for actor in frame.synthetic_actors
        ]


class UltralyticsDetector:
    """YOLO person detector (optional; requires `pip install ".[ml]"`)."""

    def __init__(self, model_path: str = "yolo11n.pt", conf: float = 0.4):
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise RuntimeError(
                "UltralyticsDetector requires the ml extra: pip install '.[ml]'"
            ) from e
        self._model = YOLO(model_path)
        self._conf = conf

    def detect(self, frame: Frame) -> list[Detection]:
        from .types import BBox

        if frame.image is None:
            return []
        results = self._model(frame.image, classes=[0], conf=self._conf, verbose=False)
        detections: list[Detection] = []
        for result in results:
            h, w = result.orig_shape
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        bbox=BBox(x=x1 / w, y=y1 / h, w=(x2 - x1) / w, h=(y2 - y1) / h),
                        confidence=float(box.conf[0]),
                    )
                )
        return detections
