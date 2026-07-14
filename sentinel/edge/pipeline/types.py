"""Core pipeline datatypes shared by all stages.

Coordinate convention: normalized [0, 1] image coordinates, origin top-left.
Keypoints follow a minimal COCO-style subset — the kinematic classifier only
needs wrists, hips, and shoulders, so the synthetic backend emits exactly
those. Real backends (RTMPose etc.) map their output down to this set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Keypoint(IntEnum):
    LEFT_SHOULDER = 0
    RIGHT_SHOULDER = 1
    LEFT_WRIST = 2
    RIGHT_WRIST = 3
    LEFT_HIP = 4
    RIGHT_HIP = 5


N_KEYPOINTS = len(Keypoint)


@dataclass
class Frame:
    """One decoded frame. `image` is backend-opaque (ndarray for real video,
    None for synthetic scenarios that carry ground-truth actors instead)."""

    camera_id: str
    ts: float
    index: int
    image: object | None = None
    # Synthetic scenarios attach ground-truth actor states here; real ingest leaves it empty.
    synthetic_actors: list["SyntheticActor"] = field(default_factory=list)


@dataclass
class BBox:
    """Normalized xywh box."""

    x: float
    y: float
    w: float
    h: float

    def iou(self, other: "BBox") -> float:
        ax2, ay2 = self.x + self.w, self.y + self.h
        bx2, by2 = other.x + other.w, other.y + other.h
        ix = max(0.0, min(ax2, bx2) - max(self.x, other.x))
        iy = max(0.0, min(ay2, by2) - max(self.y, other.y))
        inter = ix * iy
        union = self.w * self.h + other.w * other.h - inter
        return inter / union if union > 0 else 0.0

    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)


@dataclass
class Detection:
    """Stage A output: one person detection in one frame."""

    bbox: BBox
    confidence: float
    # Carried through from synthetic ground truth so downstream synthetic
    # backends can look up the actor; never populated by real detectors.
    actor_ref: object | None = None


@dataclass
class TrackedPerson:
    """Stage A output after tracking: a detection with a stable track id."""

    track_id: int
    detection: Detection
    ts: float


@dataclass
class PoseSample:
    """Stage B output: keypoints for one tracked person in one frame.

    keypoints[k] = (x, y) normalized; index by `Keypoint`.
    """

    track_id: int
    ts: float
    keypoints: list[tuple[float, float]]

    def kp(self, k: Keypoint) -> tuple[float, float]:
        return self.keypoints[k]


@dataclass
class SyntheticActor:
    """Ground-truth actor state for synthetic scenarios (tests + demo)."""

    actor_id: str
    bbox: BBox
    keypoints: list[tuple[float, float]]
