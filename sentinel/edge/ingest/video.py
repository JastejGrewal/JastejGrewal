"""Real video ingestion — decode a file or RTSP stream into Frame objects.

This is the ingest half of blueprint §4.3: the edge box pulls RTSP (or reads a
recorded file for dev/replay) and hands decoded BGR frames to the pipeline.
The `image` on each Frame is a real numpy ndarray (H, W, 3) BGR, which the
real perception backends (YOLO-pose) consume.

OpenCV is an optional dependency (part of the `[ml]` extra); importing this
module without it raises a clear error rather than failing at call time.
"""

from __future__ import annotations

from collections.abc import Iterator

from sentinel.edge.pipeline.types import Frame

try:
    import cv2

    _HAVE_CV2 = True
except ImportError:  # pragma: no cover - exercised only in minimal installs
    _HAVE_CV2 = False


class VideoSource:
    """Iterable wrapper over an OpenCV VideoCapture (file path or RTSP URL).

    `target_fps` decimates the source to a processing rate: real CCTV is often
    25-30 fps but the pipeline only needs ~10-15 fps for gesture windows, and
    dropping frames at ingest is the cheapest place to save downstream compute.
    """

    def __init__(self, source: str, camera_id: str = "cam-01", target_fps: float | None = None):
        if not _HAVE_CV2:
            raise RuntimeError(
                "VideoSource requires OpenCV: pip install '.[ml]' (opencv-python-headless)"
            )
        self.source = source
        self.camera_id = camera_id
        self.target_fps = target_fps
        self._cap = None

    def __enter__(self) -> "VideoSource":
        self._cap = cv2.VideoCapture(self.source)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open video source: {self.source!r}")
        return self

    def __exit__(self, *exc) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _source_fps(self) -> float:
        fps = self._cap.get(cv2.CAP_PROP_FPS) if self._cap else 0.0
        # RTSP/webcams often report 0; assume 25 as a sane default.
        return fps if fps and fps > 0 else 25.0

    def frames(self) -> Iterator[Frame]:
        """Yield decoded frames, decimated to target_fps if set."""
        if self._cap is None:
            raise RuntimeError("use VideoSource as a context manager (`with VideoSource(...)`)")

        source_fps = self._source_fps()
        # Emit a frame whenever accumulated source time crosses the target step.
        step = (1.0 / self.target_fps) if self.target_fps else 0.0
        next_emit = 0.0
        index = 0
        src_index = 0
        while True:
            ok, image = self._cap.read()
            if not ok:
                break
            src_ts = src_index / source_fps
            src_index += 1
            if step and src_ts + 1e-9 < next_emit:
                continue
            next_emit = src_ts + step
            yield Frame(camera_id=self.camera_id, ts=src_ts, index=index, image=image)
            index += 1


def frames_from_source(
    source: str, camera_id: str = "cam-01", target_fps: float | None = 10.0
) -> Iterator[Frame]:
    """Convenience: open a source and stream frames (closes on exhaustion)."""
    with VideoSource(source, camera_id=camera_id, target_fps=target_fps) as vs:
        yield from vs.frames()
