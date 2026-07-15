"""Real perception backend: Ultralytics YOLO-pose (detection + pose in one net).

A single YOLO-pose model detects people AND regresses COCO-17 keypoints per
person, so it fills BOTH stage A (detector) and stage B (pose) — the cleanest
real-model path onto the existing pipeline. In production these stages split
again (YOLO-detect + RTMPose) for independent per-stage retraining (see
docs/architecture/detection-pipeline.md), but one model is the fastest way to
run the pipeline on real pixels.

Optional dependency: `pip install '.[ml]'` (ultralytics). Import-guarded so the
core package never requires torch.

COCO-17 -> Sentinel 6-keypoint mapping (see types.Keypoint):
  5 L-shoulder, 6 R-shoulder, 9 L-wrist, 10 R-wrist, 11 L-hip, 12 R-hip.
"""

from __future__ import annotations

from sentinel.edge.pipeline.types import (
    BBox,
    Detection,
    Frame,
    Keypoint,
    N_KEYPOINTS,
    PoseSample,
    TrackedPerson,
)

# COCO-17 index -> our Keypoint enum slot.
_COCO_TO_SENTINEL = {
    5: Keypoint.LEFT_SHOULDER,
    6: Keypoint.RIGHT_SHOULDER,
    9: Keypoint.LEFT_WRIST,
    10: Keypoint.RIGHT_WRIST,
    11: Keypoint.LEFT_HIP,
    12: Keypoint.RIGHT_HIP,
}


def map_coco17_to_sentinel(
    coco_xy: list[tuple[float, float]], width: int, height: int
) -> list[tuple[float, float]]:
    """Map a COCO-17 keypoint list (pixel coords) to our normalized 6-point set.

    Pure and weights-free so the mapping is unit-testable without loading a
    model. Missing/out-of-range COCO indices leave the slot at (0, 0).
    """
    kp: list[tuple[float, float]] = [(0.0, 0.0)] * N_KEYPOINTS
    for coco_idx, slot in _COCO_TO_SENTINEL.items():
        if coco_idx < len(coco_xy):
            px, py = coco_xy[coco_idx]
            kp[slot] = (px / width, py / height)
    return kp


class YoloPoseBackend:
    """Runs YOLO-pose once per frame; exposes detector + pose adapters.

    Because one inference yields both boxes and keypoints, we cache the last
    frame's result keyed by frame index so the Detector and PoseEstimator
    adapters don't run the net twice. The orchestrator calls detect() then
    estimate() on the same frame, so the cache hit rate is 100%.
    """

    def __init__(self, model_path: str = "yolo11n-pose.pt", conf: float = 0.4, imgsz: int = 640):
        try:
            from ultralytics import YOLO
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "YoloPoseBackend requires the ml extra: pip install '.[ml]'"
            ) from e
        self._model = YOLO(model_path)
        self._conf = conf
        self._imgsz = imgsz
        self._cache_index: int | None = None
        self._cache: list[tuple[Detection, list[tuple[float, float]]]] = []

    def _run(self, frame: Frame) -> list[tuple[Detection, list[tuple[float, float]]]]:
        if frame.index == self._cache_index and self._cache_index is not None:
            return self._cache
        results = []
        if frame.image is not None:
            h, w = frame.image.shape[:2]
            preds = self._model(frame.image, conf=self._conf, imgsz=self._imgsz, verbose=False)
            for pred in preds:
                boxes = pred.boxes
                kpts = pred.keypoints
                if boxes is None:
                    continue
                for i in range(len(boxes)):
                    x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                    det = Detection(
                        bbox=BBox(x=x1 / w, y=y1 / h, w=(x2 - x1) / w, h=(y2 - y1) / h),
                        confidence=float(boxes.conf[i]),
                    )
                    kp = [(0.0, 0.0)] * N_KEYPOINTS
                    if kpts is not None and kpts.xy is not None and i < len(kpts.xy):
                        coco = [tuple(p) for p in kpts.xy[i].tolist()]  # 17 x (x, y) px
                        kp = map_coco17_to_sentinel(coco, w, h)
                    results.append((det, kp))
        self._cache_index = frame.index
        self._cache = results
        return results

    # --- Detector adapter (stage A) ---
    def detect(self, frame: Frame) -> list[Detection]:
        return [det for det, _kp in self._run(frame)]

    # --- PoseEstimator adapter (stage B) ---
    def estimate(self, frame: Frame, people: list[TrackedPerson]) -> list[PoseSample]:
        results = self._run(frame)
        # Match each tracked person back to the detection it came from by best
        # bbox IoU (the tracker may have reordered / assigned ids).
        samples: list[PoseSample] = []
        for person in people:
            best_kp = None
            best_iou = 0.0
            for det, kp in results:
                iou = person.detection.bbox.iou(det.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_kp = kp
            if best_kp is not None:
                samples.append(PoseSample(track_id=person.track_id, ts=person.ts, keypoints=best_kp))
        return samples


class _DetectorView:
    def __init__(self, backend: YoloPoseBackend):
        self._backend = backend

    def detect(self, frame: Frame) -> list[Detection]:
        return self._backend.detect(frame)


class _PoseView:
    def __init__(self, backend: YoloPoseBackend):
        self._backend = backend

    def estimate(self, frame: Frame, people: list[TrackedPerson]) -> list[PoseSample]:
        return self._backend.estimate(frame, people)


def yolo_pose_stages(model_path: str = "yolo11n-pose.pt", conf: float = 0.4):
    """Return (detector, pose) adapters sharing one YOLO-pose backend."""
    backend = YoloPoseBackend(model_path=model_path, conf=conf)
    return _DetectorView(backend), _PoseView(backend)
