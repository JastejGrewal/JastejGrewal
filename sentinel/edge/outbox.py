"""Offline-tolerant event outbox — blueprint §4.3, a Phase 1 requirement.

Every event/alert is durably enqueued in SQLite before any network attempt.
A drain pass hands pending rows to a publisher; failures leave rows pending
(with attempt counts for backoff), so a store can lose connectivity for hours
and batch-sync on reconnect. Detection never blocks on the network.
"""

from __future__ import annotations

import json
import sqlite3
import threading
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
    dead_lettered: int
    remaining: int


class Outbox:
    """Durable, thread-safe, offline-tolerant event queue.

    The detection thread enqueues; a (possibly separate) sync loop drains —
    so the connection allows cross-thread use and every access is serialized
    under a lock. WAL + synchronous=NORMAL keeps the per-event commit cheap on
    edge flash storage. Delivered rows are deleted (not just marked) so the DB
    stays bounded on a 24/7 box, and rows exceeding max_attempts are moved to a
    'dead' status so a permanently-rejected payload can't be retried forever.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        base_backoff_s: float = 2.0,
        max_backoff_s: float = 300.0,
        max_attempts: int = 8,
    ):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self.base_backoff_s = base_backoff_s
        self.max_backoff_s = max_backoff_s
        self.max_attempts = max_attempts

    def enqueue(self, event: DetectionEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO outbox (event_id, payload, created_ts) VALUES (?, ?, ?)",
                (event.event_id, json.dumps(event.to_dict()), time.time()),
            )
            self._conn.commit()

    def pending_count(self) -> int:
        with self._lock:
            (n,) = self._conn.execute(
                "SELECT COUNT(*) FROM outbox WHERE status = 'pending'"
            ).fetchone()
        return n

    def dead_letter_count(self) -> int:
        with self._lock:
            (n,) = self._conn.execute(
                "SELECT COUNT(*) FROM outbox WHERE status = 'dead'"
            ).fetchone()
        return n

    def drain(self, publish, batch_size: int = 50, now: float | None = None) -> DrainResult:
        """Attempt delivery of due pending events via `publish(event) -> bool`."""
        now = time.time() if now is None else now
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, event_id, payload, attempts FROM outbox "
                "WHERE status = 'pending' AND next_attempt_ts <= ? "
                "ORDER BY id LIMIT ?",
                (now, batch_size),
            ).fetchall()

        sent = failed = dead = 0
        for row_id, _event_id, payload, attempts in rows:
            event = DetectionEvent.from_dict(json.loads(payload))
            ok = False
            try:
                ok = bool(publish(event))
            except Exception:
                ok = False
            with self._lock:
                if ok:
                    sent += 1
                    self._conn.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
                elif attempts + 1 >= self.max_attempts:
                    dead += 1
                    self._conn.execute(
                        "UPDATE outbox SET attempts = ?, status = 'dead' WHERE id = ?",
                        (attempts + 1, row_id),
                    )
                else:
                    failed += 1
                    backoff = min(self.max_backoff_s, self.base_backoff_s * (2 ** attempts))
                    self._conn.execute(
                        "UPDATE outbox SET attempts = ?, next_attempt_ts = ? WHERE id = ?",
                        (attempts + 1, now + backoff, row_id),
                    )
                self._conn.commit()
        return DrainResult(
            sent=sent, failed=failed, dead_lettered=dead, remaining=self.pending_count()
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
