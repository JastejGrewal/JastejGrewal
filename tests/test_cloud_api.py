import pytest
from fastapi.testclient import TestClient

import sentinel.cloud.app as cloud_app
from sentinel.cloud.store import CloudStore


@pytest.fixture()
def client(monkeypatch):
    store = CloudStore()
    monkeypatch.setattr(cloud_app, "_store", store)
    return TestClient(cloud_app.app)


def _event(event_id="e1", tier="alert", fused=0.9):
    return {
        "event_id": event_id, "store_id": "s1", "camera_id": "cam-01",
        "track_id": 7, "tier": tier, "fused_score": fused, "action_score": 0.8,
        "rule_flags": ["in_merchandise_zone:aisle-3"],
        "window_start_ts": 1.0, "window_end_ts": 3.0, "created_ts": 100.0,
        "clip": {"camera_id": "cam-01", "start_ts": 0.0, "end_ts": 6.0, "frame_count": 60},
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_and_list_alert(client):
    r = client.post("/api/v1/events", json=_event())
    assert r.status_code == 201 and r.json()["inserted"] is True
    alerts = client.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["event_id"] == "e1"
    assert alerts[0]["clip"]["frame_count"] == 60
    assert alerts[0]["feedback"] is None


def test_ingest_idempotent(client):
    client.post("/api/v1/events", json=_event())
    r = client.post("/api/v1/events", json=_event())
    assert r.json()["inserted"] is False
    assert len(client.get("/api/v1/alerts").json()) == 1


def test_ingest_validates_tier_and_score(client):
    bad = _event()
    bad["tier"] = "catastrophic"
    assert client.post("/api/v1/events", json=bad).status_code == 422
    bad = _event()
    bad["fused_score"] = 1.5
    assert client.post("/api/v1/events", json=bad).status_code == 422


def test_feedback_flow(client):
    client.post("/api/v1/events", json=_event())
    r = client.post(
        "/api/v1/alerts/e1/feedback",
        json={"verdict": "confirmed", "reviewer": "lp-1"},
    )
    assert r.status_code == 200
    alerts = client.get("/api/v1/alerts").json()
    assert alerts[0]["feedback"]["verdict"] == "confirmed"
    stats = client.get("/api/v1/stats").json()
    assert stats["feedback_by_verdict"] == {"confirmed": 1}


def test_feedback_unknown_event_404(client):
    r = client.post("/api/v1/alerts/nope/feedback", json={"verdict": "unsure"})
    assert r.status_code == 404


def test_events_filter_by_tier(client):
    client.post("/api/v1/events", json=_event("e1", tier="alert"))
    client.post("/api/v1/events", json=_event("e2", tier="log", fused=0.1))
    logs = client.get("/api/v1/events", params={"tier": "log"}).json()
    assert [e["event_id"] for e in logs] == ["e2"]


def test_review_queue_prioritizes_boundary_and_alerts(client):
    client.post("/api/v1/events", json=_event("boundary", tier="soft", fused=0.5))
    client.post("/api/v1/events", json=_event("confident-neg", tier="log", fused=0.02))
    client.post("/api/v1/events", json=_event("alert-1", tier="alert", fused=0.9))
    queue = client.get("/api/v1/review-queue").json()
    ids = [item["event"]["event_id"] for item in queue]
    # Unreviewed alert first, boundary case above confident negative.
    assert ids[0] == "alert-1"
    assert ids.index("boundary") < ids.index("confident-neg")


def test_reviewed_events_leave_queue(client):
    client.post("/api/v1/events", json=_event("e1"))
    client.post("/api/v1/alerts/e1/feedback", json={"verdict": "false_alarm"})
    assert client.get("/api/v1/review-queue").json() == []


def test_dashboard_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Loss Prevention Dashboard" in r.text
