"""The edge pipeline orchestrator: stages A -> B -> C -> E -> F per frame.

Flow per frame (blueprint §4.1/§4.6):
  detect -> track -> pose -> (per-track sliding window) action score
  -> rules -> fusion/tier -> ring buffer clip on alert -> outbox enqueue.

Every scored window becomes a DetectionEvent (LOG tier included) because the
active-learning selector needs confident negatives too. Only ALERT-tier
events get a clip extracted.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from sentinel.common.events import AlertTier, DetectionEvent
from sentinel.edge.outbox import Outbox

from .action import ActionClassifier, KinematicConcealmentClassifier
from .detector import Detector, SyntheticDetector
from .fusion import FusionEngine
from .pose import PoseEstimator, SyntheticPose
from .ringbuffer import RingBuffer
from .rules import RuleEngine
from .types import Frame, PoseSample


@dataclass
class PipelineConfig:
    store_id: str = "store-001"
    camera_id: str = "cam-01"
    window_size: int = 20          # frames per action window (~2s at 10fps synthetic)
    window_stride: int = 5
    employee_actor_prefix: str = "employee"


@dataclass
class PipelineStats:
    frames: int = 0
    windows_scored: int = 0
    events_by_tier: dict[str, int] = field(default_factory=dict)


class EdgePipeline:
    def __init__(
        self,
        config: PipelineConfig | None = None,
        detector: Detector | None = None,
        pose: PoseEstimator | None = None,
        action: ActionClassifier | None = None,
        rules: RuleEngine | None = None,
        fusion: FusionEngine | None = None,
        outbox: Outbox | None = None,
    ):
        self.config = config or PipelineConfig()
        self.detector = detector or SyntheticDetector()
        self.pose = pose or SyntheticPose()
        self.action = action or KinematicConcealmentClassifier()
        self.rules = rules or RuleEngine()
        self.fusion = fusion or FusionEngine()
        self.outbox = outbox or Outbox()
        self.ring = RingBuffer(camera_id=self.config.camera_id)
        self.stats = PipelineStats()
        self._pose_windows: dict[int, deque[PoseSample]] = {}
        self._frames_since_score: dict[int, int] = {}
        # Synthetic ground truth: which actor each track id maps to (for the
        # employee-uniform rule cue in demo/tests; real ingest sets this from
        # a uniform/badge visual classifier, never identity).
        self._track_actor: dict[int, str] = {}
        from .tracker import IoUTracker

        self.tracker = IoUTracker()

    def process_frame(self, frame: Frame) -> list[DetectionEvent]:
        self.stats.frames += 1
        self.ring.push(frame)

        detections = self.detector.detect(frame)
        people = self.tracker.update(detections, frame.ts)
        samples = self.pose.estimate(frame, people)
        bbox_by_track = {p.track_id: p.detection.bbox for p in people}

        for person in people:
            actor = person.detection.actor_ref
            if actor is not None:
                self._track_actor[person.track_id] = actor.actor_id

        events: list[DetectionEvent] = []
        for sample in samples:
            window = self._pose_windows.setdefault(
                sample.track_id, deque(maxlen=self.config.window_size)
            )
            window.append(sample)
            self._frames_since_score[sample.track_id] = (
                self._frames_since_score.get(sample.track_id, 0) + 1
            )
            if (
                len(window) < self.config.window_size
                or self._frames_since_score[sample.track_id] < self.config.window_stride
            ):
                continue
            self._frames_since_score[sample.track_id] = 0

            action_score = self.action.score_window(list(window))
            if action_score is None:
                continue
            self.stats.windows_scored += 1

            actor_id = self._track_actor.get(sample.track_id, "")
            verdict = self.rules.evaluate(
                track_id=sample.track_id,
                bbox=bbox_by_track[sample.track_id],
                ts=frame.ts,
                is_employee=actor_id.startswith(self.config.employee_actor_prefix),
            )
            decision = self.fusion.decide(action_score, verdict)

            clip = None
            if decision.tier == AlertTier.ALERT:
                clip, _frames = self.ring.extract_clip(event_ts=frame.ts)

            event = DetectionEvent(
                store_id=self.config.store_id,
                camera_id=self.config.camera_id,
                track_id=decision.track_id,
                tier=decision.tier.value,
                fused_score=decision.fused_score,
                action_score=decision.action_score,
                rule_flags=decision.rule_flags,
                window_start_ts=decision.window_start_ts,
                window_end_ts=decision.window_end_ts,
                clip=clip,
            )
            self.outbox.enqueue(event)
            self.stats.events_by_tier[event.tier] = (
                self.stats.events_by_tier.get(event.tier, 0) + 1
            )
            events.append(event)
        return events
