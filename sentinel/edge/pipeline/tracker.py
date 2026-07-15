"""Stage A (tracking half): greedy IoU tracker.

A deliberately simple stand-in for ByteTrack/BoT-SORT with the same contract:
stable integer track ids over time. Good enough for Phase 1 synthetic and
single-camera validation; swap for ByteTrack when the ml extra lands.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import BBox, Detection, TrackedPerson


@dataclass
class _Track:
    track_id: int
    bbox: BBox
    misses: int = 0


class IoUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_misses: int = 15):
        self._iou_threshold = iou_threshold
        self._max_misses = max_misses
        self._tracks: dict[int, _Track] = {}
        self._next_id = 1
        # Track ids aged out during the most recent update(), so the
        # orchestrator can release the per-track state those ids own
        # (fixes the unbounded-growth leak in a 24/7 process).
        self.dropped_ids: list[int] = []

    @property
    def active_ids(self) -> set[int]:
        return set(self._tracks)

    def update(self, detections: list[Detection], ts: float) -> list[TrackedPerson]:
        self.dropped_ids = []
        # Greedy matching: highest-IoU (track, detection) pairs first.
        pairs: list[tuple[float, int, int]] = []
        for ti, track in self._tracks.items():
            for di, det in enumerate(detections):
                iou = track.bbox.iou(det.bbox)
                if iou >= self._iou_threshold:
                    pairs.append((iou, ti, di))
        pairs.sort(reverse=True)

        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        assignments: dict[int, int] = {}  # detection index -> track id
        for _iou, ti, di in pairs:
            if ti in matched_tracks or di in matched_dets:
                continue
            matched_tracks.add(ti)
            matched_dets.add(di)
            assignments[di] = ti

        out: list[TrackedPerson] = []
        for di, det in enumerate(detections):
            if di in assignments:
                tid = assignments[di]
                self._tracks[tid].bbox = det.bbox
                self._tracks[tid].misses = 0
            else:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = _Track(track_id=tid, bbox=det.bbox)
            out.append(TrackedPerson(track_id=tid, detection=det, ts=ts))

        # Age out unmatched tracks.
        live_ids = {p.track_id for p in out}
        for tid in list(self._tracks):
            if tid not in live_ids:
                self._tracks[tid].misses += 1
                if self._tracks[tid].misses > self._max_misses:
                    del self._tracks[tid]
                    self.dropped_ids.append(tid)
        return out
