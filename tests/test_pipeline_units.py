"""Unit tests: tracker, rules, fusion, ring buffer, action classifier."""

import pytest

from sentinel.common.events import AlertTier
from sentinel.edge.pipeline.action import KinematicConcealmentClassifier
from sentinel.edge.pipeline.fusion import FusionEngine
from sentinel.edge.pipeline.ringbuffer import RingBuffer
from sentinel.edge.pipeline.rules import RuleEngine, Zone
from sentinel.edge.pipeline.tracker import IoUTracker
from sentinel.edge.pipeline.types import BBox, Detection, Frame
from sentinel.edge.scenario import browsing_actor, concealment_actor
from sentinel.edge.pipeline.pose import SyntheticPose
from sentinel.edge.pipeline.detector import SyntheticDetector


# --- tracker -----------------------------------------------------------------

def _det(x, y):
    return Detection(bbox=BBox(x=x, y=y, w=0.1, h=0.2), confidence=0.9)


def test_tracker_keeps_id_across_small_motion():
    tracker = IoUTracker()
    t1 = tracker.update([_det(0.5, 0.5)], ts=0.0)
    t2 = tracker.update([_det(0.51, 0.5)], ts=0.1)
    assert t1[0].track_id == t2[0].track_id


def test_tracker_assigns_new_id_for_distant_detection():
    tracker = IoUTracker()
    t1 = tracker.update([_det(0.1, 0.1)], ts=0.0)
    t2 = tracker.update([_det(0.8, 0.8)], ts=0.1)
    assert t1[0].track_id != t2[0].track_id


def test_tracker_two_people_stable():
    tracker = IoUTracker()
    a = tracker.update([_det(0.2, 0.5), _det(0.7, 0.5)], ts=0.0)
    b = tracker.update([_det(0.21, 0.5), _det(0.71, 0.5)], ts=0.1)
    assert {p.track_id for p in a} == {p.track_id for p in b}


def test_tracker_ages_out_missing_tracks():
    tracker = IoUTracker(max_misses=2)
    t1 = tracker.update([_det(0.5, 0.5)], ts=0.0)
    old_id = t1[0].track_id
    for i in range(3):
        tracker.update([], ts=0.1 * (i + 1))
    t2 = tracker.update([_det(0.5, 0.5)], ts=1.0)
    assert t2[0].track_id != old_id


# --- rules -------------------------------------------------------------------

ZONE = Zone(name="aisle", kind="merchandise", polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)])
CHECKOUT = Zone(name="till", kind="checkout", polygon=[(0.6, 0.6), (1.0, 0.6), (1.0, 1.0), (0.6, 1.0)])


def test_zone_containment():
    assert ZONE.contains((0.25, 0.5))
    assert not ZONE.contains((0.75, 0.5))


def test_rules_merchandise_flag():
    engine = RuleEngine(zones=[ZONE])
    verdict = engine.evaluate(track_id=1, bbox=BBox(0.2, 0.4, 0.1, 0.2), ts=0.0)
    assert any(f.startswith("in_merchandise_zone") for f in verdict.flags)
    assert not verdict.suppressed


def test_rules_checkout_suppresses():
    engine = RuleEngine(zones=[CHECKOUT])
    verdict = engine.evaluate(track_id=1, bbox=BBox(0.75, 0.75, 0.1, 0.1), ts=0.0)
    assert verdict.suppressed


def test_rules_employee_suppresses():
    engine = RuleEngine()
    verdict = engine.evaluate(track_id=1, bbox=BBox(0.2, 0.4, 0.1, 0.2), ts=0.0, is_employee=True)
    assert verdict.suppressed
    assert "employee_suppress" in verdict.flags


def test_rules_long_dwell():
    engine = RuleEngine(dwell_threshold_s=5.0)
    bbox = BBox(0.2, 0.4, 0.1, 0.2)
    engine.evaluate(track_id=1, bbox=bbox, ts=0.0)
    verdict = engine.evaluate(track_id=1, bbox=bbox, ts=6.0)
    assert "long_dwell" in verdict.flags


# --- action classifier -------------------------------------------------------

def _poses_for(actor_fn, n=40, actor_id="a"):
    pose = SyntheticPose()
    detector = SyntheticDetector()
    tracker = IoUTracker()
    samples = []
    for t in range(n):
        frame = Frame(camera_id="c", ts=t / 10.0, index=t, synthetic_actors=[actor_fn(actor_id, t)])
        people = tracker.update(detector.detect(frame), frame.ts)
        samples.extend(pose.estimate(frame, people))
    return samples


def test_concealment_scores_high():
    clf = KinematicConcealmentClassifier()
    samples = _poses_for(concealment_actor, n=45)
    score = clf.score_window(samples)
    assert score is not None
    assert score.score >= 0.6, score.features


def test_browsing_scores_low():
    clf = KinematicConcealmentClassifier()
    samples = _poses_for(browsing_actor, n=45)
    score = clf.score_window(samples)
    assert score is not None
    assert score.score < 0.4, score.features


def test_short_window_returns_none():
    clf = KinematicConcealmentClassifier(min_window=8)
    samples = _poses_for(concealment_actor, n=4)
    assert clf.score_window(samples) is None


# --- fusion ------------------------------------------------------------------

def _action(score, track_id=1):
    from sentinel.edge.pipeline.action import ActionScore

    return ActionScore(track_id=track_id, score=score, window_start_ts=0.0, window_end_ts=2.0)


def _verdict(flags=(), suppressed=False):
    from sentinel.edge.pipeline.rules import RuleVerdict

    return RuleVerdict(flags=list(flags), suppressed=suppressed)


def test_fusion_hysteresis_blocks_single_flicker():
    fusion = FusionEngine(hysteresis_n=2)
    d1 = fusion.decide(_action(0.95), _verdict(["in_merchandise_zone:a"]))
    assert d1.tier == AlertTier.LOG  # first positive window: not enough history
    d2 = fusion.decide(_action(0.95), _verdict(["in_merchandise_zone:a"]))
    assert d2.tier == AlertTier.ALERT


def test_fusion_suppression_forces_log():
    fusion = FusionEngine()
    for _ in range(3):
        d = fusion.decide(_action(0.95), _verdict(["employee_suppress"], suppressed=True))
    assert d.tier == AlertTier.LOG


def test_fusion_low_score_stays_log():
    fusion = FusionEngine()
    for _ in range(4):
        d = fusion.decide(_action(0.1), _verdict())
    assert d.tier == AlertTier.LOG


def test_fusion_merchandise_zone_boosts():
    fusion = FusionEngine()
    plain = fusion._fuse(_action(0.6), _verdict())
    boosted = fusion._fuse(_action(0.6), _verdict(["in_merchandise_zone:a"]))
    assert boosted > plain


# --- ring buffer -------------------------------------------------------------

def test_ringbuffer_clip_extraction():
    ring = RingBuffer(camera_id="c", capacity_seconds=10, fps=10)
    for t in range(100):
        ring.push(Frame(camera_id="c", ts=t / 10.0, index=t))
    ref, frames = ring.extract_clip(event_ts=8.0, pre_roll_s=1.0, post_roll_s=1.0)
    assert ref.frame_count == len(frames)
    assert frames[0].ts >= 7.0 and frames[-1].ts <= 9.0
    assert ref.frame_count == pytest.approx(21, abs=2)


def test_ringbuffer_respects_capacity():
    ring = RingBuffer(camera_id="c", capacity_seconds=2, fps=10)
    for t in range(100):
        ring.push(Frame(camera_id="c", ts=t / 10.0, index=t))
    assert len(ring) == 20
