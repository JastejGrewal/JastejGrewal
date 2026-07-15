# Continuous Learning Policy

The blueprint (§4.2) calls this "the document most likely to prevent a costly
production mistake." It governs how production feedback becomes training data
and how retrained models reach the fleet. Phase 1 implements the *feedback
capture* and *review prioritization* halves; retraining/promotion arrives in
Phase 2 and MUST follow the gates below.

## What exists today

- **Label source**: LP staff confirm/false-alarm/unsure dispositions via
  `POST /api/v1/alerts/{id}/feedback` (dashboard buttons). Stored in the
  `feedback` table keyed to the event, which carries the `pose_trace` (the
  skeleton window that produced the decision — keypoints only, no identity).
- **Review queue**: `GET /api/v1/review-queue` ranks unreviewed events by
  boundary confidence, novelty vs. labeled centroids, stratified sampling of
  confident negatives, and unreviewed-alert priority
  (`sentinel/cloud/active_learning.py`).
- **Telemetry completeness**: LOG-tier events are stored alongside alerts so
  negatives exist to sample.
- **Trainable model** (`sentinel/ml/`): a temporal CNN over skeleton windows,
  trained on synthetic data (`dataset.py`), exported to ONNX, and served via
  `OnnxActionClassifier` behind the same interface as the kinematic stand-in.
- **Frozen golden set** (`dataset.golden_set`, fixed seed) — built once, never
  sourced from feedback.
- **Registry + gate** (`registry.py`): versioned ONNX artifacts with lineage, a
  `production` pointer, and `golden_gate()` enforcing the accuracy floor +
  no-FPR-regression rule before promotion.
- **Shadow runner** (`shadow.py`): scores a candidate alongside production on
  live windows, logging agreement/divergence without affecting alerts.
- **Retraining** (`retrain.py`): feedback → labeled windows → merge with
  synthetic base → train → golden-gate → register (+ promote if gated). The
  §4.2 guards below are enforced in code and covered by `tests/test_ml.py`.

## Non-negotiable gates for Phase 2 retraining (from blueprint §4.2)

1. **Only human-confirmed labels enter the training set.** Weak signals (EAS
   gates, POS reconciliation) are auxiliary calibration data, down-weighted,
   never auto-promoted to labels.
2. **The golden evaluation set is frozen and feedback-free.** It is curated
   and double-annotated before the loop goes live and is never sampled from
   production feedback. A retrained model must beat the incumbent on the
   golden set — not merely on live feedback — before any promotion step.
3. **Promotion ladder**: shadow (predictions logged, no alerts) → canary
   (~5% of cameras, auto-rollback triggers) → staged rollout (25% → 100%),
   each step gated on golden-set metrics plus live precision/recall deltas.
4. **Per-tenant isolation**: store-specific adaptation happens in adapters/
   heads, never by fine-tuning the shared base on one tenant's feedback.
   One store rubber-stamping "false alarm" must not corrupt the fleet.
5. **Batch caps and lineage**: rate/diversity caps per store/camera per
   retraining batch; every batch traceable to a versioned data snapshot so a
   poisoned batch can be identified and rolled back.
6. **Bias audit before promotion**: FP/TP rates segmented by store and region
   (and clothing-style proxies, carefully) must not regress. This is the
   operational hedge against the FTC/Rite-Aid theory of harm (blueprint §5).

## Rollout ladder — implemented

The full §4.2 promotion ladder now exists in code:

1. **Golden gate** (`registry.golden_gate`): absolute accuracy floor + no
   accuracy loss vs. incumbent + no false-positive-rate increase beyond
   tolerance. A candidate that fails is registered (for lineage) but never
   promoted.
2. **Shadow** (`shadow.ShadowRunner`): candidate scores live windows alongside
   production; only agreement/divergence is recorded, alerts are unaffected.
3. **Canary** (`canary.CanaryController`): deterministic hash-of-camera-id
   slice (default 5%) alerts on the candidate; live confirm/false-alarm rates
   are compared canary-vs-control with an evidence floor, an early-rollback
   trigger for egregious noise, and a false-alarm-rate regression bound.
   `unsure` dispositions contribute no evidence, mirroring the label rule.
4. **OTA distribution** (`cloud/app.py` model endpoints + `edge/model_sync.py`):
   the edge polls the cloud's production-model endpoint, downloads on version
   change, verifies the artifact loads before swapping, and keeps the current
   model on any failure — a box that never syncs still detects with whatever
   classifier it booted with.

## Ensemble disagreement (Phase 3)

When the appearance branch lands, add branch-disagreement as a first-class
review-queue signal — it is the highest-information sampler and is already
stubbed in the queue-item `reasons` design.
