"""Regression tests for issues found in the post-implementation code audit.

Each test pins a specific fix so it can't silently regress.
"""

import pytest
from fastapi.testclient import TestClient

import sentinel.cloud.app as cloud_app
from sentinel.cloud.active_learning import prioritize
from sentinel.cloud.store import CloudStore
from sentinel.common.events import AlertTier, DetectionEvent
from sentinel.edge.outbox import Outbox
from sentinel.edge.pipeline.action import ActionScore
from sentinel.edge.pipeline.fusion import FusionEngine
from sentinel.edge.pipeline.orchestrator import EdgePipeline, PipelineConfig
from sentinel.edge.pipeline.rules import RuleEngine, RuleVerdict, Zone
from sentinel.edge.pipeline.tracker import IoUTracker
from sentinel.edge.pipeline.types import BBox, Detection
from sentinel.edge.scenario import store_scenario

FULL_FLOOR = Zone(
    name="floor", kind="merchandise",
    polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
)


# --- track-state leak: per-track state is released when a track ages out -----

def test_tracker_reports_dropped_ids():
    tracker = IoUTracker(max_misses=2)
    tracker.update([Detection(bbox=BBox(0.5, 0.5, 0.1, 0.2), confidence=0.9)], ts=0.0)
    assert tracker.dropped_ids == []
    for i in range(3):
        tracker.update([], ts=0.1 * (i + 1))
    assert tracker.dropped_ids == [1]


def test_pipeline_releases_state_for_dead_tracks():
    pipeline = EdgePipeline(config=PipelineConfig(), rules=RuleEngine(zones=[FULL_FLOOR]), outbox=Outbox())
    # One thief appears, gets scored, then the scenario ends and the track
    # should be fully forgotten once it ages out.
    for frame in store_scenario(n_frames=60):
        pipeline.process_frame(frame)
    live_before = set(pipeline._pose_windows)
    assert live_before, "expected live per-track state during the scenario"
    # Feed empty frames until every track ages out of the tracker.
    for i in range(40):
        pipeline.process_frame(type(frame)(camera_id="cam-01", ts=6.0 + i * 0.1, index=1000 + i))
    pipeline.finalize()
    assert pipeline._pose_windows == {}
    assert pipeline._frames_since_score == {}
    assert pipeline._track_actor == {}
    assert pipeline.rules._tracks == {}
    assert pipeline.fusion._history == {}


# --- deferred clip: an ALERT clip contains post-roll frames -------------------

def test_alert_clip_contains_post_roll():
    pipeline = EdgePipeline(config=PipelineConfig(), rules=RuleEngine(zones=[FULL_FLOOR]), outbox=Outbox())
    alerts = []
    for frame in store_scenario(n_frames=120):
        alerts.extend(e for e in pipeline.process_frame(frame) if e.tier == "alert")
    alerts.extend(e for e in pipeline.finalize() if e.tier == "alert")
    assert alerts, "expected the concealment actor to alert"
    for alert in alerts:
        assert alert.clip is not None
        # end_ts must extend past the event window end: post-roll is present.
        assert alert.clip.end_ts > alert.window_end_ts


# --- fusion hysteresis: suppression decays history, no stale instant alert ---

def test_suppression_decays_hysteresis_history():
    fusion = FusionEngine(hysteresis_n=2, hysteresis_m=4)
    hot = ActionScore(track_id=1, score=0.95, window_start_ts=0, window_end_ts=2)
    merch = RuleVerdict(flags=["in_merchandise_zone:a"])
    suppressed = RuleVerdict(flags=["in_checkout_zone:till"], suppressed=True)

    # Build two positives, then dwell suppressed long enough to flush history.
    fusion.decide(hot, merch)
    fusion.decide(hot, merch)
    for _ in range(4):
        fusion.decide(hot, suppressed)
    # History is now all-negative; the next hot window alone must NOT alert.
    d = fusion.decide(hot, merch)
    assert d.tier != AlertTier.ALERT


# --- outbox: thread-safe connection + dead-letter after max attempts ---------

def test_outbox_dead_letters_poison_pill():
    outbox = Outbox(base_backoff_s=0.0, max_attempts=3)
    outbox.enqueue(DetectionEvent(store_id="s", camera_id="c", track_id=1, tier="alert",
                                  fused_score=0.9, action_score=0.8, event_id="poison"))
    dead_total = 0
    for _ in range(5):
        result = outbox.drain(lambda e: False, now=1e9)
        dead_total += result.dead_lettered
    assert dead_total == 1
    assert outbox.pending_count() == 0
    assert outbox.dead_letter_count() == 1


def test_outbox_deletes_delivered_rows():
    outbox = Outbox()
    outbox.enqueue(DetectionEvent(store_id="s", camera_id="c", track_id=1, tier="log",
                                  fused_score=0.1, action_score=0.1, event_id="e1"))
    outbox.drain(lambda e: True)
    # Delivered row is gone, so a re-enqueue of the same id can be accepted again
    # only if truly new; here we just assert the table isn't accumulating.
    (n,) = outbox._conn.execute("SELECT COUNT(*) FROM outbox").fetchone()
    assert n == 0


# --- cloud API guards --------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(cloud_app, "_store", CloudStore())
    return TestClient(cloud_app.app)


def _event(event_id="e1", tier="alert", fused=0.9):
    return {"event_id": event_id, "store_id": "s1", "camera_id": "cam-01",
            "track_id": 7, "tier": tier, "fused_score": fused, "action_score": 0.8}


def test_negative_limit_rejected(client):
    client.post("/api/v1/events", json=_event())
    assert client.get("/api/v1/events", params={"limit": -1}).status_code == 422
    assert client.get("/api/v1/alerts", params={"limit": -1}).status_code == 422


def test_duplicate_ingest_returns_200(client):
    assert client.post("/api/v1/events", json=_event()).status_code == 201
    r = client.post("/api/v1/events", json=_event())
    assert r.status_code == 200 and r.json()["inserted"] is False


def test_boundary_center_zero_rejected():
    with pytest.raises(ValueError):
        prioritize([], [], boundary_center=0.0)


# --- XSS: hostile event_id cannot break out of the dashboard button ----------

def test_dashboard_uses_data_attributes_not_inline_onclick():
    # The fix replaces inline onclick string interpolation (defeated by HTML
    # entity decoding) with data-attributes + delegation.
    from pathlib import Path
    html = (Path(cloud_app.__file__).parent / "static" / "dashboard.html").read_text()
    assert "data-event-id" in html
    assert "onclick=\"feedback(" not in html


# --- employee suppression rides on detection.is_employee, not a name prefix --

def test_employee_flag_comes_from_detection():
    from sentinel.edge.pipeline.detector import SyntheticDetector
    from sentinel.edge.pipeline.types import Frame
    from sentinel.edge.scenario import employee_restock_actor, concealment_actor

    detector = SyntheticDetector()
    frame = Frame(camera_id="c", ts=0.0, index=0, synthetic_actors=[
        concealment_actor("shopper_thief", 30),
        employee_restock_actor("employee_restock", 30),
    ])
    dets = {d.actor_ref.actor_id: d.is_employee for d in detector.detect(frame)}
    assert dets["shopper_thief"] is False
    assert dets["employee_restock"] is True
