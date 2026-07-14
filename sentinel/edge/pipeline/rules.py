"""Stage E: deterministic rule/heuristic layer.

Blueprint §4.1: "This layer does most of the actual false-positive suppression
in production." Rules consume track context and emit named flags that the
fusion layer weighs; suppression rules can veto an alert outright.

Zones are per-camera normalized polygons configured at install time
(merchandise zones escalate; checkout/exit zones and employee areas suppress).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import BBox


@dataclass
class Zone:
    name: str
    kind: str  # "merchandise" | "checkout" | "suppress"
    polygon: list[tuple[float, float]]  # normalized vertices

    def contains(self, point: tuple[float, float]) -> bool:
        # Ray casting.
        x, y = point
        inside = False
        n = len(self.polygon)
        for i in range(n):
            x1, y1 = self.polygon[i]
            x2, y2 = self.polygon[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < x_cross:
                    inside = not inside
        return inside


@dataclass
class RuleVerdict:
    flags: list[str] = field(default_factory=list)
    suppressed: bool = False


@dataclass
class _TrackState:
    first_seen_ts: float
    last_bbox: BBox | None = None


class RuleEngine:
    def __init__(self, zones: list[Zone] | None = None, dwell_threshold_s: float = 5.0):
        self.zones = zones or []
        self.dwell_threshold_s = dwell_threshold_s
        self._tracks: dict[int, _TrackState] = {}

    def evaluate(
        self,
        track_id: int,
        bbox: BBox,
        ts: float,
        is_employee: bool = False,
    ) -> RuleVerdict:
        state = self._tracks.setdefault(track_id, _TrackState(first_seen_ts=ts))
        state.last_bbox = bbox

        verdict = RuleVerdict()
        center = bbox.center()

        if is_employee:
            # Uniform/badge visual cue only — never identity (blueprint §3.4).
            verdict.flags.append("employee_suppress")
            verdict.suppressed = True

        for zone in self.zones:
            if not zone.contains(center):
                continue
            if zone.kind == "merchandise":
                verdict.flags.append(f"in_merchandise_zone:{zone.name}")
            elif zone.kind == "checkout":
                # Concealment-like motion at checkout is usually bagging a
                # purchase: suppress rather than escalate.
                verdict.flags.append(f"in_checkout_zone:{zone.name}")
                verdict.suppressed = True
            elif zone.kind == "suppress":
                verdict.flags.append(f"in_suppress_zone:{zone.name}")
                verdict.suppressed = True

        dwell = ts - state.first_seen_ts
        if dwell >= self.dwell_threshold_s:
            verdict.flags.append("long_dwell")

        return verdict

    def forget(self, track_id: int) -> None:
        self._tracks.pop(track_id, None)
