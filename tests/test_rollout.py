"""Tests for the canary controller and the OTA model-distribution loop."""

import json

import pytest

from sentinel.ml.canary import CanaryController, CanaryVerdict, in_canary


# --- canary assignment --------------------------------------------------------

def test_assignment_deterministic():
    assert in_canary("cam-7", 0.5, "s") == in_canary("cam-7", 0.5, "s")


def test_assignment_fraction_roughly_respected():
    n = 2000
    hits = sum(in_canary(f"cam-{i}", 0.1, "salt") for i in range(n))
    assert 0.05 * n < hits < 0.15 * n  # ~10% with slack


def test_assignment_bounds():
    assert not in_canary("cam-1", 0.0)
    assert in_canary("cam-1", 1.0)
    with pytest.raises(ValueError):
        in_canary("cam-1", 1.5)


# --- canary judgement ----------------------------------------------------------

def _controller(**kw):
    return CanaryController(candidate_version="action-v2", fraction=0.5, salt="t", **kw)


def _feed(ctrl, group_camera, confirmed, false_alarms):
    for _ in range(confirmed):
        ctrl.record_feedback(group_camera, "confirmed")
    for _ in range(false_alarms):
        ctrl.record_feedback(group_camera, "false_alarm")


def _camera_in(ctrl, group):
    for i in range(1000):
        cam = f"cam-{i}"
        if ctrl.group_for(cam) == group:
            return cam
    raise AssertionError(f"no camera found for group {group}")


def test_continue_until_evidence_floor():
    ctrl = _controller(min_reviewed_per_group=20)
    verdict, _ = ctrl.evaluate()
    assert verdict == CanaryVerdict.CONTINUE


def test_promote_ready_when_no_regression():
    ctrl = _controller(min_reviewed_per_group=10)
    _feed(ctrl, _camera_in(ctrl, "canary"), confirmed=9, false_alarms=1)
    _feed(ctrl, _camera_in(ctrl, "control"), confirmed=9, false_alarms=1)
    verdict, reason = ctrl.evaluate()
    assert verdict == CanaryVerdict.PROMOTE_READY, reason


def test_rollback_on_far_regression():
    ctrl = _controller(min_reviewed_per_group=10, max_far_increase=0.1)
    _feed(ctrl, _camera_in(ctrl, "canary"), confirmed=5, false_alarms=5)   # FAR 0.5
    _feed(ctrl, _camera_in(ctrl, "control"), confirmed=9, false_alarms=1)  # FAR 0.1
    verdict, reason = ctrl.evaluate()
    assert verdict == CanaryVerdict.ROLLBACK
    assert "exceeds" in reason


def test_early_rollback_on_egregious_canary():
    ctrl = _controller(min_reviewed_per_group=10)
    _feed(ctrl, _camera_in(ctrl, "canary"), confirmed=1, false_alarms=19)  # FAR 0.95
    # control has no evidence at all — early trigger must fire anyway
    verdict, _ = ctrl.evaluate()
    assert verdict == CanaryVerdict.ROLLBACK


def test_unsure_contributes_no_evidence():
    ctrl = _controller(min_reviewed_per_group=1)
    cam = _camera_in(ctrl, "canary")
    for _ in range(50):
        ctrl.record_feedback(cam, "unsure")
    verdict, _ = ctrl.evaluate()
    assert verdict == CanaryVerdict.CONTINUE


# --- OTA model distribution -----------------------------------------------------

onnxruntime = pytest.importorskip("onnxruntime")
torch = pytest.importorskip("torch")
pytest.importorskip("onnxscript")

from fastapi.testclient import TestClient  # noqa: E402

import sentinel.cloud.app as cloud_app  # noqa: E402
from sentinel.cloud.store import CloudStore  # noqa: E402
from sentinel.edge.model_sync import ModelSync  # noqa: E402
from sentinel.ml.dataset import generate_dataset, golden_set  # noqa: E402
from sentinel.ml.registry import ModelRegistry, evaluate_onnx  # noqa: E402


@pytest.fixture(scope="module")
def populated_registry(tmp_path_factory):
    from sentinel.ml.model import export_onnx, train_model

    root = tmp_path_factory.mktemp("registry")
    X, y = generate_dataset(n_per_class=400, window_size=20, seed=0)
    model, _ = train_model(X, y, window_size=20, epochs=80, seed=0)
    onnx_path = str(root / "trained.onnx")
    export_onnx(model, 20, onnx_path)

    registry = ModelRegistry(str(root / "reg"))
    Xg, yg = golden_set(20, n_per_class=50)
    metrics = evaluate_onnx(onnx_path, Xg, yg)
    version = registry.register(onnx_path, metrics, lineage={"parent": None})
    registry.promote(version)
    return str(root / "reg")


@pytest.fixture()
def client(monkeypatch, populated_registry):
    monkeypatch.setattr(cloud_app, "_store", CloudStore())
    monkeypatch.setattr(cloud_app, "_registry_root", populated_registry)
    return TestClient(cloud_app.app)


def test_model_endpoints_serve_production(client):
    info = client.get("/api/v1/models/production")
    assert info.status_code == 200
    assert info.json()["version"] == "action-v1"
    artifact = client.get("/api/v1/models/production/artifact")
    assert artifact.status_code == 200
    assert len(artifact.content) > 1000  # a real ONNX, not an error body


def test_model_endpoints_404_without_registry(monkeypatch):
    monkeypatch.setattr(cloud_app, "_registry_root", None)
    c = TestClient(cloud_app.app)
    assert c.get("/api/v1/models/production").status_code == 404


def test_edge_ota_round_trip(client, tmp_path):
    """Cloud registry -> edge sync -> working classifier: the loop closes."""
    def transport(url: str) -> bytes:
        r = client.get(url.replace("http://cloud", ""))
        assert r.status_code == 200
        return r.content

    sync = ModelSync("http://cloud", cache_dir=str(tmp_path / "cache"), transport=transport)
    assert sync.current_version() is None
    result = sync.sync()
    assert result is not None
    version, path = result
    assert version == "action-v1"

    # Re-sync with same version: no-op.
    assert sync.sync() is None
    assert sync.current_version() == "action-v1"

    # The pulled model actually classifies.
    clf = sync.build_classifier(window_size=20)
    import numpy as np
    from sentinel.ml.dataset import _make_window

    rng = np.random.default_rng(5)
    conceal = clf.score_window(_make_window("conceal", 20, rng))
    browse = clf.score_window(_make_window("browse", 20, rng))
    assert conceal.score > 0.5 > browse.score


def test_edge_keeps_model_when_cloud_unreachable(tmp_path):
    def dead_transport(url):
        raise OSError("network down")

    sync = ModelSync("http://cloud", cache_dir=str(tmp_path / "c"), transport=dead_transport)
    assert sync.sync() is None
    assert sync.build_classifier(20) is None  # never synced -> caller keeps default


def test_corrupt_artifact_rejected(client, tmp_path):
    calls = {"n": 0}

    def transport(url: str) -> bytes:
        if url.endswith("/artifact"):
            return b"not an onnx model"
        r = client.get(url.replace("http://cloud", ""))
        return r.content

    sync = ModelSync("http://cloud", cache_dir=str(tmp_path / "c"), transport=transport)
    assert sync.sync() is None
    assert sync.current_version() is None  # corrupt download never became current