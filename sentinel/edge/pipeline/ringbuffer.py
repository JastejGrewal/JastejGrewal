"""Rolling per-camera ring buffer for pre/post-roll alert clips (§4.3).

Phase 1 stores frame metadata (and whatever `image` payload the ingest layer
attached); the clip extracted for an alert is a ClipRef plus the frame slice,
which the publisher can encode/upload. Raw frames never leave the store except
inside these flagged clips — the privacy core of the edge-primary design.
"""

from __future__ import annotations

from collections import deque

from sentinel.common.events import ClipRef

from .types import Frame


class RingBuffer:
    def __init__(self, camera_id: str, capacity_seconds: float = 90.0, fps: float = 15.0):
        self.camera_id = camera_id
        self._frames: deque[Frame] = deque(maxlen=int(capacity_seconds * fps))

    def push(self, frame: Frame) -> None:
        self._frames.append(frame)

    def __len__(self) -> int:
        return len(self._frames)

    def extract_clip(
        self, event_ts: float, pre_roll_s: float = 5.0, post_roll_s: float = 5.0
    ) -> tuple[ClipRef, list[Frame]]:
        """Slice frames in [event_ts - pre_roll, event_ts + post_roll]."""
        start = event_ts - pre_roll_s
        end = event_ts + post_roll_s
        frames = [f for f in self._frames if start <= f.ts <= end]
        ref = ClipRef(
            camera_id=self.camera_id,
            start_ts=frames[0].ts if frames else start,
            end_ts=frames[-1].ts if frames else end,
            frame_count=len(frames),
        )
        return ref, frames
