"""Run the real pipeline on real video.

    python -m sentinel.edge.run_video --source store.mp4               # HOG detect
    python -m sentinel.edge.run_video --source rtsp://... --backend yolo-pose
    python -m sentinel.edge.run_video --source store.mp4 --cloud-url http://localhost:8000

Backends:
  hog        real OpenCV HOG person detection (no weights download) — the
             sandbox-runnable path; proves decode -> detect -> track -> pipeline
             on real pixels. No pose model, so pose-dependent action scoring is
             skipped (detections/tracks still flow).
  yolo-pose  real neural detection + COCO-17 pose in one model; runs the FULL
             pipeline (incl. action/fusion) on real pixels wherever the weights
             are reachable (e.g. a network with github/HF access).

The pipeline, tracker, rules, fusion, outbox and cloud path are identical to
the synthetic demo — only the perception front-end changes.
"""

from __future__ import annotations

import argparse

from sentinel.common.events import AlertTier
from sentinel.edge.ingest.video import frames_from_source
from sentinel.edge.outbox import Outbox
from sentinel.edge.pipeline.orchestrator import EdgePipeline, PipelineConfig
from sentinel.edge.pipeline.pose import PoseEstimator
from sentinel.edge.pipeline.rules import RuleEngine, Zone
from sentinel.edge.publisher import StdoutPublisher, WebhookPublisher
from sentinel.edge.pipeline.types import Frame, PoseSample, TrackedPerson

FULL_FLOOR = Zone(
    name="floor", kind="merchandise",
    polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
)


class _NullPose:
    """No pose backend available: emit no keypoints (detection/tracking only)."""

    def estimate(self, frame: Frame, people: list[TrackedPerson]) -> list[PoseSample]:
        return []


def _build_backends(backend: str):
    """Return (detector, pose) for the requested backend."""
    if backend == "yolo-pose":
        from sentinel.edge.pipeline.pose_yolo import yolo_pose_stages

        return yolo_pose_stages()
    if backend == "hog":
        from sentinel.edge.pipeline.detector import HogDetector

        return HogDetector(), _NullPose()
    raise ValueError(f"unknown backend: {backend!r} (use 'hog' or 'yolo-pose')")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Sentinel on real video")
    parser.add_argument("--source", required=True, help="video file path or RTSP URL")
    parser.add_argument("--backend", default="hog", choices=["hog", "yolo-pose"])
    parser.add_argument("--target-fps", type=float, default=10.0)
    parser.add_argument("--cloud-url", default=None)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args(argv)

    detector, pose = _build_backends(args.backend)
    outbox = Outbox()
    pipeline = EdgePipeline(
        config=PipelineConfig(),
        detector=detector,
        pose=pose,
        rules=RuleEngine(zones=[FULL_FLOOR]),
        outbox=outbox,
    )
    publisher = WebhookPublisher(args.cloud_url) if args.cloud_url else StdoutPublisher()

    frames = 0
    frames_with_person = 0
    distinct_tracks: set[int] = set()
    print(f"running backend={args.backend} on {args.source}")
    for frame in frames_from_source(args.source, target_fps=args.target_fps):
        frames += 1
        pipeline.process_frame(frame)
        active = pipeline.tracker.active_ids
        if active:
            frames_with_person += 1
            distinct_tracks |= active
        outbox.drain(publisher.publish)
        if args.max_frames and frames >= args.max_frames:
            break
    pipeline.finalize()
    outbox.drain(publisher.publish)

    stats = pipeline.stats
    print(
        f"\nframes={frames} frames_with_person={frames_with_person} "
        f"distinct_tracks={len(distinct_tracks)} "
        f"windows_scored={stats.windows_scored} events={stats.events_by_tier}"
    )
    print(
        f"real perception ran: detected a person in {frames_with_person}/{frames} "
        f"decoded frames and tracked {len(distinct_tracks)} distinct person(s)."
    )
    alerts = stats.events_by_tier.get(AlertTier.ALERT.value, 0)
    if args.backend == "hog":
        print("(HOG backend: no pose model, so no gesture/action alerts — "
              "swap --backend yolo-pose where weights are reachable for the full pipeline.)")
    elif alerts:
        print(f"{alerts} ALERT(s) from real pose+action on real video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
