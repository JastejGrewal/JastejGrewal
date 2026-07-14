"""Offline-tolerant event outbox — blueprint §4.3, a Phase 1 requirement.

Every event/alert is durably enqueued in SQLite before any network attempt.
A drain pass hands pending rows to a publisher; failures leave rows pending
(with attempt counts for backoff), so a store can lose connectivity for hours
and batch-sync on reconnect. Detection never blocks on the network.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass

from sentinel.common.events import DetectionEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_ts REAL NOT NULL DEFAULT 0,
    created_ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox (status, next_attempt_ts);
"""


@dataclass
class DrainResult:
    sent: int
    failed: int
    remaining: int


class Outbox:
    def __init__(self, db_path: str = ":memory:", base_backoff_s: float = 2.0, max_backoff_s: float = 300.0):
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self.base_backoff_s = base_backoff_s
        self.max_backoff_s = max_backoff_s

    def enqueue(self, event: DetectionEvent) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO outbox (event_id, payload, created_ts) VALUES (?, ?, ?)",
            (event.event_id, json.dumps(event.to_dict()), time.time()),
        )
        self._conn.commit()

    def pending_count(self) -> int:
        (n,) = self._conn.execute(
            "SELECT COUNT(*) FROM outbox WHERE status = 'pending'"
        ).fetchone()
        return n

    def drain(self, publish, batch_size: int = 50, now: float | None = None) -> DrainResult:
        """Attempt delivery of due pending events via `publish(event) -> bool`."""
        now = time.time() if now is None else now
        rows = self._conn.execute(
            "SELECT id, event_id, payload, attempts FROM outbox "
            "WHERE status = 'pending' AND next_attempt_ts <= ? "
            "ORDER BY id LIMIT ?",
            (now, batch_size),
        ).fetchall()

        sent = failed = 0
        for row_id, _event_id, payload, attempts in rows:
            event = DetectionEvent.from_dict(json.loads(payload))
            ok = False
            try:
                ok = bool(publish(event))
            except Exception:
                ok = False
            if ok:
                sent += 1
                self._conn.execute(
                    "UPDATE outbox SET status = 'sent' WHERE id = ?", (row_id,)
                )
            else:
                failed += 1
                backoff = min(self.max_backoff_s, self.base_backoff_s * (2 ** attempts))
                self._conn.execute(
                    "UPDATE outbox SET attempts = ?, next_attempt_ts = ? WHERE id = ?",
                    (attempts + 1, now + backoff, row_id),
                )
        self._conn.commit()
        return DrainResult(sent=sent, failed=failed, remaining=self.pending_count())

    def close(self) -> None:
        self._conn.close()
