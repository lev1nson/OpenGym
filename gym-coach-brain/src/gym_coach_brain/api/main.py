"""Composition root for the structured workout API."""
from __future__ import annotations

import argparse
import sys
from typing import Callable

from gym_coach_brain.api.contract import build_response, dumps_response
from gym_coach_brain.api.handlers import (
    handle_exercise_add,
    handle_onboarding_answer,
    handle_onboarding_complete,
    handle_onboarding_start,
    handle_volume_report,
    handle_profile_show,
    handle_profile_update_equipment,
    handle_profile_update_split,
    handle_readiness_log,
    handle_workout_finish,
    handle_workout_log_set,
    handle_workout_post_checkin,
    handle_workout_recap,
    handle_workout_start,
    handle_workout_status,
    handle_workout_summary,
)
from gym_coach_brain.core.science import ScienceConfig, load_science_config
from gym_coach_brain.data.session import get_session
from gym_coach_brain.exceptions import ConfigError, GymCoachError, ScienceLimitError

HandlerNoScience = Callable[[list[str], object], tuple[str, int]]
HandlerWithScience = Callable[[list[str], object, ScienceConfig], tuple[str, int]]

_HANDLERS: dict[str, tuple[Callable[..., tuple[str, int]], bool]] = {
    "exercise_add": (handle_exercise_add, False),
    "onboarding_start": (handle_onboarding_start, True),
    "onboarding_answer": (handle_onboarding_answer, True),
    "onboarding_complete": (handle_onboarding_complete, True),
    "profile_show": (handle_profile_show, False),
    "profile_update_equipment": (handle_profile_update_equipment, False),
    "profile_update_split": (handle_profile_update_split, False),
    "readiness_log": (handle_readiness_log, True),
    "workout_start": (handle_workout_start, True),
    "workout_status": (handle_workout_status, False),
    "workout_post_checkin": (handle_workout_post_checkin, False),
    "workout_log_set": (handle_workout_log_set, True),
    "workout_finish": (handle_workout_finish, True),
    "workout_recap": (handle_workout_recap, False),
    "workout_summary": (handle_workout_summary, True),
    "volume_report": (handle_volume_report, True),
}


def execute_intent(
    intent: str,
    argv: list[str],
    *,
    session,
    science: ScienceConfig,
) -> dict[str, object]:
    """Run one intent inside an existing DB session and return the JSON envelope."""
    session.info.pop("response_data", None)

    try:
        handler_entry = _HANDLERS.get(intent)
        if handler_entry is None:
            return build_response(
                intent=intent,
                argv=argv,
                stdout=f"Unknown intent: {intent}",
                exit_code=1,
            )

        handler, requires_science = handler_entry
        if requires_science:
            stdout, exit_code = handler(argv, session, science)
        else:
            stdout, exit_code = handler(argv, session)

        response_data = session.info.pop("response_data", None)
        if exit_code == 0:
            session.commit()
        else:
            session.rollback()

        return build_response(
            intent=intent,
            argv=argv,
            stdout=stdout,
            exit_code=exit_code,
            data=response_data,
        )
    except ScienceLimitError as exc:
        session.rollback()
        return build_response(intent=intent, argv=argv, stdout=str(exc), exit_code=1)
    except ConfigError as exc:
        session.rollback()
        return build_response(intent=intent, argv=argv, stdout=str(exc), exit_code=2)
    except GymCoachError as exc:
        session.rollback()
        return build_response(intent=intent, argv=argv, stdout=str(exc), exit_code=1)
    except Exception as exc:  # pragma: no cover - defensive boundary
        session.rollback()
        return build_response(
            intent=intent,
            argv=argv,
            stdout=f"System error: {exc}",
            exit_code=2,
        )


def parse_cli_args(argv: list[str] | None = None) -> tuple[str, list[str]]:
    """Parse the API CLI arguments and preserve remaining intent args."""
    parser = argparse.ArgumentParser(prog="python -m gym_coach_brain.api", add_help=False)
    parser.add_argument("--intent", required=True)
    args, remaining = parser.parse_known_args(argv)
    return args.intent, remaining


def main(
    argv: list[str] | None = None,
    *,
    engine=None,
    science: ScienceConfig | None = None,
) -> int:
    """CLI entrypoint: execute one intent and print the JSON envelope."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    intent = ""
    intent_argv: list[str] = []

    try:
        intent, intent_argv = parse_cli_args(raw_argv)
        resolved_science = science or load_science_config()
        with get_session(engine) as session:
            response = execute_intent(
                intent,
                intent_argv,
                session=session,
                science=resolved_science,
            )
    except SystemExit:
        response = build_response(
            intent=intent,
            argv=intent_argv,
            stdout="Missing required argument: --intent",
            exit_code=1,
        )
    except Exception as exc:
        response = build_response(
            intent=intent,
            argv=intent_argv,
            stdout=f"System error: {exc}",
            exit_code=2,
        )

    sys.stdout.write(dumps_response(response) + "\n")
    return int(response["exit_code"])
