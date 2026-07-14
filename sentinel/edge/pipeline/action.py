"""Stage C: temporal action scoring over per-track keypoint windows.

Phase 1 ships a transparent kinematic classifier behind the same interface a
trained ST-GCN/PoseC3D model will use later. The concealment signature it
scores is the classic "reach and stow": the wrist extends away from the torso
(shelf reach), then returns to the hip/waistband region and *dwells* there —
which is what stuffing an item into a pocket, bag, or waistband looks like in
skeleton space. Normal browsing extends the arm but doesn't produce a
sustained near-hip dwell right after the reach.

Being feature-based (not learned) it is honest about its role: a placeholder
that makes the whole pipeline testable end-to-end, to be replaced via the
model registry once Phase 0 training data exists.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

from .types import Keypoint, PoseSample


@dataclass
class ActionScore:
    track_id: int
    score: float                      # calibrated-ish [0, 1]
    window_start_ts: float
    window_end_ts: float
    features: dict[str, float] = field(default_factory=dict)


class ActionClassifier(Protocol):
    def score_window(self, samples: list[PoseSample]) -> ActionScore | None: ...


def _wrist_hip_gap(sample: PoseSample) -> float:
    """Min distance from either wrist to either hip: 'hand at stow position'."""
    wrists = [sample.kp(Keypoint.LEFT_WRIST), sample.kp(Keypoint.RIGHT_WRIST)]
    hips = [sample.kp(Keypoint.LEFT_HIP), sample.kp(Keypoint.RIGHT_HIP)]
    return min(math.dist(w, h) for w in wrists for h in hips)


def _reach_extent(sample: PoseSample) -> float:
    """Max distance from either wrist to its shoulder midline: 'arm extension'."""
    wrists = [sample.kp(Keypoint.LEFT_WRIST), sample.kp(Keypoint.RIGHT_WRIST)]
    ls, rs = sample.kp(Keypoint.LEFT_SHOULDER), sample.kp(Keypoint.RIGHT_SHOULDER)
    mid = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
    return max(math.dist(w, mid) for w in wrists)


class KinematicConcealmentClassifier:
    """Scores the reach-then-stow signature over one pose window."""

    def __init__(
        self,
        reach_threshold: float = 0.12,
        # Must be tighter than the natural hands-at-sides hang distance
        # (~0.045 in normalized units), or idle standing reads as stowing.
        stow_gap_threshold: float = 0.03,
        min_stow_frames: int = 4,
        min_window: int = 8,
    ):
        self.reach_threshold = reach_threshold
        self.stow_gap_threshold = stow_gap_threshold
        self.min_stow_frames = min_stow_frames
        self.min_window = min_window

    def score_window(self, samples: list[PoseSample]) -> ActionScore | None:
        if len(samples) < self.min_window:
            return None

        reach = [_reach_extent(s) for s in samples]
        gap = [_wrist_hip_gap(s) for s in samples]

        peak_reach = max(reach)
        peak_idx = reach.index(peak_reach)

        # Longest run of near-hip dwell frames strictly after the reach peak.
        stow_run = best_run = 0
        for g in gap[peak_idx + 1 :]:
            if g <= self.stow_gap_threshold:
                stow_run += 1
                best_run = max(best_run, stow_run)
            else:
                stow_run = 0

        reached = peak_reach >= self.reach_threshold
        stowed = best_run >= self.min_stow_frames

        # Smooth score: both components saturate at ~2x their threshold.
        reach_component = min(1.0, peak_reach / (2 * self.reach_threshold))
        stow_component = min(1.0, best_run / (2 * self.min_stow_frames))
        if reached and stowed:
            score = 0.5 + 0.5 * (0.5 * reach_component + 0.5 * stow_component)
        else:
            score = 0.4 * reach_component * stow_component

        return ActionScore(
            track_id=samples[0].track_id,
            score=round(score, 4),
            window_start_ts=samples[0].ts,
            window_end_ts=samples[-1].ts,
            features={
                "peak_reach": round(peak_reach, 4),
                "best_stow_run": float(best_run),
                "min_gap": round(min(gap), 4),
            },
        )
