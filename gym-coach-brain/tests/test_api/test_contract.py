"""Tests for the structured API JSON contract."""

from gym_coach_brain.api.contract import build_response
from gym_coach_brain.api import main as api_main
from gym_coach_brain.exceptions import ScienceLimitError


def test_build_response_keeps_required_keys_only_when_data_absent():
    payload = build_response(
        intent="workout_status",
        argv=["--verbose"],
        stdout="ok",
        exit_code=0,
    )

    assert payload == {
        "intent": "workout_status",
        "argv": ["--verbose"],
        "stdout": "ok",
        "exit_code": 0,
    }


def test_build_response_adds_optional_data_only_when_provided():
    payload = build_response(
        intent="workout_start",
        argv=["--confirm-second"],
        stdout="blocked",
        exit_code=1,
        data={"second_session_today": True, "session_id": 12},
    )

    assert payload["data"] == {
        "second_session_today": True,
        "session_id": 12,
    }


def test_execute_intent_maps_science_limit_error_to_exit_code_1(
    db_session,
    mock_science_config,
    monkeypatch,
):
    def raise_science_limit(argv, session):
        del argv, session
        raise ScienceLimitError("PUOS limit exceeded")

    monkeypatch.setitem(api_main._HANDLERS, "science_limit_test", (raise_science_limit, False))

    payload = api_main.execute_intent(
        "science_limit_test",
        [],
        session=db_session,
        science=mock_science_config,
    )

    assert payload["exit_code"] == 1
    assert payload["stdout"] == "PUOS limit exceeded"


def test_execute_intent_maps_unexpected_exception_to_exit_code_2(
    db_session,
    mock_science_config,
    monkeypatch,
):
    def raise_unexpected(argv, session):
        del argv, session
        raise RuntimeError("boom")

    monkeypatch.setitem(api_main._HANDLERS, "unexpected_test", (raise_unexpected, False))

    payload = api_main.execute_intent(
        "unexpected_test",
        [],
        session=db_session,
        science=mock_science_config,
    )

    assert payload["exit_code"] == 2
    assert payload["stdout"] == "System error: boom"


def test_execute_intent_preserves_optional_data_after_rollback(
    db_session,
    mock_science_config,
    monkeypatch,
):
    def domain_block(argv, session):
        del argv
        session.info["response_data"] = {"orphaned_session": True, "session_id": 4}
        return "blocked", 1

    monkeypatch.setitem(api_main._HANDLERS, "domain_block_test", (domain_block, False))

    payload = api_main.execute_intent(
        "domain_block_test",
        [],
        session=db_session,
        science=mock_science_config,
    )

    assert payload["exit_code"] == 1
    assert payload["data"] == {"orphaned_session": True, "session_id": 4}
