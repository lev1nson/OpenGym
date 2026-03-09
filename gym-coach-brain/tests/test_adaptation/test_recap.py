"""
Tests for adaptation/recap.py — pre-workout Recap generator.

AC coverage:
- Empty history → "Первая тренировка — история пока пуста"
- Correct format for sets with weight
- Bodyweight exercises (weight_kg=0.0) — no weight in format
- Latest completed session is used (not an older one)
- Non-completed sessions are ignored
"""
import pytest
from gym_coach_brain.data.models import (
    WorkoutSession,
    WorkoutSet,
    Exercise,
    MuscleGroup,
    MovementPattern,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_exercise(db_session, name="Жим лёжа"):
    mg = MuscleGroup(name=f"muscle_{name}", body_region="upper", is_push=True, is_pull=False, stretch_mediated=False)
    mp = MovementPattern(name=f"pattern_{name}", category="push")
    db_session.add_all([mg, mp])
    db_session.flush()
    ex = Exercise(
        name=name,
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        is_compound=True,
        stretch_mediated=False,
        equipment_type="barbell",
    )
    db_session.add(ex)
    db_session.flush()
    return ex


def _make_session(db_session, date="2026-03-08", status="completed"):
    sess = WorkoutSession(session_date=date, status=status)
    db_session.add(sess)
    db_session.flush()
    return sess


def _add_set(db_session, session, exercise, set_number, weight_kg, reps):
    ws = WorkoutSet(
        session_id=session.id,
        exercise_id=exercise.id,
        set_number=set_number,
        weight_kg=weight_kg,
        reps=reps,
    )
    db_session.add(ws)
    db_session.flush()
    return ws


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_recap_empty_history(db_session):
    """No completed sessions → returns no-history message."""
    from gym_coach_brain.adaptation.recap import generate_recap

    result = generate_recap(db_session)
    assert result == "Первая тренировка — история пока пуста"


def test_recap_formats_sets_correctly(db_session):
    """Session with 3 sets → correct format 'Exercise: weight × reps, ...'"""
    from gym_coach_brain.adaptation.recap import generate_recap

    ex = _make_exercise(db_session, "Жим лёжа")
    sess = _make_session(db_session, "2026-03-08", "completed")

    for i, (w, r) in enumerate([(80.0, 8), (80.0, 7), (77.5, 8)], start=1):
        _add_set(db_session, sess, ex, i, w, r)

    result = generate_recap(db_session)
    assert "Жим лёжа" in result
    assert "80кг × 8" in result
    assert "80кг × 7" in result
    assert "77.5кг × 8" in result


def test_recap_bodyweight_omits_weight(db_session):
    """Bodyweight exercise (weight_kg=0.0) → format without weight '× reps'."""
    from gym_coach_brain.adaptation.recap import generate_recap

    ex = _make_exercise(db_session, "Подтягивания")
    sess = _make_session(db_session, "2026-03-08", "completed")
    _add_set(db_session, sess, ex, 1, 0.0, 12)
    _add_set(db_session, sess, ex, 2, 0.0, 10)

    result = generate_recap(db_session)
    assert "Подтягивания" in result
    assert "× 12" in result
    assert "× 10" in result
    # No "кг" should appear for bodyweight
    assert "кг" not in result


def test_recap_latest_completed_session(db_session):
    """Multiple completed sessions → returns sets from the most recent one."""
    from gym_coach_brain.adaptation.recap import generate_recap

    ex = _make_exercise(db_session, "Тяга")

    # Older session
    old_sess = _make_session(db_session, "2026-03-01", "completed")
    _add_set(db_session, old_sess, ex, 1, 60.0, 5)

    # Newer session
    new_sess = _make_session(db_session, "2026-03-08", "completed")
    _add_set(db_session, new_sess, ex, 1, 100.0, 5)

    result = generate_recap(db_session)
    assert "100кг × 5" in result
    # Old session weight should not appear
    assert "60кг" not in result


def test_recap_same_timestamp_prefers_latest_row(db_session):
    """Tied session_date values should still pick the newest completed row deterministically."""
    from gym_coach_brain.adaptation.recap import generate_recap

    ex = _make_exercise(db_session, "Тяга")

    first = _make_session(db_session, "2026-03-08T10:00:00", "completed")
    _add_set(db_session, first, ex, 1, 80.0, 5)

    second = _make_session(db_session, "2026-03-08T10:00:00", "completed")
    _add_set(db_session, second, ex, 1, 100.0, 5)

    result = generate_recap(db_session)

    assert "100кг × 5" in result
    assert "80кг × 5" not in result


def test_recap_ignores_non_completed_sessions(db_session):
    """Sessions with status != 'completed' are ignored."""
    from gym_coach_brain.adaptation.recap import generate_recap

    ex = _make_exercise(db_session, "Приседания")
    planned_sess = _make_session(db_session, "2026-03-09", "planned")
    _add_set(db_session, planned_sess, ex, 1, 120.0, 5)

    result = generate_recap(db_session)
    assert result == "Первая тренировка — история пока пуста"
