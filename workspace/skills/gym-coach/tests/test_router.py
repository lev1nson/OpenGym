import subprocess
import pytest
from router import route_text, run_gym_coach


def test_route_workout_start():
    result = route_text("начать тренировку push")
    assert result.intent == "workout_start"
    assert not result.needs_clarification
    assert "Push" in result.argv


def test_route_workout_set():
    result = route_text("жим 70x6 rpe 8")
    assert result.intent == "workout_set"
    assert not result.needs_clarification
    rpe_idx = result.argv.index("--rpe")
    assert result.argv[rpe_idx + 1] == "8"


def test_route_workout_set_cyrillic_x():
    result = route_text("жим 70х6")
    assert result.intent == "workout_set"
    assert not result.needs_clarification


def test_route_workout_done():
    result = route_text("закончил")
    assert result.intent == "workout_done"
    assert not result.needs_clarification


def test_route_unknown():
    result = route_text("абракадабра xyz")
    assert result.needs_clarification


def test_run_gym_coach_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=30)
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_gym_coach(["--help"])
    assert result.returncode == 1
    assert "timed out" in result.stderr
