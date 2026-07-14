"""Cloud persistence: alerts, events, and feedback in SQLite.

SQLite keeps Phase 1 dependency-free; the schema is deliberately boring so a
Postgres/Timescale migration (blueprint §4.4) is a connection-string change
plus a migration script, not a redesign.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    tier TEXT NOT NULL,
    fused_score REAL NOT NULL,
    action_score REAL NOT NULL,
    rule_flags TEXT NOT NULL DEFAULT '[]',
    window_start_ts REAL NOT NULL DEFAULT 0,
    window_end_ts REAL NOT NULL DEFAULT 0,
    clip TEXT,
    created_ts REAL NOT NULL,
    received_ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_tier ON events (tier, received_ts);

CREATE TABLE IF NOT EXISTS feedback (
    event_id TEXT PRIMARY KEY REFERENCES events (event_id),
    verdict TEXT NOT NULL,
    reason TEXT,
    reviewer TEXT,
    created_ts REAL NOT NULL
);
"""


class CloudStore:
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def insert_event(self, payload: dict) -> bool:
        """Idempotent insert; returns False if the event_id already exists."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO events (event_id, store_id, camera_id, track_id,"
                " tier, fused_score, action_score, rule_flags, window_start_ts,"
                " window_end_ts, clip, created_ts, received_ts)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    payload["event_id"],
                    payload["store_id"],
                    payload["camera_id"],
                    payload["track_id"],
                    payload["tier"],
                    payload["fused_score"],
                    payload["action_score"],
                    json.dumps(payload.get("rule_flags", [])),
                    payload.get("window_start_ts", 0.0),
                    payload.get("window_end_ts", 0.0),
                    json.dumps(payload["clip"]) if payload.get("clip") else None,
                    payload.get("created_ts", time.time()),
                    time.time(),
                ),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def _row_to_event(self, row: sqlite3.Row) -> dict:
        event = dict(row)
        event["rule_flags"] = json.loads(event["rule_flags"])
        event["clip"] = json.loads(event["clip"]) if event["clip"] else None
        return event

    def list_events(self, tier: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            if tier:
                rows = self._conn.execute(
                    "SELECT * FROM events WHERE tier = ? ORDER BY received_ts DESC LIMIT ?",
                    (tier, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM events ORDER BY received_ts DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_event(self, event_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return self._row_to_event(row) if row else None

    def unreviewed_events(self, limit: int = 500) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT e.* FROM events e LEFT JOIN feedback f ON f.event_id = e.event_id"
                " WHERE f.event_id IS NULL ORDER BY e.received_ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def add_feedback(
        self, event_id: str, verdict: str, reason: str | None, reviewer: str | None
    ) -> bool:
        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if not exists:
                return False
            self._conn.execute(
                "INSERT OR REPLACE INTO feedback (event_id, verdict, reason, reviewer, created_ts)"
                " VALUES (?, ?, ?, ?, ?)",
                (event_id, verdict, reason, reviewer, time.time()),
            )
            self._conn.commit()
            return True

    def get_feedback(self, event_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM feedback WHERE event_id = ?", (event_id,)
            ).fetchone()
        return dict(row) if row else None

    def labeled_examples(self) -> list[dict]:
        """Feedback-labeled events: the future retraining set (§4.2)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT e.*, f.verdict FROM events e JOIN feedback f ON f.event_id = e.event_id"
            ).fetchall()
        out = []
        for row in rows:
            event = self._row_to_event(row)
            event["verdict"] = row["verdict"]
            out.append(event)
        return out

    def stats(self) -> dict:
        with self._lock:
            tiers = dict(
                self._conn.execute(
                    "SELECT tier, COUNT(*) FROM events GROUP BY tier"
                ).fetchall()
            )
            verdicts = dict(
                self._conn.execute(
                    "SELECT verdict, COUNT(*) FROM feedback GROUP BY verdict"
                ).fetchall()
            )
        return {"events_by_tier": tiers, "feedback_by_verdict": verdicts}
