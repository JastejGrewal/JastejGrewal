"""Synthetic store scenarios: scripted actors emitting frames with ground truth.

Used by the e2e tests and the demo. Actors are kinematic scripts over the
minimal keypoint set; the concealment actor performs the reach-then-stow
signature inside the merchandise zone, the browser reaches but never stows,
and the employee performs restock motions that look concealment-ish — which
is exactly what the employee-uniform suppression rule exists to kill.
"""

from __future__ import annotations

import math
from collections.abc import Iterator

from .pipeline.types import BBox, Frame, Keypoint, N_KEYPOINTS, SyntheticActor


def _base_keypoints(cx: float, cy: float) -> list[tuple[float, float]]:
    """Neutral standing pose centred at (cx, cy); person is ~0.2 tall."""
    kp: list[tuple[float, float]] = [(0.0, 0.0)] * N_KEYPOINTS
    kp[Keypoint.LEFT_SHOULDER] = (cx - 0.03, cy - 0.06)
    kp[Keypoint.RIGHT_SHOULDER] = (cx + 0.03, cy - 0.06)
    kp[Keypoint.LEFT_WRIST] = (cx - 0.04, cy)
    kp[Keypoint.RIGHT_WRIST] = (cx + 0.04, cy)
    kp[Keypoint.LEFT_HIP] = (cx - 0.02, cy + 0.04)
    kp[Keypoint.RIGHT_HIP] = (cx + 0.02, cy + 0.04)
    return kp


def _bbox_around(cx: float, cy: float) -> BBox:
    return BBox(x=cx - 0.06, y=cy - 0.10, w=0.12, h=0.24)


def _actor(actor_id: str, cx: float, cy: float, right_wrist: tuple[float, float] | None = None) -> SyntheticActor:
    kp = _base_keypoints(cx, cy)
    if right_wrist is not None:
        kp[Keypoint.RIGHT_WRIST] = right_wrist
    return SyntheticActor(actor_id=actor_id, bbox=_bbox_around(cx, cy), keypoints=kp)


def concealment_actor(actor_id: str, t: int, cx: float = 0.3, cy: float = 0.5) -> SyntheticActor:
    """Reach (frames 10-25), stow at hip (frames 26-60), then idle."""
    if 10 <= t <= 25:
        # Arm extends toward the shelf: wrist moves away from the torso.
        progress = (t - 10) / 15
        wrist = (cx + 0.04 + 0.18 * progress, cy - 0.02)
    elif 26 <= t <= 60:
        # Hand at hip/waistband: the stow dwell.
        hip = (cx + 0.02, cy + 0.04)
        wrist = (hip[0] + 0.01, hip[1] + 0.005)
    else:
        wrist = None
    return _actor(actor_id, cx, cy, right_wrist=wrist)


def browsing_actor(actor_id: str, t: int, cx: float = 0.7, cy: float = 0.5) -> SyntheticActor:
    """Reaches for items but the hand returns to a neutral carry, never a stow."""
    # Gentle periodic reach.
    phase = math.sin(t / 8.0)
    if phase > 0.3:
        wrist = (cx + 0.04 + 0.15 * phase, cy - 0.02)
    else:
        wrist = (cx + 0.05, cy - 0.01)  # neutral carry, well away from hip
    return _actor(actor_id, cx, cy, right_wrist=wrist)


def employee_restock_actor(actor_id: str, t: int, cx: float = 0.5, cy: float = 0.35) -> SyntheticActor:
    """Same reach-and-stow kinematics as a thief — suppressed by uniform rule."""
    return concealment_actor(actor_id, t, cx=cx, cy=cy)


def store_scenario(
    n_frames: int = 120,
    fps: float = 10.0,
    camera_id: str = "cam-01",
    include_employee: bool = False,
) -> Iterator[Frame]:
    """Two shoppers (one thief, one browser), optional restocking employee."""
    for t in range(n_frames):
        actors = [
            concealment_actor("shopper_thief", t),
            browsing_actor("shopper_browser", t),
        ]
        if include_employee:
            actors.append(employee_restock_actor("employee_restock", t))
        yield Frame(
            camera_id=camera_id,
            ts=t / fps,
            index=t,
            synthetic_actors=actors,
        )
