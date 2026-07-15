"""Real-perception tests: keypoint mapping (pure) + real video decode/detect.

The cv2/skimage-backed tests are skipped automatically where those optional
deps aren't installed (they live in the `[ml]`/`[dev]` extras), so the core
suite still runs in a minimal environment.
"""

import pytest

from sentinel.edge.pipeline.pose_yolo import map_coco17_to_sentinel
from sentinel.edge.pipeline.types import Keypoint


# --- pure keypoint mapping (no model weights, no heavy deps) -----------------

def test_coco17_to_sentinel_mapping():
    # 17 COCO points; put a recognizable value at each mapped index.
    coco = [(0.0, 0.0)] * 17
    coco[5] = (100, 200)    # L shoulder
    coco[6] = (300, 200)    # R shoulder
    coco[9] = (110, 400)    # L wrist
    coco[10] = (290, 400)   # R wrist
    coco[11] = (140, 500)   # L hip
    coco[12] = (260, 500)   # R hip
    kp = map_coco17_to_sentinel(coco, width=400, height=1000)

    assert kp[Keypoint.LEFT_SHOULDER] == (0.25, 0.2)
    assert kp[Keypoint.RIGHT_WRIST] == (0.725, 0.4)
    assert kp[Keypoint.LEFT_HIP] == (0.35, 0.5)
    assert len(kp) == len(Keypoint)


def test_coco17_mapping_tolerates_short_input():
    kp = map_coco17_to_sentinel([(10, 10)] * 6, width=100, height=100)
    # Indices 9/10/11/12 are absent -> stay at origin; 5/6 map through.
    assert kp[Keypoint.LEFT_SHOULDER] == (0.1, 0.1)
    assert kp[Keypoint.LEFT_WRIST] == (0.0, 0.0)


# --- real video decode + real HOG detection ----------------------------------

cv2 = pytest.importorskip("cv2")
pytest.importorskip("skimage")


@pytest.fixture()
def real_mp4(tmp_path):
    from sentinel.edge.render_demo_video import render

    return render(str(tmp_path / "store.mp4"), n_frames=30, fps=15)


def test_render_produces_playable_mp4(real_mp4):
    cap = cv2.VideoCapture(real_mp4)
    assert cap.isOpened()
    ok, frame = cap.read()
    cap.release()
    assert ok and frame.ndim == 3 and frame.shape[2] == 3


def test_video_source_decodes_real_frames(real_mp4):
    from sentinel.edge.ingest.video import VideoSource

    with VideoSource(real_mp4, target_fps=None) as vs:
        frames = list(vs.frames())
    assert len(frames) == 30
    assert all(f.image is not None and f.image.shape[2] == 3 for f in frames)
    # Timestamps are monotonic.
    assert all(frames[i].ts < frames[i + 1].ts for i in range(len(frames) - 1))


def test_target_fps_decimates(real_mp4):
    from sentinel.edge.ingest.video import VideoSource

    with VideoSource(real_mp4, target_fps=5.0) as vs:  # 15fps source -> ~5fps
        frames = list(vs.frames())
    assert 8 <= len(frames) <= 12  # ~1/3 of 30


def test_hog_detects_real_person(real_mp4):
    from sentinel.edge.ingest.video import VideoSource
    from sentinel.edge.pipeline.detector import HogDetector

    detector = HogDetector()
    hits = 0
    with VideoSource(real_mp4, target_fps=None) as vs:
        for frame in vs.frames():
            if detector.detect(frame):
                hits += 1
    # Real detector fires on the real composited person in most frames.
    assert hits >= 20


def test_pipeline_runs_on_real_video(real_mp4):
    """The full edge pipeline consumes real decoded frames without error and
    tracks the real detected person."""
    from sentinel.edge.ingest.video import VideoSource
    from sentinel.edge.outbox import Outbox
    from sentinel.edge.pipeline.detector import HogDetector
    from sentinel.edge.pipeline.orchestrator import EdgePipeline, PipelineConfig
    from sentinel.edge.run_video import _NullPose

    pipeline = EdgePipeline(
        config=PipelineConfig(),
        detector=HogDetector(),
        pose=_NullPose(),
        outbox=Outbox(),
    )
    tracked = set()
    with VideoSource(real_mp4, target_fps=10.0) as vs:
        for frame in vs.frames():
            pipeline.process_frame(frame)
            tracked |= pipeline.tracker.active_ids
    assert tracked, "expected at least one real track from real detections"
