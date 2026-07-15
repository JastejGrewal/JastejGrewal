"""Cloud API: event ingestion, alert routing, feedback, review queue, dashboard.

Run: uvicorn sentinel.cloud.app:app --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from sentinel.common.events import AlertTier, FeedbackVerdict

from .active_learning import prioritize
from .store import CloudStore

app = FastAPI(title="Sentinel Cloud", version="0.1.0")
_store = CloudStore(db_path=os.environ.get("SENTINEL_DB", ":memory:"))
# Model registry root for OTA distribution (§4.2 rollout / §4.6 "OTA push").
# Unset -> the model endpoints report 404 and edges keep their current model.
_registry_root = os.environ.get("SENTINEL_REGISTRY")


def get_store() -> CloudStore:
    return _store


def get_registry():
    if not _registry_root:
        return None
    from sentinel.ml.registry import ModelRegistry

    return ModelRegistry(_registry_root)


class ClipRefIn(BaseModel):
    camera_id: str
    start_ts: float
    end_ts: float
    frame_count: int


class EventIn(BaseModel):
    event_id: str
    store_id: str
    camera_id: str
    track_id: int
    tier: AlertTier
    fused_score: float = Field(ge=0.0, le=1.0)
    action_score: float = Field(ge=0.0, le=1.0)
    rule_flags: list[str] = []
    window_start_ts: float = 0.0
    window_end_ts: float = 0.0
    created_ts: float = 0.0
    clip: ClipRefIn | None = None
    pose_trace: list[list[list[float]]] | None = None


class FeedbackIn(BaseModel):
    verdict: FeedbackVerdict
    reason: str | None = None
    reviewer: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/events", status_code=201)
def ingest_event(event: EventIn, response: Response) -> dict:
    payload = event.model_dump()
    payload["tier"] = event.tier.value
    inserted = get_store().insert_event(payload)
    # Idempotent re-delivery (normal on outbox reconnect) is not a new create.
    response.status_code = 201 if inserted else 200
    return {"event_id": event.event_id, "inserted": inserted}


@app.get("/api/v1/events")
def list_events(
    tier: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    return get_store().list_events(tier=tier, limit=limit)


@app.get("/api/v1/alerts")
def list_alerts(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return get_store().list_alerts_with_feedback(limit=limit)


@app.post("/api/v1/alerts/{event_id}/feedback")
def submit_feedback(event_id: str, feedback: FeedbackIn) -> dict:
    ok = get_store().add_feedback(
        event_id, feedback.verdict.value, feedback.reason, feedback.reviewer
    )
    if not ok:
        raise HTTPException(status_code=404, detail="unknown event_id")
    return {"event_id": event_id, "verdict": feedback.verdict.value}


@app.get("/api/v1/review-queue")
def review_queue(limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    store = get_store()
    items = prioritize(store.unreviewed_events(), store.labeled_examples())
    return [
        {"priority": it.priority, "reasons": it.reasons, "event": it.event}
        for it in items[:limit]
    ]


@app.get("/api/v1/stats")
def stats() -> dict:
    return get_store().stats()


@app.get("/api/v1/models/production")
def production_model_info() -> dict:
    registry = get_registry()
    prod = registry.production() if registry else None
    if not prod:
        raise HTTPException(status_code=404, detail="no production model")
    return {
        "version": prod["version"],
        "metrics": prod["metrics"],
        "created_ts": prod["created_ts"],
    }


@app.get("/api/v1/models/production/artifact")
def production_model_artifact() -> FileResponse:
    registry = get_registry()
    prod = registry.production() if registry else None
    if not prod:
        raise HTTPException(status_code=404, detail="no production model")
    return FileResponse(
        prod["path"],
        media_type="application/octet-stream",
        filename=f"{prod['version']}.onnx",
    )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return (Path(__file__).parent / "static" / "dashboard.html").read_text()
