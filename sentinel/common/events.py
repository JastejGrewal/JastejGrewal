"""Shared event schemas: the contract between edge boxes and the cloud.

These are deliberately plain dataclasses (not pydantic) so the edge package
works with zero web-framework dependencies; the cloud layer validates its own
inbound payloads with pydantic models derived from the same field set.

Privacy invariant: nothing in these schemas may ever carry identity data —
no face crops, no embeddings usable for re-identification, no names. Alerts
carry kinematic evidence and a clip reference only.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum


class AlertTier(str, Enum):
    """Confidence tiers from blueprint §4.1 stage F."""

    LOG = "log"          # low confidence: telemetry only, training-data candidate
    SOFT = "soft"        # medium: non-intrusive notification
    ALERT = "alert"      # high: real-time push with clip


class FeedbackVerdict(str, Enum):
    """LP-staff disposition of an alert — the label source for §4.2."""

    CONFIRMED = "confirmed"
    FALSE_ALARM = "false_alarm"
    UNSURE = "unsure"


@dataclass
class ClipRef:
    """Reference to a pre/post-roll clip extracted from the edge ring buffer."""

    camera_id: str
    start_ts: float
    end_ts: float
    frame_count: int


@dataclass
class DetectionEvent:
    """One scored decision window for one tracked person.

    Every window is logged (not just alerts) so the active-learning selector
    can sample confident negatives too (blueprint §4.2).
    """

    store_id: str
    camera_id: str
    track_id: int
    tier: str
    fused_score: float
    action_score: float
    rule_flags: list[str] = field(default_factory=list)
    window_start_ts: float = 0.0
    window_end_ts: float = 0.0
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_ts: float = field(default_factory=time.time)
    clip: ClipRef | None = None
    # The skeleton window that produced this decision — keypoints only, no
    # identity. When an LP reviewer confirms/rejects the alert, this trace plus
    # their verdict becomes one labeled training example (blueprint §4.2). Shape:
    # [frame][keypoint] -> [x, y]. Optional so lightweight LOG telemetry can omit it.
    pose_trace: list[list[list[float]]] | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DetectionEvent":
        clip = d.get("clip")
        kwargs = {k: v for k, v in d.items() if k != "clip"}
        return cls(clip=ClipRef(**clip) if clip else None, **kwargs)
