"""End-to-end: synthetic store -> edge pipeline -> outbox -> cloud API -> feedback.

This is the Phase 1 acceptance test in miniature: the concealment actor must
alert, the browsing shopper must not, the employee restocker must be
suppressed, and the offline outbox must batch-sync into the cloud.
"""

import pytest
from fastapi.testclient import TestClient

import sentinel.cloud.app as cloud_app
from sentinel.cloud.store import CloudStore
from sentinel.edge.outbox import Outbox
from sentinel.edge.pipeline.orchestrator import EdgePipeline, PipelineConfig
from sentinel.edge.pipeline.rules import RuleEngine, Zone
from sentinel.edge.scenario import store_scenario

FULL_FLOOR = Zone(
    name="floor", kind="merchandise",
    polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(cloud_app, "_store", CloudStore())
    return TestClient(cloud_app.app)


def _run_pipeline(include_employee=False):
    pipeline = EdgePipeline(
        config=PipelineConfig(),
        rules=RuleEngine(zones=[FULL_FLOOR]),
        outbox=Outbox(),
    )
    all_events = []
    for frame in store_scenario(n_frames=120, include_employee=include_employee):
        all_events.extend(pipeline.process_frame(frame))
    return pipeline, all_events


def _actor_of(pipeline, track_id):
    return pipeline._track_actor.get(track_id, "?")


def test_thief_alerts_browser_does_not():
    pipeline, events = _run_pipeline()
    alerts = [e for e in events if e.tier == "alert"]
    assert alerts, "concealment actor should produce at least one ALERT"
    alert_actors = {_actor_of(pipeline, e.track_id) for e in alerts}
    assert alert_actors == {"shopper_thief"}
    # The browser generated windows, but none escalated.
    browser_events = [
        e for e in events if _actor_of(pipeline, e.track_id) == "shopper_browser"
    ]
    assert browser_events, "browser should still be scored (LOG telemetry)"
    assert all(e.tier == "log" for e in browser_events)


def test_alerts_carry_clips():
    _pipeline, events = _run_pipeline()
    alerts = [e for e in events if e.tier == "alert"]
    assert all(e.clip is not None and e.clip.frame_count > 0 for e in alerts)
    logs = [e for e in events if e.tier == "log"]
    assert all(e.clip is None for e in logs)


def test_employee_restock_suppressed():
    pipeline, events = _run_pipeline(include_employee=True)
    employee_events = [
        e for e in events if _actor_of(pipeline, e.track_id) == "employee_restock"
    ]
    assert employee_events, "employee should be scored"
    assert all(e.tier == "log" for e in employee_events)
    assert all("employee_suppress" in e.rule_flags for e in employee_events)


def test_full_edge_to_cloud_flow(client):
    pipeline, _events = _run_pipeline()

    # Simulate an outage: first drain fails entirely, events stay queued.
    result = pipeline.outbox.drain(lambda e: False, now=0.0)
    assert result.remaining > 0

    # Reconnect: publish everything to the cloud API.
    def publish(event):
        r = client.post("/api/v1/events", json=event.to_dict())
        return r.status_code == 201

    result = pipeline.outbox.drain(publish, batch_size=1000, now=10_000.0)
    assert result.remaining == 0 and result.sent > 0

    alerts = client.get("/api/v1/alerts").json()
    assert len(alerts) >= 1

    # LP staff confirms the first alert; it leaves the review queue.
    event_id = alerts[0]["event_id"]
    r = client.post(
        f"/api/v1/alerts/{event_id}/feedback",
        json={"verdict": "confirmed", "reason": "clip shows concealment"},
    )
    assert r.status_code == 200
    queue_ids = [i["event"]["event_id"] for i in client.get("/api/v1/review-queue").json()]
    assert event_id not in queue_ids

    stats = client.get("/api/v1/stats").json()
    assert stats["feedback_by_verdict"].get("confirmed") == 1
