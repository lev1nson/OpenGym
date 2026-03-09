"""
Tests for adaptation/summary.py — post-workout Summary generator.

AC coverage:
- Full plan executed → no ❌, no ➕
- Missed exercise → ❌ Пропущено
- Extra exercise → ➕ Дополнительно
- avg_rpe < easy_threshold → "Объёмы хорошие"
- avg_rpe >= fatigue_threshold → "Видно что устал"
- total sets count appears in output
- Thresholds come from science config (not hardcoded)
"""
import json
import pytest
from gym_coach_brain.data.models import (
    WorkoutSession,
    WorkoutSet,
    Exercise,
    MuscleGroup,
    MovementPattern,
)
from gym_coach_brain.core.science import ScienceConfig, SummaryConfig


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_exercise(db_session, name):
    mg = MuscleGroup(name=f"mg_{name}", body_region="upper", is_push=True, is_pull=False, stretch_mediated=False)
    mp = MovementPattern(name=f"mp_{name}", category="push")
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


def _make_completed_session(db_session, planned_names=None, date="2026-03-08"):
    planned = json.dumps([{"exercise_name": n} for n in (planned_names or [])])
    sess = WorkoutSession(session_date=date, status="completed", planned_exercises=planned)
    db_session.add(sess)
    db_session.flush()
    return sess


def _add_set(db_session, session, exercise, set_number, weight_kg=80.0, reps=8, rpe=None):
    ws = WorkoutSet(
        session_id=session.id,
        exercise_id=exercise.id,
        set_number=set_number,
        weight_kg=weight_kg,
        reps=reps,
        rpe=rpe,
    )
    db_session.add(ws)
    db_session.flush()
    return ws


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_summary_no_missed_no_extra(db_session, mock_science_config):
    """Plan == actual → no ❌ and no ➕ lines."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex = _make_exercise(db_session, "Жим лёжа")
    sess = _make_completed_session(db_session, planned_names=["Жим лёжа"])
    _add_set(db_session, sess, ex, 1)

    result = generate_summary(sess, db_session, mock_science_config)
    assert "❌" not in result
    assert "➕" not in result


def test_summary_missed_exercise(db_session, mock_science_config):
    """Exercise in plan but not performed → ❌ Пропущено."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex_done = _make_exercise(db_session, "Жим лёжа")
    sess = _make_completed_session(db_session, planned_names=["Жим лёжа", "Тяга"])
    _add_set(db_session, sess, ex_done, 1)

    result = generate_summary(sess, db_session, mock_science_config)
    assert "❌ Пропущено: Тяга" in result
    assert "❌ Пропущено: Жим лёжа" not in result


def test_summary_extra_exercise(db_session, mock_science_config):
    """Exercise performed but not in plan → ➕ Дополнительно."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex_planned = _make_exercise(db_session, "Жим лёжа")
    ex_extra = _make_exercise(db_session, "Кёрл")
    sess = _make_completed_session(db_session, planned_names=["Жим лёжа"])
    _add_set(db_session, sess, ex_planned, 1)
    _add_set(db_session, sess, ex_extra, 1)

    result = generate_summary(sess, db_session, mock_science_config)
    assert "➕ Дополнительно: Кёрл" in result
    assert "❌" not in result


def test_summary_easy_rpe(db_session, mock_science_config):
    """avg_rpe 5.0 (< 7.0 easy_threshold) → 'Объёмы хорошие'."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex = _make_exercise(db_session, "Тяга")
    sess = _make_completed_session(db_session, planned_names=["Тяга"])
    _add_set(db_session, sess, ex, 1, rpe=5.0)
    _add_set(db_session, sess, ex, 2, rpe=5.0)
    _add_set(db_session, sess, ex, 3, rpe=5.0)

    result = generate_summary(sess, db_session, mock_science_config)
    assert "Объёмы хорошие" in result


def test_summary_high_rpe(db_session, mock_science_config):
    """avg_rpe 9.0 (>= 8.0 fatigue_threshold) → 'Видно что устал'."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex = _make_exercise(db_session, "Присед")
    sess = _make_completed_session(db_session, planned_names=["Присед"])
    _add_set(db_session, sess, ex, 1, rpe=9.0)
    _add_set(db_session, sess, ex, 2, rpe=9.0)

    result = generate_summary(sess, db_session, mock_science_config)
    assert "Видно что устал" in result


def test_summary_weight_decline_without_rpe_is_fatigued(db_session, mock_science_config):
    """Weight drop should trigger fatigue even when RPE is missing."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex = _make_exercise(db_session, "Жим стоя")
    sess = _make_completed_session(db_session, planned_names=["Жим стоя"])
    _add_set(db_session, sess, ex, 1, weight_kg=60.0, reps=8, rpe=None)
    _add_set(db_session, sess, ex, 2, weight_kg=50.0, reps=8, rpe=None)

    result = generate_summary(sess, db_session, mock_science_config)

    assert "Видно что устал" in result
    assert "RPE: не зафиксирован" in result


def test_summary_total_sets_count(db_session, mock_science_config):
    """3 exercises × 3 sets = 9 total sets in output."""
    from gym_coach_brain.adaptation.summary import generate_summary

    names = ["Жим лёжа", "Тяга", "Присед"]
    exercises = [_make_exercise(db_session, n) for n in names]
    sess = _make_completed_session(db_session, planned_names=names)

    for ex in exercises:
        for i in range(1, 4):
            _add_set(db_session, sess, ex, i)

    result = generate_summary(sess, db_session, mock_science_config)
    assert "Выполнено подходов: 9" in result


def test_summary_thresholds_from_science_config(db_session):
    """Changing thresholds changes classification — confirms not hardcoded."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex = _make_exercise(db_session, "Жим гантелей")
    # avg_rpe = 7.5 — would be "Нормальная нагрузка" with defaults (easy=7.0, fatigue=8.0)
    sess = _make_completed_session(db_session, planned_names=["Жим гантелей"])
    _add_set(db_session, sess, ex, 1, rpe=7.5)
    _add_set(db_session, sess, ex, 2, rpe=7.5)

    # Custom config: lower fatigue threshold → 7.5 >= 6.0 → "Видно что устал"
    custom_science = ScienceConfig(
        version="test",
        puos=__import__("gym_coach_brain.core.science", fromlist=["PUOSConfig"]).PUOSConfig(
            max_sets_per_group=11, smh_volume_multiplier=1.2
        ),
        progression=__import__("gym_coach_brain.core.science", fromlist=["ProgressionConfig"]).ProgressionConfig(
            compound_increment_kg=2.5,
            isolation_increment_kg=1.25,
            apre_6_step_min_kg=2.5,
            apre_6_step_max_kg=5.0,
            hypertrophy_rep_min=6,
            hypertrophy_rep_max=12,
        ),
        recovery=__import__("gym_coach_brain.core.science", fromlist=["RecoveryConfig"]).RecoveryConfig(
            hrv_weight=0.5, sleep_weight=0.3, stress_weight=0.2
        ),
        exercises={},
        methodologies=__import__("gym_coach_brain.core.science", fromlist=["MethodologiesConfig"]).MethodologiesConfig(
            strength=__import__("gym_coach_brain.core.science", fromlist=["MethodologySpec"]).MethodologySpec(
                rep_min=1, rep_max=5, frequency_per_week_min=2, frequency_per_week_max=4
            ),
            hypertrophy=__import__("gym_coach_brain.core.science", fromlist=["MethodologySpec"]).MethodologySpec(
                rep_min=6, rep_max=12, frequency_per_week_min=2, frequency_per_week_max=4
            ),
            endurance=__import__("gym_coach_brain.core.science", fromlist=["MethodologySpec"]).MethodologySpec(
                rep_min=15, rep_max=30, frequency_per_week_min=3, frequency_per_week_max=5
            ),
        ),
        planning=__import__("gym_coach_brain.core.science", fromlist=["PlanningConfig"]).PlanningConfig(
            min_rest_days_per_muscle_group=2, min_rest_days_compound=3
        ),
        summary=SummaryConfig(rpe_easy_threshold=7.0, rpe_fatigue_threshold=6.0),
    )

    result = generate_summary(sess, db_session, custom_science)
    assert "Видно что устал" in result


def test_summary_bad_planned_exercises_json_degrades_safely(db_session, mock_science_config):
    """Malformed planned_exercises JSON should not abort summary generation."""
    from gym_coach_brain.adaptation.summary import generate_summary

    ex = _make_exercise(db_session, "Тяга штанги")
    sess = WorkoutSession(
        session_date="2026-03-08",
        status="completed",
        planned_exercises="not valid json{{",
    )
    db_session.add(sess)
    db_session.flush()
    _add_set(db_session, sess, ex, 1, rpe=7.0)

    result = generate_summary(sess, db_session, mock_science_config)

    assert "Выполнено подходов: 1" in result
    assert "➕ Дополнительно: Тяга штанги" in result
