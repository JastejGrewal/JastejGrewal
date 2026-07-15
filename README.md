# Sentinel — Privacy-First Retail Theft-Gesture Detection

Phase 1 MVP implementing the architecture in [`docs/veesion-clone-blueprint.md`](docs/veesion-clone-blueprint.md):
an edge pipeline that watches a store's **existing** CCTV cameras for theft gestures
(concealment, bag-stuffing) and alerts staff in real time — **no facial recognition,
no biometric identity, skeleton/kinematics only**.

## What's implemented (Phase 1 scope, §4.7 of the blueprint)

| Component | Module | Status |
|---|---|---|
| Camera discovery: ONVIF WS-Discovery + vendor RTSP URL-pattern fallback (Hikvision/Dahua/Uniview OEM families) — blueprint §4.3a | `sentinel/edge/discovery/` | ✅ |
| Person detection + tracking (pluggable backend; synthetic default, Ultralytics optional) — stage A | `sentinel/edge/pipeline/detector.py`, `tracker.py` | ✅ |
| Pose estimation (pluggable; synthetic default) — stage B | `sentinel/edge/pipeline/pose.py` | ✅ |
| Kinematic concealment classifier (placeholder for ST-GCN; same interface) — stage C | `sentinel/edge/pipeline/action.py` | ✅ |
| Zone/dwell/sequence rule engine — stage E | `sentinel/edge/pipeline/rules.py` | ✅ |
| Fusion + temporal hysteresis + confidence tiers — stage F | `sentinel/edge/pipeline/fusion.py` | ✅ |
| Pre/post-roll ring buffer for alert clips | `sentinel/edge/pipeline/ringbuffer.py` | ✅ |
| Offline-tolerant outbox (SQLite queue, batch sync on reconnect) — §4.3 Phase 1 requirement | `sentinel/edge/outbox.py` | ✅ |
| Alert publishers (webhook to cloud, stdout; MQTT optional) | `sentinel/edge/publisher.py` | ✅ |
| Cloud backend: alerts / feedback / events API + live dashboard | `sentinel/cloud/` | ✅ |
| Active-learning review-queue prioritization — §4.2 | `sentinel/cloud/active_learning.py` | ✅ |
| End-to-end demo (synthetic store: normal shopper vs. concealment actor) | `sentinel/edge/demo.py` | ✅ |

| Real video ingestion (OpenCV file/RTSP decode) | `sentinel/edge/ingest/video.py` | ✅ |
| Real person detection: OpenCV HOG (no weights download) — stage A | `sentinel/edge/pipeline/detector.py` `HogDetector` | ✅ |
| Real neural detection + pose: YOLO-pose (COCO-17 → 6-keypoint) — stages A+B | `sentinel/edge/pipeline/pose_yolo.py` | ✅ (needs weights) |
| Run the pipeline on real video | `sentinel/edge/run_video.py` | ✅ |
| **Trainable action model** (temporal CNN over skeleton windows, ONNX export) — stage C | `sentinel/ml/model.py`, `onnx_classifier.py` | ✅ |
| Synthetic training data + frozen golden eval set — §4.5 | `sentinel/ml/dataset.py`, `features.py` | ✅ |
| Model registry + golden-set-gated promotion — §4.2 | `sentinel/ml/registry.py` | ✅ |
| Shadow deployment (candidate vs production) — §4.2 | `sentinel/ml/shadow.py` | ✅ |
| Canary rollout: deterministic camera slice, auto-rollback — §4.2 | `sentinel/ml/canary.py` | ✅ |
| Self-training loop: feedback → retrain → gate — §4.2 | `sentinel/ml/retrain.py` | ✅ |
| Model OTA: cloud serves production ONNX, edge pulls + hot-swaps — §4.6 | `sentinel/cloud/app.py` model endpoints, `sentinel/edge/model_sync.py` | ✅ |

Object/context detection (stage D) and the appearance-model branch are Phase 3 scope
and are stubbed at the interface level only.

### Training the learned model and the self-training loop

The action model is a real neural net trained in-repo (no downloads — training is
local):

```bash
pip install -e ".[train]"                    # torch + onnx (CPU is fine)

# Phase 0: train the initial model, evaluate on the frozen golden set, register + promote
python -m sentinel.ml.train_cli --registry ./model_registry

# run the pipeline with the LEARNED model instead of the kinematic stand-in:
#   EdgePipeline(action=OnnxActionClassifier("model_registry/models/action-v1.onnx", 20))
```

The **self-training loop** (`sentinel/ml/retrain.py`) closes the circle: every alert
carries the skeleton `pose_trace` that produced it; when an LP reviewer confirms or
rejects it on the dashboard, that trace + verdict becomes one labeled example.
`retrain()` merges human-labeled production data with the synthetic base set, trains a
candidate, evaluates it on the **frozen golden set**, and only promotes it if it clears
the gate (beats the incumbent's accuracy, doesn't raise the false-positive rate). Guards
from blueprint §4.2 are enforced in code: `unsure` verdicts never become labels, the
golden set is never sourced from feedback, and a candidate is registered but not promoted
unless it passes the gate.

### Running on real video

The pipeline runs on real decoded video, not just synthetic actors:

```bash
pip install -e ".[dev]"                                  # opencv + scikit-image

# make a real .mp4 (composites a real person photo — no download needed)
python -m sentinel.edge.render_demo_video --out /tmp/store.mp4

# real decode -> real HOG person detection -> tracker -> pipeline
python -m sentinel.edge.run_video --source /tmp/store.mp4 --backend hog
```

Two real perception backends, chosen by what your environment can reach:

- **`hog`** — OpenCV's built-in HOG person detector. Real CV, **no model
  download**, so it runs anywhere. It has no pose model, so it exercises
  *decode → detect → track → pipeline* on real pixels but not the pose-dependent
  action/alert stages.
- **`yolo-pose`** — a real neural net (Ultralytics YOLO-pose) that does person
  detection **and** COCO-17 pose in one pass, running the **full** pipeline
  (incl. gesture/action/alerts) on real pixels. It needs the model weights,
  which are fetched from the vendor's host on first use — available on any
  network with normal outbound access. The COCO-17 → 6-keypoint mapping is
  unit-tested independently of the weights (`test_real_perception.py`).

Point `--source` at an `rtsp://…` URL (resolved via the discovery adapter in
§4.3a) to run against a real camera instead of a file.

## Quickstart

```bash
pip install -e ".[dev]"

# run the test suite
pytest

# terminal 1: start the cloud backend + dashboard (http://localhost:8000)
uvicorn sentinel.cloud.app:app --port 8000

# terminal 2: run the end-to-end synthetic demo against it
python -m sentinel.edge.demo --cloud-url http://localhost:8000
```

The demo simulates a store with two shoppers — one browsing normally, one performing
a concealment gesture. The concealment actor should produce a high-tier alert (visible
on the dashboard at `http://localhost:8000`); the normal shopper should not. Confirm or
reject the alert on the dashboard to exercise the feedback loop that Phase 2's
active-learning retraining will consume.

To probe a real network for cameras (ONVIF discovery + vendor URL patterns):

```bash
python -m sentinel.edge.discovery.cli --subnet 192.168.1.0/24
```

## Design principles carried from the blueprint

- **Privacy by design**: the pipeline reasons over skeleton keypoints; raw frames stay
  on the edge except short flagged clips. No identity features anywhere in the codebase.
- **Pluggable inference**: every model stage is an interface with a synthetic backend
  (used in tests/demo) and optional real backends (`pip install ".[ml]"`), so the
  pipeline architecture is exercised end-to-end without a GPU.
- **Offline-first edge**: alerts and events queue durably through connectivity loss and
  batch-sync on reconnect (blueprint §4.3 — a Phase 1 requirement, not an afterthought).

## Project status

**The software vertical is complete and verified end-to-end** (100 passing tests):
camera discovery → real video decode → real detection/tracking → learned
concealment model → rules/fusion → offline-tolerant sync → cloud API + dashboard
→ human feedback → golden-set-gated retraining → shadow/canary rollout → OTA back
to the edge. The full loop has been exercised live: a model trained from scratch,
distributed to an edge box over the API, alerting on a concealment scenario,
confirmed by a reviewer, and a retrained successor passing the gate and taking
over production.

What separates this from a deployed product is **the physical world, not code**:
real theft footage to replace the synthetic training generator (`sentinel/ml/dataset.py`
is the only module that changes), YOLO-pose weights on a network with normal
egress, edge hardware (Jetson/Hailo) with a pilot store, and the legal/DPIA
work laid out in `docs/veesion-clone-blueprint.md` §5.

## Repository layout

```
docs/                      strategy blueprint + architecture specs
sentinel/common/           shared event schemas (edge <-> cloud contract)
sentinel/edge/             everything that runs in the store
sentinel/cloud/            alert routing, feedback store, review queue, dashboard
tests/                     pytest suite (unit + end-to-end)
ceramic-coating-campaign/  unrelated pre-existing marketing docs (untouched)
```
