"""Stage B: pluggable pose estimators.

Skeleton keypoints are the privacy-preserving representation the rest of the
system reasons over (blueprint §4.1 stage B): no pixels leave this stage.
"""

from __future__ import annotations

from typing import Protocol

from .types import Frame, PoseSample, TrackedPerson


class PoseEstimator(Protocol):
    def estimate(self, frame: Frame, people: list[TrackedPerson]) -> list[PoseSample]: ...


class SyntheticPose:
    """Reads keypoints from the synthetic actor attached to each detection."""

    def estimate(self, frame: Frame, people: list[TrackedPerson]) -> list[PoseSample]:
        samples: list[PoseSample] = []
        for person in people:
            actor = person.detection.actor_ref
            if actor is None:
                continue
            samples.append(
                PoseSample(
                    track_id=person.track_id,
                    ts=person.ts,
                    keypoints=list(actor.keypoints),
                )
            )
        return samples
