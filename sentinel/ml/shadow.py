"""Shadow deployment (blueprint §4.2, step 1 of the promotion ladder).

Runs a candidate action model in parallel with the production model on the same
live pose windows, logging predictions and divergence WITHOUT ever affecting
alerts. Aggregated agreement + per-class divergence over a fixed window is the
evidence used before a candidate is allowed to canary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sentinel.edge.pipeline.action import ActionClassifier
from sentinel.edge.pipeline.types import PoseSample


@dataclass
class ShadowReport:
    windows: int = 0
    agree: int = 0                     # both above/below the alert threshold
    prod_only_positive: int = 0        # production fires, candidate doesn't
    cand_only_positive: int = 0        # candidate fires, production doesn't
    sum_abs_delta: float = 0.0
    _deltas: list[float] = field(default_factory=list)

    @property
    def agreement_rate(self) -> float:
        return self.agree / self.windows if self.windows else 0.0

    @property
    def mean_abs_delta(self) -> float:
        return self.sum_abs_delta / self.windows if self.windows else 0.0

    def to_dict(self) -> dict:
        return {
            "windows": self.windows,
            "agreement_rate": round(self.agreement_rate, 4),
            "prod_only_positive": self.prod_only_positive,
            "cand_only_positive": self.cand_only_positive,
            "mean_abs_delta": round(self.mean_abs_delta, 4),
        }


class ShadowRunner:
    """Feed pose windows to both models; production drives behavior, candidate
    is observed only."""

    def __init__(
        self,
        production: ActionClassifier,
        candidate: ActionClassifier,
        alert_threshold: float = 0.75,
    ):
        self.production = production
        self.candidate = candidate
        self.alert_threshold = alert_threshold
        self.report = ShadowReport()

    def observe(self, samples: list[PoseSample]) -> float | None:
        """Score with both; return the PRODUCTION score (what the pipeline uses)."""
        prod = self.production.score_window(samples)
        cand = self.candidate.score_window(samples)
        if prod is None or cand is None:
            return prod.score if prod else None

        self.report.windows += 1
        prod_pos = prod.score >= self.alert_threshold
        cand_pos = cand.score >= self.alert_threshold
        if prod_pos == cand_pos:
            self.report.agree += 1
        elif prod_pos and not cand_pos:
            self.report.prod_only_positive += 1
        else:
            self.report.cand_only_positive += 1
        self.report.sum_abs_delta += abs(prod.score - cand.score)
        return prod.score
