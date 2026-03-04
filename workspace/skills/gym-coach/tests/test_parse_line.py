import pytest
from gym_coach import parse_line


@pytest.mark.parametrize("line,expected_rpe", [
    ("bench press 70x6 @8", 8.0),
    ("bench press 70x6 rpe 8", 8.0),
    ("bench press 70x6 rpe8", 8.0),   # no-space variant
    ("bench press 70x6 RPE 8.5", 8.5),
    ("bench press 70x6", None),
])
def test_rpe_parsing(line, expected_rpe):
    _, _, rpe, _ = parse_line(line)
    assert rpe == expected_rpe


@pytest.mark.parametrize("line,expected_w,expected_r", [
    ("жим 70x6", 70.0, 6),        # Latin x
    ("жим 70х6", 70.0, 6),        # Cyrillic х
    ("жим 70×6", 70.0, 6),        # Unicode multiplication sign
    ("bench 82.5x4", 82.5, 4),
])
def test_weight_reps_parsing(line, expected_w, expected_r):
    _, sets, _, _ = parse_line(line)
    assert len(sets) == 1
    w, r = sets[0]
    assert w == expected_w
    assert r == expected_r


def test_wxrxs_format():
    _, sets, _, _ = parse_line("squat 100x5x3")
    assert len(sets) == 3
    assert all(w == 100.0 and r == 5 for w, r in sets)


def test_wxrxs_cyrillic():
    _, sets, _, _ = parse_line("присед 100х5х3")
    assert len(sets) == 3
    assert all(w == 100.0 and r == 5 for w, r in sets)


def test_exercise_name_only():
    name, sets, rpe, _ = parse_line("pull-up")
    assert name == "pull-up"
    assert sets == []
    assert rpe is None


def test_empty_line():
    name, sets, rpe, notes = parse_line("")
    assert name == ""
    assert sets == []
    assert rpe is None
