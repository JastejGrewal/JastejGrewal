"""The edge pipeline orchestrator: stages A -> B -> C -> E -> F per frame.

Flow per frame (blueprint §4.1/§4.6):
  detect -> track -> pose -> (per-track sliding window) action score
  -> rules -> fusion/tier -> ring buffer clip on alert -> outbox enqueue.

Every scored window becomes a DetectionEvent (LOG tier included) because the
active-learning selector needs confident negatives too. Only ALERT-tier
events get a clip extracted, and that extraction is DEFERRED by post_roll
seconds so the clip actually contains post-event frames (see _pending_alerts).

Per-track state is released when the tracker ages a track out, so a 24/7
process does not leak one deque + several dict entries per shopper forever.
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
from .tracker import IoUTracker
from .types import Frame, PoseSample


@dataclass
class PipelineConfig:
    store_id: str = "store-001"
    camera_id: str = "cam-01"
    window_size: int = 20          # frames per action window (~2s at 10fps synthetic)
    window_stride: int = 5
    clip_pre_roll_s: float = 5.0
    clip_post_roll_s: float = 5.0


@dataclass
class _PendingAlert:
    """An ALERT awaiting enough post-roll frames before its clip is cut."""

    event: DetectionEvent
    event_ts: float
    ready_ts: float


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
        # Synthetic ground truth: which actor each track id maps to (demo/test
        # attribution only; pruned with the track so it can't leak). Employee
        # suppression does NOT depend on this — it reads detection.is_employee.
        self._track_actor: dict[int, str] = {}
        self._pending_alerts: list[_PendingAlert] = []
        self.tracker = IoUTracker()

    def _release_track(self, track_id: int) -> None:
        """Free all per-track state when the tracker ages a track out."""
        self._pose_windows.pop(track_id, None)
        self._frames_since_score.pop(track_id, None)
        self._track_actor.pop(track_id, None)
        self.rules.forget(track_id)
        self.fusion.forget(track_id)

    def _emit(self, event: DetectionEvent) -> None:
        self.outbox.enqueue(event)
        self.stats.events_by_tier[event.tier] = (
            self.stats.events_by_tier.get(event.tier, 0) + 1
        )

    def _drain_ready_clips(self, now_ts: float, force: bool = False) -> list[DetectionEvent]:
        """Attach clips and emit alerts whose post-roll window has filled."""
        ready: list[DetectionEvent] = []
        still_pending: list[_PendingAlert] = []
        for pending in self._pending_alerts:
            if force or now_ts >= pending.ready_ts:
                clip, _frames = self.ring.extract_clip(
                    event_ts=pending.event_ts,
                    pre_roll_s=self.config.clip_pre_roll_s,
                    post_roll_s=self.config.clip_post_roll_s,
                )
                pending.event.clip = clip
                self._emit(pending.event)
                ready.append(pending.event)
            else:
                still_pending.append(pending)
        self._pending_alerts = still_pending
        return ready

    def process_frame(self, frame: Frame) -> list[DetectionEvent]:
        self.stats.frames += 1
        self.ring.push(frame)

        detections = self.detector.detect(frame)
        people = self.tracker.update(detections, frame.ts)
        for dropped in self.tracker.dropped_ids:
            self._release_track(dropped)
        samples = self.pose.estimate(frame, people)
        bbox_by_track = {p.track_id: p.detection.bbox for p in people}
        employee_by_track = {p.track_id: p.detection.is_employee for p in people}

        for person in people:
            actor = person.detection.actor_ref
            if actor is not None:
                self._track_actor[person.track_id] = actor.actor_id

        events: list[DetectionEvent] = []
        for sample in samples:
            bbox = bbox_by_track.get(sample.track_id)
            if bbox is None:
                # A pose sample for a track the detector didn't report this
                # frame (e.g. a backend interpolating through an occlusion):
                # no fresh box to reason over, so skip this window safely.
                continue

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

            verdict = self.rules.evaluate(
                track_id=sample.track_id,
                bbox=bbox,
                ts=frame.ts,
                is_employee=employee_by_track.get(sample.track_id, False),
            )
            decision = self.fusion.decide(action_score, verdict)

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
            )
            if decision.tier == AlertTier.ALERT:
                # Defer: the clip needs post-roll frames that don't exist yet.
                self._pending_alerts.append(
                    _PendingAlert(
                        event=event,
                        event_ts=frame.ts,
                        ready_ts=frame.ts + self.config.clip_post_roll_s,
                    )
                )
            else:
                self._emit(event)
                events.append(event)

        events.extend(self._drain_ready_clips(now_ts=frame.ts))
        return events

    def finalize(self) -> list[DetectionEvent]:
        """Flush any alerts still awaiting post-roll (end of stream/shift)."""
        return self._drain_ready_clips(now_ts=float("inf"), force=True)
