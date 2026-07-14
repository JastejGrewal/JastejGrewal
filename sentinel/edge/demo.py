"""End-to-end demo: synthetic store -> edge pipeline -> cloud dashboard.

    python -m sentinel.edge.demo                       # prints to stdout
    python -m sentinel.edge.demo --cloud-url http://localhost:8000

With --cloud-url, events post to the cloud API; open the dashboard to see the
alert appear and confirm/reject it. Without connectivity, events queue in the
outbox and drain when the cloud comes back — kill the server mid-demo to see
the offline path work.
"""

from __future__ import annotations

import argparse
import time

from sentinel.edge.outbox import Outbox
from sentinel.edge.pipeline.orchestrator import EdgePipeline, PipelineConfig
from sentinel.edge.pipeline.rules import RuleEngine, Zone
from sentinel.edge.publisher import StdoutPublisher, WebhookPublisher
from sentinel.edge.scenario import store_scenario

MERCHANDISE_ZONE = Zone(
    name="aisle-3",
    kind="merchandise",
    polygon=[(0.0, 0.2), (0.6, 0.2), (0.6, 0.9), (0.0, 0.9)],
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sentinel end-to-end synthetic demo")
    parser.add_argument("--cloud-url", default=None, help="Cloud API base URL")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--include-employee", action="store_true")
    args = parser.parse_args(argv)

    outbox = Outbox()  # in-memory for the demo; on a real box this is a file path
    pipeline = EdgePipeline(
        config=PipelineConfig(),
        rules=RuleEngine(zones=[MERCHANDISE_ZONE]),
        outbox=outbox,
    )

    publisher = (
        WebhookPublisher(args.cloud_url) if args.cloud_url else StdoutPublisher()
    )

    print(f"processing {args.frames} synthetic frames...")
    for frame in store_scenario(n_frames=args.frames, include_employee=args.include_employee):
        pipeline.process_frame(frame)
        # Drain opportunistically, as the real edge loop does.
        outbox.drain(publisher.publish)
    # Flush any alert still awaiting its post-roll clip at end of stream.
    pipeline.finalize()

    # Final drain with brief retries for anything still queued.
    for _ in range(5):
        result = outbox.drain(publisher.publish)
        if result.remaining == 0:
            break
        time.sleep(0.5)

    stats = pipeline.stats
    print(
        f"\nframes={stats.frames} windows_scored={stats.windows_scored} "
        f"events={stats.events_by_tier} outbox_remaining={outbox.pending_count()}"
    )
    alerts = stats.events_by_tier.get("alert", 0)
    if alerts:
        print(f"\n{alerts} ALERT-tier event(s) fired — expected: the concealment actor.")
        if args.cloud_url:
            print(f"open {args.cloud_url} to review and confirm/reject.")
    else:
        print("\nno alerts fired — unexpected for this scenario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
