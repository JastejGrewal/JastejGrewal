"""Canary rollout (blueprint §4.2, step 2 of the promotion ladder).

After a candidate survives shadow mode, it alerts for real on a small,
deterministic slice of cameras while the incumbent serves the rest. The
controller compares live outcomes (LP confirm / false-alarm rates) between the
canary slice and the control group and produces one of three verdicts:

- CONTINUE   — not enough evidence yet, keep collecting;
- ROLLBACK   — the canary's false-alarm rate is materially worse: pull it;
- PROMOTE_READY — enough volume, no regression: safe to widen the rollout.

Assignment is a deterministic hash of camera_id, so a camera stays in the same
group across restarts (no flapping between models mid-shift) and the split
needs no coordination state.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


def in_canary(camera_id: str, fraction: float, salt: str = "") -> bool:
    """Deterministically assign a camera to the canary slice."""
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be in [0, 1]")
    digest = hashlib.sha256(f"{salt}:{camera_id}".encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") / 2**32
    return bucket < fraction


class CanaryVerdict(str, Enum):
    CONTINUE = "continue"
    ROLLBACK = "rollback"
    PROMOTE_READY = "promote_ready"


@dataclass
class _GroupStats:
    alerts: int = 0
    confirmed: int = 0
    false_alarms: int = 0

    @property
    def reviewed(self) -> int:
        return self.confirmed + self.false_alarms

    @property
    def false_alarm_rate(self) -> float:
        return self.false_alarms / self.reviewed if self.reviewed else 0.0


@dataclass
class CanaryController:
    """Aggregates live alert outcomes for canary vs control and judges them."""

    candidate_version: str
    fraction: float = 0.05
    salt: str = ""
    # Judgement thresholds:
    min_reviewed_per_group: int = 20      # evidence floor before any verdict
    max_far_increase: float = 0.10        # canary FAR may exceed control by at most this
    stats: dict[str, _GroupStats] = field(
        default_factory=lambda: {"canary": _GroupStats(), "control": _GroupStats()}
    )

    def group_for(self, camera_id: str) -> str:
        return "canary" if in_canary(camera_id, self.fraction, self.salt) else "control"

    def record_alert(self, camera_id: str) -> None:
        self.stats[self.group_for(camera_id)].alerts += 1

    def record_feedback(self, camera_id: str, verdict: str) -> None:
        group = self.stats[self.group_for(camera_id)]
        if verdict == "confirmed":
            group.confirmed += 1
        elif verdict == "false_alarm":
            group.false_alarms += 1
        # 'unsure' contributes no evidence, mirroring the retraining label rule.

    def evaluate(self) -> tuple[CanaryVerdict, str]:
        canary, control = self.stats["canary"], self.stats["control"]

        # Rollback can trigger early on egregious canary noise: enough canary
        # reviews, nearly all false alarms — don't wait for the control floor.
        if canary.reviewed >= self.min_reviewed_per_group and canary.false_alarm_rate >= 0.8:
            return (
                CanaryVerdict.ROLLBACK,
                f"canary false-alarm rate {canary.false_alarm_rate:.2f} is egregious",
            )

        if (
            canary.reviewed < self.min_reviewed_per_group
            or control.reviewed < self.min_reviewed_per_group
        ):
            return (
                CanaryVerdict.CONTINUE,
                f"insufficient evidence: canary={canary.reviewed}, "
                f"control={control.reviewed} reviewed "
                f"(need {self.min_reviewed_per_group} each)",
            )

        far_delta = canary.false_alarm_rate - control.false_alarm_rate
        if far_delta > self.max_far_increase:
            return (
                CanaryVerdict.ROLLBACK,
                f"canary false-alarm rate {canary.false_alarm_rate:.2f} exceeds "
                f"control {control.false_alarm_rate:.2f} by more than "
                f"{self.max_far_increase}",
            )
        return (
            CanaryVerdict.PROMOTE_READY,
            f"no regression: canary FAR {canary.false_alarm_rate:.2f} vs "
            f"control {control.false_alarm_rate:.2f} over "
            f"{canary.reviewed}+{control.reviewed} reviewed alerts",
        )
