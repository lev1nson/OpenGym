"""Tool schemas and subprocess-backed execution for the agent loop."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import subprocess
import sys
from typing import Any

from loguru import logger

from gym_coach_brain.bot.state import UserState


DEFAULT_TOOL_TIMEOUT_SECONDS = 30
_RE_EXERCISE_ID = re.compile(r"(?P<name>.+?) \(id:(?P<id>\d+)\)")
_RE_LEADING_INDEX = re.compile(r"^\d+\.\s*")


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "workout_start",
            "description": "Start today's workout after deterministic readiness flow is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sleep_hours": {
                        "type": "number",
                        "description": "Hours of sleep from the pre-workout check-in. Required for the first session of the day.",
                    },
                    "pre_readiness": {
                        "type": "integer",
                        "description": "Pre-workout readiness score (2, 5, or 9) from the pre-workout check-in.",
                    },
                    "confirm_second_session": {
                        "type": "boolean",
                        "description": "Use true only when the athlete explicitly confirms a second session today.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workout_log_set",
            "description": "Log one completed set for the active workout session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise_id": {"type": "integer"},
                    "set_number": {"type": "integer"},
                    "weight_kg": {"type": "number"},
                    "reps": {"type": "integer"},
                    "rir": {"type": "integer"},
                },
                "required": ["exercise_id", "set_number", "weight_kg", "reps", "rir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workout_finish",
            "description": "Finish the active workout session and generate the summary.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workout_status",
            "description": "Show the current workout plan and logged-set progress.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workout_summary",
            "description": "Show a summary for the latest or requested completed workout session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "integer",
                        "description": "Optional completed workout session id.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "readiness_log",
            "description": "Log readiness using the backend-supported sleep, stress, and optional HRV inputs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sleep": {"type": "number"},
                    "stress": {"type": "integer"},
                    "hrv": {"type": "number"},
                },
                "required": ["sleep", "stress"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_report",
            "description": "Return a fractional-volume report over a lookback period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "weeks": {"type": "integer"},
                },
                "required": ["weeks"],
            },
        },
    },
]


@dataclass(slots=True)
class ToolExecutionResult:
    """Normalized tool execution output reused by the loop and tests."""

    name: str
    intent: str
    exit_code: int
    stdout: str
    argv: list[str]
    data: dict[str, Any] | None = None
    tool_call_id: str | None = None

    def model_payload(self) -> str:
        payload: dict[str, Any] = {
            "intent": self.intent,
            "argv": self.argv,
            "stdout": self.stdout,
            "exit_code": self.exit_code,
        }
        if self.data:
            payload["data"] = self.data
        return json.dumps(payload, ensure_ascii=False)


class ToolExecutor:
    """Execute backend intents via the stable gym_coach_brain.api CLI boundary."""

    def __init__(
        self,
        *,
        python_executable: str = sys.executable,
        timeout_seconds: int = DEFAULT_TOOL_TIMEOUT_SECONDS,
    ) -> None:
        self.python_executable = python_executable
        self.timeout_seconds = timeout_seconds

    def execute(
        self,
        *,
        tool_name: str,
        arguments_json: str,
        state: UserState,
        tool_call_id: str | None = None,
    ) -> ToolExecutionResult:
        if tool_name not in {tool["function"]["name"] for tool in TOOL_SCHEMAS}:
            logger.error("Unknown tool requested by model: {}", tool_name)
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout="Unknown tool requested by the model.",
                argv=[],
                tool_call_id=tool_call_id,
            )

        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError:
            logger.exception("Invalid tool JSON for {}", tool_name)
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout="Tool arguments were not valid JSON.",
                argv=[],
                tool_call_id=tool_call_id,
            )

        try:
            argv = self._build_intent_argv(tool_name, arguments)
        except (TypeError, ValueError) as exc:
            logger.exception("Invalid tool arguments for {}", tool_name)
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout=f"Tool arguments were invalid: {exc}",
                argv=[],
                tool_call_id=tool_call_id,
            )

        command = [
            self.python_executable,
            "-m",
            "gym_coach_brain.api",
            "--intent",
            tool_name,
            *argv,
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.exception("Tool execution timed out for {}", tool_name)
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout="The backend tool timed out.",
                argv=argv,
                tool_call_id=tool_call_id,
            )

        payload = self._parse_backend_payload(tool_name, argv, completed.stdout)
        apply_result_to_state(state, payload)
        payload.tool_call_id = tool_call_id
        return payload

    def _build_intent_argv(self, tool_name: str, arguments: dict[str, Any]) -> list[str]:
        if tool_name == "workout_start":
            argv: list[str] = []
            if arguments.get("sleep_hours") is not None:
                argv.extend(["--sleep-hours", str(float(arguments["sleep_hours"]))])
            if arguments.get("pre_readiness") is not None:
                argv.extend(["--pre-readiness", str(int(arguments["pre_readiness"]))])
            if arguments.get("confirm_second_session"):
                argv.append("--confirm-second")
            return argv
        if tool_name == "workout_log_set":
            required = ["exercise_id", "set_number", "weight_kg", "reps", "rir"]
            self._require_keys(tool_name, arguments, required)
            return [
                "--exercise-id",
                str(int(arguments["exercise_id"])),
                "--set-number",
                str(int(arguments["set_number"])),
                "--weight-kg",
                str(float(arguments["weight_kg"])),
                "--reps",
                str(int(arguments["reps"])),
                "--rir",
                str(int(arguments["rir"])),
            ]
        if tool_name == "workout_finish":
            return []
        if tool_name == "workout_status":
            return []
        if tool_name == "workout_summary":
            argv = []
            if "session_id" in arguments and arguments["session_id"] is not None:
                argv.extend(["--session-id", str(int(arguments["session_id"]))])
            return argv
        if tool_name == "readiness_log":
            required = ["sleep", "stress"]
            self._require_keys(tool_name, arguments, required)
            argv = [
                "--sleep",
                str(float(arguments["sleep"])),
                "--stress",
                str(int(arguments["stress"])),
            ]
            if "hrv" in arguments and arguments["hrv"] is not None:
                argv.extend(["--hrv", str(float(arguments["hrv"]))])
            return argv
        if tool_name == "volume_report":
            self._require_keys(tool_name, arguments, ["weeks"])
            return ["--weeks", str(int(arguments["weeks"]))]
        raise ValueError(f"Unsupported tool: {tool_name}")

    @staticmethod
    def _require_keys(tool_name: str, arguments: dict[str, Any], keys: list[str]) -> None:
        missing = [key for key in keys if key not in arguments]
        if missing:
            raise ValueError(f"{tool_name} missing required arguments: {', '.join(missing)}")

    def _parse_backend_payload(
        self,
        tool_name: str,
        argv: list[str],
        stdout: str,
    ) -> ToolExecutionResult:
        if not stdout.strip():
            logger.error("Tool {} returned empty stdout", tool_name)
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout="Backend returned no stdout.",
                argv=argv,
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            logger.exception("Tool {} returned malformed JSON", tool_name)
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout="Backend returned malformed JSON.",
                argv=argv,
            )

        if not isinstance(payload, dict):
            logger.error("Tool {} returned non-object payload", tool_name)
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout="Backend returned an invalid response envelope.",
                argv=argv,
            )

        required_keys = {"intent", "argv", "stdout", "exit_code"}
        if not required_keys.issubset(payload):
            logger.error("Tool {} returned incomplete payload keys: {}", tool_name, payload.keys())
            return ToolExecutionResult(
                name=tool_name,
                intent=tool_name,
                exit_code=2,
                stdout="Backend response envelope was incomplete.",
                argv=argv,
            )

        response_argv = payload["argv"] if isinstance(payload["argv"], list) else argv
        response_stdout = payload["stdout"] if isinstance(payload["stdout"], str) else ""
        response_data = payload.get("data")
        if response_data is not None and not isinstance(response_data, dict):
            response_data = None
        return ToolExecutionResult(
            name=tool_name,
            intent=str(payload["intent"]),
            exit_code=int(payload["exit_code"]),
            stdout=response_stdout,
            argv=[str(item) for item in response_argv],
            data=response_data,
        )


def apply_result_to_state(state: UserState, result: ToolExecutionResult) -> None:
    """Merge tool execution metadata back into the shared user state."""
    if result.data and "session_id" in result.data:
        # Do not overwrite active_session_id from a rejected workout_start: the backend
        # returns the *existing* completed session_id in its rejection payload (exit_code=1).
        if result.name == "workout_start" and result.exit_code != 0:
            pass
        else:
            try:
                state.active_session_id = int(result.data["session_id"])
            except (TypeError, ValueError):
                logger.warning("Invalid session_id in tool payload: {}", result.data["session_id"])

    if result.name == "workout_finish" and result.exit_code == 0:
        state.pending_postcheckin = True
        state.current_stage = "post_workout_checkin"
    elif result.name == "workout_start" and result.exit_code == 0:
        state.current_stage = "active_workout"

    for line in result.stdout.splitlines():
        match = _RE_EXERCISE_ID.search(line.strip())
        if not match:
            continue
        exercise_name = _RE_LEADING_INDEX.sub("", match.group("name").strip())
        state.known_exercise_ids[exercise_name] = int(match.group("id"))
