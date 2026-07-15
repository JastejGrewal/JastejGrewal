"""Render a real MP4 of a person moving across a scene, for in-sandbox testing.

We can't ship real CCTV footage in the repo and can't fetch it here (egress
policy), so this composites a real photo of a person (scikit-image's bundled
`astronaut` image — actual pixels of a real human, no download) onto a moving
position over a plain background and encodes a real .mp4. The result is genuine
video that a real detector (OpenCV HOG / YOLO) actually fires on — enough to
exercise the decode -> detect -> track -> pipeline path on real pixels.

    python -m sentinel.edge.render_demo_video --out /tmp/store.mp4
"""

from __future__ import annotations

import argparse


def render(out_path: str, n_frames: int = 90, fps: int = 15, size: tuple[int, int] = (640, 480)) -> str:
    import cv2
    import numpy as np
    from skimage import data

    w, h = size
    person = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)  # real person, 512x512
    # Scale the person to a plausible on-camera height (~60% of frame height).
    ph = int(h * 0.6)
    pw = int(person.shape[1] * (ph / person.shape[0]))
    person = cv2.resize(person, (pw, ph))

    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"could not open VideoWriter for {out_path!r}")

    try:
        for i in range(n_frames):
            # Store-ish background: mid-gray with a darker shelf band.
            frame = np.full((h, w, 3), 150, dtype=np.uint8)
            cv2.rectangle(frame, (0, int(h * 0.15)), (w, int(h * 0.35)), (90, 90, 90), -1)
            # Person walks left->right across the aisle.
            x = int((w - pw) * (i / max(1, n_frames - 1)))
            y = h - ph - 10
            frame[y : y + ph, x : x + pw] = person
            writer.write(frame)
    finally:
        writer.release()
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a real test MP4 with a moving person")
    parser.add_argument("--out", required=True)
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--fps", type=int, default=15)
    args = parser.parse_args(argv)
    path = render(args.out, n_frames=args.frames, fps=args.fps)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
