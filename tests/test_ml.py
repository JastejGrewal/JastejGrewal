"""ML-layer tests: featurization, dataset, registry gating, and (torch-gated)
training + learned-model end-to-end.

The pure-numpy tests always run; training tests are skipped where torch/onnx
aren't installed (the `[train]` extra).
"""

import numpy as np
import pytest

from sentinel.ml.dataset import generate_dataset, golden_set
from sentinel.ml.features import N_FEATURES, window_to_features
from sentinel.ml.registry import EvalMetrics, ModelRegistry, golden_gate
from sentinel.edge.pipeline.types import Keypoint, PoseSample


# --- featurization (pure) ----------------------------------------------------

def _flat_sample(track=0, ts=0.0):
    kp = [(0.5, 0.5)] * 6
    kp[Keypoint.LEFT_SHOULDER] = (0.45, 0.4)
    kp[Keypoint.RIGHT_SHOULDER] = (0.55, 0.4)
    return PoseSample(track_id=track, ts=ts, keypoints=kp)


def test_features_shape_and_padding():
    feats = window_to_features([_flat_sample()], window_size=20)
    assert feats.shape == (20, N_FEATURES)
    # short window is left-padded by repeating the first frame
    assert np.allclose(feats[0], feats[-1])


def test_features_translation_invariant():
    a = _flat_sample()
    shifted = PoseSample(track_id=0, ts=0.0, keypoints=[(x + 0.2, y + 0.1) for (x, y) in a.keypoints])
    fa = window_to_features([a] * 20, 20)
    fb = window_to_features([shifted] * 20, 20)
    assert np.allclose(fa, fb, atol=1e-5)


def test_empty_window_is_zeros():
    feats = window_to_features([], window_size=20)
    assert feats.shape == (20, N_FEATURES) and not feats.any()


# --- dataset -----------------------------------------------------------------

def test_dataset_balanced_and_shaped():
    X, y = generate_dataset(n_per_class=50, window_size=20, seed=1)
    assert X.shape == (100, 20, N_FEATURES)
    assert int((y == 1).sum()) == 50 and int((y == 0).sum()) == 50


def test_golden_set_is_deterministic():
    a = golden_set(20, n_per_class=30)
    b = golden_set(20, n_per_class=30)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


# --- gate logic (no model needed) --------------------------------------------

def _m(acc, fpr, rec=1.0, prec=1.0):
    return EvalMetrics(acc, prec, rec, fpr, 400)


def test_gate_rejects_below_floor():
    assert not golden_gate(_m(0.8, 0.01), None, min_accuracy=0.9).passed


def test_gate_accepts_good_first_model():
    assert golden_gate(_m(0.97, 0.01), None, min_accuracy=0.9).passed


def test_gate_rejects_accuracy_regression():
    baseline = _m(0.97, 0.01)
    assert not golden_gate(_m(0.95, 0.01), baseline).passed


def test_gate_rejects_fpr_increase():
    baseline = _m(0.97, 0.01)
    res = golden_gate(_m(0.97, 0.05), baseline, max_fpr_increase=0.02)
    assert not res.passed and any("FPR" in r for r in res.reasons)


def test_registry_promote_flow(tmp_path):
    reg = ModelRegistry(str(tmp_path / "reg"))
    # fake onnx artifact (registry only copies the file; promotion is metadata)
    fake = tmp_path / "m.onnx"
    fake.write_bytes(b"onnx-bytes")
    v1 = reg.register(str(fake), _m(0.95, 0.02), lineage={"parent": None})
    assert reg.production() is None
    reg.promote(v1)
    assert reg.production_version() == v1
    v2 = reg.register(str(fake), _m(0.98, 0.01), lineage={"parent": v1})
    reg.promote(v2)
    assert reg.production_version() == v2
    assert reg.get(v1)["stage"] == "archived"


# --- training + learned model end-to-end (torch-gated) -----------------------

torch = pytest.importorskip("torch")
onnxruntime = pytest.importorskip("onnxruntime")
pytest.importorskip("onnxscript")


@pytest.fixture(scope="module")
def trained_onnx(tmp_path_factory):
    from sentinel.ml.model import export_onnx, train_model

    X, y = generate_dataset(n_per_class=500, window_size=20, seed=0)
    model, report = train_model(X, y, window_size=20, epochs=80, seed=0)
    assert report.val_accuracy > 0.9
    path = str(tmp_path_factory.mktemp("m") / "action.onnx")
    export_onnx(model, 20, path)
    return path


def test_trained_model_beats_golden_gate(trained_onnx):
    from sentinel.ml.registry import evaluate_onnx

    Xg, yg = golden_set(20)
    metrics = evaluate_onnx(trained_onnx, Xg, yg)
    assert metrics.accuracy >= 0.9
    assert golden_gate(metrics, None).passed


def test_onnx_classifier_scores_gesture(trained_onnx):
    from sentinel.ml.onnx_classifier import OnnxActionClassifier
    from sentinel.ml.dataset import _make_window
    import numpy as np

    clf = OnnxActionClassifier(trained_onnx, window_size=20)
    rng = np.random.default_rng(7)
    conceal = clf.score_window(_make_window("conceal", 20, rng))
    browse = clf.score_window(_make_window("browse", 20, rng))
    assert conceal.score > 0.5 > browse.score


def test_learned_model_drives_pipeline_alert(trained_onnx):
    """The whole point: the LEARNED model, wired into the unchanged pipeline,
    alerts on the concealment actor and not the browser."""
    from sentinel.edge.outbox import Outbox
    from sentinel.edge.pipeline.orchestrator import EdgePipeline, PipelineConfig
    from sentinel.edge.pipeline.rules import RuleEngine, Zone
    from sentinel.ml.onnx_classifier import OnnxActionClassifier
    from sentinel.edge.scenario import store_scenario

    floor = Zone(name="floor", kind="merchandise",
                 polygon=[(0, 0), (1, 0), (1, 1), (0, 1)])
    pipeline = EdgePipeline(
        config=PipelineConfig(),
        action=OnnxActionClassifier(trained_onnx, window_size=20),
        rules=RuleEngine(zones=[floor]),
        outbox=Outbox(),
    )
    events = []
    for frame in store_scenario(n_frames=120):
        events.extend(pipeline.process_frame(frame))
    events.extend(pipeline.finalize())

    actor = pipeline._track_actor
    alerts = [e for e in events if e.tier == "alert"]
    assert alerts, "learned model should alert on the concealment actor"
    assert {actor.get(e.track_id) for e in alerts} == {"shopper_thief"}
    # alerts carry the pose trace that will become training data
    assert all(e.pose_trace and len(e.pose_trace) == 20 for e in alerts)


def test_retrain_loop_closes(tmp_path):
    """Feedback in the store -> retrain -> gated, registered candidate."""
    from sentinel.cloud.store import CloudStore
    from sentinel.ml.dataset import _make_window
    from sentinel.ml.registry import ModelRegistry
    from sentinel.ml.retrain import labeled_windows_from_feedback, retrain

    store = CloudStore()
    rng = np.random.default_rng(3)

    def _trace(kind):
        return [[[x, y] for (x, y) in s.keypoints] for s in _make_window(kind, 20, rng)]

    # Two human-labeled production examples with skeleton traces.
    store.insert_event({"event_id": "a", "store_id": "s", "camera_id": "c", "track_id": 1,
                        "tier": "alert", "fused_score": 0.9, "action_score": 0.9,
                        "pose_trace": _trace("conceal")})
    store.add_feedback("a", "confirmed", None, "lp")
    store.insert_event({"event_id": "b", "store_id": "s", "camera_id": "c", "track_id": 2,
                        "tier": "alert", "fused_score": 0.8, "action_score": 0.8,
                        "pose_trace": _trace("browse")})
    store.add_feedback("b", "false_alarm", None, "lp")

    # 'unsure' must never become a label.
    store.insert_event({"event_id": "c", "store_id": "s", "camera_id": "c", "track_id": 3,
                        "tier": "soft", "fused_score": 0.5, "action_score": 0.5,
                        "pose_trace": _trace("idle")})
    store.add_feedback("c", "unsure", None, "lp")

    Xf, yf = labeled_windows_from_feedback(store.labeled_examples(), 20)
    assert len(Xf) == 2 and set(yf.tolist()) == {0, 1}  # unsure dropped

    reg = ModelRegistry(str(tmp_path / "reg"))
    report = retrain(store, reg, window_size=20, synthetic_per_class=400, epochs=80, seed=0)
    assert report.n_feedback == 2
    assert report.version == "action-v1"
    assert report.candidate_metrics["accuracy"] >= 0.9
    assert report.promoted is True  # first good model auto-promotes
    assert reg.production_version() == "action-v1"
