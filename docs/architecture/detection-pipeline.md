# Detection Pipeline Spec

Canonical spec for the staged cascade (blueprint §4.1). This document tracks
what is **implemented** vs. **planned**; keep it in sync as stages evolve.

## Stage map

| Stage | Role | Phase 1 implementation | Production target |
|---|---|---|---|
| A | Person detection | `SyntheticDetector` (tests/demo); `UltralyticsDetector` behind `[ml]` extra | YOLOv8/v11-n INT8 on TensorRT |
| A | Tracking | `IoUTracker` (greedy IoU, miss aging) | ByteTrack / BoT-SORT |
| B | Pose estimation | `SyntheticPose` (ground-truth passthrough) | RTMPose (ONNX→TensorRT); BlazePose on budget tier |
| C | Action scoring | `KinematicConcealmentClassifier` (reach-then-stow features) | ST-GCN / PoseC3D trained on Phase 0 data |
| D | Object/context detection | **Not implemented** (interface reserved) | Fine-tuned YOLO: bag/cart/shelf/hand classes |
| E | Rule engine | `RuleEngine`: zone polygons, dwell, employee-uniform suppression | Same + gesture-sequence and repetition rules |
| F | Fusion + tiering | `FusionEngine`: fixed logistic, N-of-M hysteresis, LOG/SOFT/ALERT tiers | Learned LightGBM/MLP meta-model, calibrated |

## Contracts that must not break

1. **Keypoints only after stage B.** Downstream stages consume `PoseSample`
   (normalized keypoints), never pixels. The only pixel path out of the edge
   box is the ring-buffer clip attached to ALERT-tier events.
2. **Every scored window becomes a `DetectionEvent`**, including LOG tier.
   The active-learning selector depends on confident negatives existing.
3. **Suppression wins.** If the rule engine sets `suppressed`, fusion may not
   emit above LOG regardless of score. Employee suppression keys on
   `Detection.is_employee` (a uniform/badge visual cue) — never identity
   (blueprint §3.4). A suppressed window is still recorded in the hysteresis
   history as non-positive, so a track dwelling in a suppressed zone *decays*
   its history rather than freezing stale positives that would fire the instant
   it leaves the zone.
4. **Hysteresis before escalation.** A single positive window never alerts;
   `FusionEngine.hysteresis_n` of the last `hysteresis_m` must be positive.
5. **Per-track state is released on track death.** `EdgePipeline._release_track`
   is called for every id in `IoUTracker.dropped_ids`, clearing the pose
   window, stride counter, actor map, and the rule/fusion per-track state.
   Without this the process leaks one deque + several dict entries per shopper
   forever — do not add new per-track dicts without wiring them into
   `_release_track`.
6. **Alert clips are extracted with a delay.** Clip extraction for an ALERT is
   deferred by `clip_post_roll_s` (via `_pending_alerts`), because the post-roll
   frames don't exist in the ring buffer at decision time. `finalize()` flushes
   any alert still awaiting post-roll at end of stream/shift — callers driving
   the pipeline to completion must call it.

## Kinematic classifier: known limits (read before tuning)

The Phase 1 classifier scores one signature: arm extension (reach) followed by
a sustained wrist-at-hip dwell (stow). Known blind spots, accepted for MVP:

- Concealment into a held bag away from the hip (needs stage D bag context).
- Two-person handoffs (needs multi-track reasoning).
- The stow threshold (`stow_gap_threshold=0.03`) must stay tighter than the
  natural hands-at-sides hang distance (~0.045 normalized) — this was a real
  bug caught in testing; see `tests/test_pipeline_units.py::test_browsing_scores_low`.

These are model-replacement work (Phase 0 data → trained ST-GCN), not
threshold-tuning work. Do not chase them with heuristics.

**Sliding-window overlap and hysteresis.** With `window_size=20` and
`window_stride=5`, consecutive scored windows share 15 frames, so a single
sustained gesture is intentionally re-scored across several overlapping
windows — that is what lets `hysteresis_n` positives accumulate. The
anti-flicker guarantee therefore rests on the *action classifier's own*
temporal requirement (`min_stow_frames`): a few-frame pose glitch never scores
high enough to count as a positive window in the first place. If a future
learned stage C is noisier per-window than the kinematic one, raise
`hysteresis_n` or `window_stride` so independent (non-overlapping) evidence is
required before escalation.

## Swapping in a real backend

Each stage is a Protocol; a real backend replaces the synthetic one via
`EdgePipeline(detector=..., pose=..., action=...)`. Rules for new backends:

- Detector outputs normalized `BBox` + confidence; person class only.
- Pose backends map their skeleton down to the 6-point `Keypoint` set
  (shoulders, wrists, hips) at minimum; extra points are ignored until the
  trained stage C lands.
- Action backends implement `score_window(samples) -> ActionScore | None`,
  returning a calibrated [0,1] score.
