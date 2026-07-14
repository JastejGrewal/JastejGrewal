"""Stage F: fusion, temporal hysteresis, and confidence tiering.

Phase 1 fuses the kinematic action score with rule flags via a fixed logistic;
the same interface later takes the learned LightGBM/MLP meta-model. Hysteresis
requires N positive windows in the last M before escalating (blueprint §4.1:
"require N consecutive positive windows, not a single flicker").
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from sentinel.common.events import AlertTier

from .action import ActionScore
from .rules import RuleVerdict


@dataclass
class FusedDecision:
    track_id: int
    fused_score: float
    tier: AlertTier
    action_score: float
    rule_flags: list[str]
    window_start_ts: float
    window_end_ts: float


class FusionEngine:
    def __init__(
        self,
        soft_threshold: float = 0.55,
        alert_threshold: float = 0.75,
        hysteresis_n: int = 2,
        hysteresis_m: int = 4,
        merchandise_boost: float = 0.8,
        dwell_boost: float = 0.3,
        bias: float = -0.2,
    ):
        self.soft_threshold = soft_threshold
        self.alert_threshold = alert_threshold
        self.hysteresis_n = hysteresis_n
        self.hysteresis_m = hysteresis_m
        self.merchandise_boost = merchandise_boost
        self.dwell_boost = dwell_boost
        self.bias = bias
        self._history: dict[int, deque[bool]] = {}

    def _fuse(self, action: ActionScore, rules: RuleVerdict) -> float:
        # Logistic over: action evidence (log-odds) + rule context boosts.
        p = min(max(action.score, 1e-6), 1 - 1e-6)
        logit = math.log(p / (1 - p)) + self.bias
        if any(f.startswith("in_merchandise_zone") for f in rules.flags):
            logit += self.merchandise_boost
        if "long_dwell" in rules.flags:
            logit += self.dwell_boost
        return 1 / (1 + math.exp(-logit))

    def decide(self, action: ActionScore, rules: RuleVerdict) -> FusedDecision:
        fused = self._fuse(action, rules)

        # Record EVERY scored window in the rolling history, counting a
        # suppressed window as non-positive. This keeps hysteresis anchored to
        # recent wall-clock windows: a track that dwells in a suppressed zone
        # decays its history to zero instead of freezing stale positives that
        # would otherwise fire an instant ALERT the moment it leaves the zone.
        positive = (not rules.suppressed) and fused >= self.soft_threshold
        history = self._history.setdefault(
            action.track_id, deque(maxlen=self.hysteresis_m)
        )
        history.append(positive)
        positives = sum(history)

        if rules.suppressed:
            tier = AlertTier.LOG
        elif fused >= self.alert_threshold and positives >= self.hysteresis_n:
            tier = AlertTier.ALERT
        elif fused >= self.soft_threshold and positives >= self.hysteresis_n:
            tier = AlertTier.SOFT
        else:
            tier = AlertTier.LOG

        return FusedDecision(
            track_id=action.track_id,
            fused_score=round(fused, 4),
            tier=tier,
            action_score=action.score,
            rule_flags=list(rules.flags),
            window_start_ts=action.window_start_ts,
            window_end_ts=action.window_end_ts,
        )

    def forget(self, track_id: int) -> None:
        self._history.pop(track_id, None)
