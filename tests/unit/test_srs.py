from datetime import datetime, timedelta, timezone

import pytest

from app.learning import srs
from app.learning.srs import AGAIN, EASY, GOOD, HARD, CardState

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def run(grades, state=CardState()):
    due = NOW
    for grade in grades:
        state, due = srs.schedule(state, grade, NOW)
    return state, due


def test_new_card_good_sequence_is_1_6_then_multiplied():
    state, due = run([GOOD])
    assert (state.interval_days, state.repetitions) == (1, 1) and due == NOW + timedelta(days=1)
    state, _ = run([GOOD, GOOD])
    assert state.interval_days == 6
    state, _ = run([GOOD, GOOD, GOOD])
    assert state.interval_days == 15  # 6 × 2,5
    assert state.ease == 2.5


def test_again_requeues_in_ten_minutes_and_resets():
    state, due = run([GOOD, GOOD, AGAIN])
    assert due == NOW + timedelta(minutes=10)
    assert (state.interval_days, state.repetitions, state.lapses) == (0, 0, 1)
    assert state.ease == 2.3


def test_again_on_new_card_is_not_a_lapse():
    state, _ = run([AGAIN, AGAIN])
    assert state.lapses == 0 and state.ease == 2.1


def test_ease_never_below_minimum():
    state, _ = run([AGAIN] * 20)
    assert state.ease == srs.MIN_EASE


def test_hard_grows_slowly_and_lowers_ease():
    state, _ = run([GOOD, GOOD, HARD])
    assert state.interval_days == 7 and state.ease == 2.35
    state, _ = run([HARD])
    assert state.interval_days == 1


def test_easy_grows_faster_and_raises_ease():
    state, _ = run([EASY])
    assert state.interval_days == 4 and state.ease == 2.65
    good, _ = run([GOOD, GOOD, GOOD])
    easy, _ = run([GOOD, GOOD, EASY])
    assert easy.interval_days > good.interval_days


def test_interval_always_increases_on_success_and_is_capped():
    state = CardState()
    previous = 0
    for _ in range(30):
        state, _ = srs.schedule(state, GOOD, NOW)
        assert state.interval_days > previous or state.interval_days == srs.MAX_INTERVAL_DAYS
        previous = state.interval_days
    assert state.interval_days == srs.MAX_INTERVAL_DAYS


def test_invalid_grade_rejected():
    with pytest.raises(ValueError):
        srs.schedule(CardState(), 7, NOW)


def test_buckets():
    assert srs.bucket(CardState(interval_days=6)) == "learning"
    assert srs.bucket(CardState(interval_days=21)) == "learned"
    assert srs.bucket(CardState(interval_days=60)) == "long_term"
