from sentinel.common.events import DetectionEvent
from sentinel.edge.outbox import Outbox


def _event(i: int) -> DetectionEvent:
    return DetectionEvent(
        store_id="s", camera_id="c", track_id=i, tier="alert",
        fused_score=0.9, action_score=0.8, event_id=f"evt-{i}",
    )


def test_enqueue_and_drain_success():
    outbox = Outbox()
    for i in range(3):
        outbox.enqueue(_event(i))
    assert outbox.pending_count() == 3
    result = outbox.drain(lambda e: True)
    assert result.sent == 3 and result.remaining == 0


def test_enqueue_is_idempotent():
    outbox = Outbox()
    e = _event(1)
    outbox.enqueue(e)
    outbox.enqueue(e)
    assert outbox.pending_count() == 1


def test_failed_publish_stays_pending_with_backoff():
    outbox = Outbox(base_backoff_s=10.0)
    outbox.enqueue(_event(1))
    result = outbox.drain(lambda e: False, now=100.0)
    assert result.failed == 1 and result.remaining == 1
    # Not due yet: drain before backoff expiry delivers nothing.
    result2 = outbox.drain(lambda e: True, now=105.0)
    assert result2.sent == 0 and result2.remaining == 1
    # Due after backoff.
    result3 = outbox.drain(lambda e: True, now=111.0)
    assert result3.sent == 1 and result3.remaining == 0


def test_publisher_exception_treated_as_failure():
    outbox = Outbox()
    outbox.enqueue(_event(1))

    def boom(event):
        raise ConnectionError("network down")

    result = outbox.drain(boom, now=100.0)
    assert result.failed == 1 and result.remaining == 1


def test_offline_then_reconnect_batch_sync():
    """The §4.3 Phase 1 requirement: queue through an outage, sync on reconnect."""
    outbox = Outbox(base_backoff_s=1.0)
    for i in range(10):
        outbox.enqueue(_event(i))
    # Outage: everything fails.
    outbox.drain(lambda e: False, now=0.0)
    assert outbox.pending_count() == 10
    # Reconnect after backoff: everything drains.
    result = outbox.drain(lambda e: True, now=60.0)
    assert result.sent == 10 and result.remaining == 0


def test_exponential_backoff_growth():
    outbox = Outbox(base_backoff_s=2.0, max_backoff_s=300.0)
    outbox.enqueue(_event(1))
    outbox.drain(lambda e: False, now=0.0)     # attempt 1 -> next at 0 + 2
    outbox.drain(lambda e: False, now=2.0)     # attempt 2 -> next at 2 + 4
    result = outbox.drain(lambda e: True, now=5.0)  # 5 < 6: not due
    assert result.sent == 0
    result = outbox.drain(lambda e: True, now=6.5)
    assert result.sent == 1
