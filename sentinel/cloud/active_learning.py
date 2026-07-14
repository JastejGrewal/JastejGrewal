"""Active-learning review-queue prioritization — blueprint §4.2.

Phase 1 implements the two signals available without a second model branch:

- boundary confidence: events whose fused score sits near the decision
  boundary carry the most label information;
- novelty: distance from the centroids of already-labeled examples in a
  simple feature space (fused/action score, flag count) — a stand-in for the
  pgvector embedding search that arrives with real embeddings in Phase 2;
- plus stratified low-rate sampling of confident negatives so silent model
  failures still get human eyes.

Ensemble disagreement joins in Phase 3 when the appearance branch exists.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class QueueItem:
    event: dict
    priority: float
    reasons: list[str]


def _features(event: dict) -> tuple[float, float, float]:
    return (
        float(event["fused_score"]),
        float(event["action_score"]),
        float(len(event.get("rule_flags", []))) / 5.0,
    )


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def prioritize(
    unreviewed: list[dict],
    labeled: list[dict],
    boundary_center: float = 0.5,
    negative_sample_rate: float = 0.05,
) -> list[QueueItem]:
    """Rank unreviewed events for human review, highest label-value first."""
    centroids: list[tuple[float, float, float]] = []
    if labeled:
        by_verdict: dict[str, list[tuple[float, float, float]]] = {}
        for ex in labeled:
            by_verdict.setdefault(ex["verdict"], []).append(_features(ex))
        for feats in by_verdict.values():
            n = len(feats)
            centroids.append(tuple(sum(f[i] for f in feats) / n for i in range(3)))

    items: list[QueueItem] = []
    for i, event in enumerate(unreviewed):
        reasons: list[str] = []
        score = float(event["fused_score"])

        # Boundary confidence: 1 at the boundary, 0 at the extremes.
        boundary = 1.0 - min(1.0, abs(score - boundary_center) / boundary_center)
        if boundary > 0.6:
            reasons.append("boundary_confidence")

        # Novelty: distance to the nearest labeled-class centroid.
        novelty = 0.0
        if centroids:
            novelty = min(_distance(_features(event), c) for c in centroids)
            novelty = min(1.0, novelty)  # feature space is roughly unit-scaled
            if novelty > 0.3:
                reasons.append("novelty")

        # Stratified sampling of confident negatives (deterministic by index
        # so the queue is stable across calls).
        sampled_negative = False
        if score < 0.2 and negative_sample_rate > 0:
            stride = max(1, int(1 / negative_sample_rate))
            if i % stride == 0:
                sampled_negative = True
                reasons.append("sampled_negative")

        priority = 0.6 * boundary + 0.4 * novelty
        if sampled_negative:
            priority = max(priority, 0.25)
        # Alerts awaiting review always outrank passive telemetry.
        if event["tier"] == "alert":
            priority += 1.0
            reasons.append("unreviewed_alert")

        items.append(QueueItem(event=event, priority=round(priority, 4), reasons=reasons))

    items.sort(key=lambda it: it.priority, reverse=True)
    return items
