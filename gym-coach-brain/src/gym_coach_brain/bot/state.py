"""In-memory per-user state shared by deterministic and agent flows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PlannerEventType(str, Enum):
    PAIN_REPORT = "pain_report"
    READINESS_OVERRIDE = "readiness_override"
    SKIPPED_SESSION = "skipped_session"
    PERFORMANCE_FEEDBACK = "performance_feedback"
    PREFERENCE_REQUEST = "preference_request"


@dataclass
class PlannerEvent:
    event_type: PlannerEventType
    timestamp: datetime
    athlete_id: int
    data: dict


@dataclass(slots=True)
class UserState:
    """Conversation state owned by the bot transport and agent layers."""

    pending_checkin_sleep: bool = False
    pending_checkin_readiness: bool = False
    pending_postcheckin: bool = False
    active_session_id: int | None = None
    selected_sleep_hours: float | None = None
    current_stage: str | None = None
    known_exercise_ids: dict[str, int] = field(default_factory=dict)

    @property
    def selected_sleep_bucket(self) -> float | None:
        return self.selected_sleep_hours

    @selected_sleep_bucket.setter
    def selected_sleep_bucket(self, value: float | None) -> None:
        self.selected_sleep_hours = value

    def start_precheckin(self) -> None:
        self.pending_checkin_sleep = True
        self.pending_checkin_readiness = False
        self.selected_sleep_hours = None
        self.current_stage = "precheckin_sleep"

    def advance_to_readiness(self, sleep_hours: float) -> None:
        self.pending_checkin_sleep = False
        self.pending_checkin_readiness = True
        self.selected_sleep_hours = sleep_hours
        self.current_stage = "precheckin_readiness"

    def clear_pending(self) -> None:
        self.pending_checkin_sleep = False
        self.pending_checkin_readiness = False
        self.pending_postcheckin = False
        self.selected_sleep_hours = None
        self.current_stage = "chat"

    def compact_summary(self) -> dict[str, object]:
        """Return the model-facing summary used by the agent loop."""
        return {
            "active_session_id": self.active_session_id,
            "current_stage": self.current_stage or "chat",
            "pending_checkin_sleep": self.pending_checkin_sleep,
            "pending_checkin_readiness": self.pending_checkin_readiness,
            "pending_postcheckin": self.pending_postcheckin,
            "selected_sleep_bucket": self.selected_sleep_bucket,
            "known_exercises": self.known_exercise_ids,
        }


class InMemoryUserStateStore:
    """Simple in-memory state store keyed by normalized user id."""

    def __init__(self) -> None:
        self._states: dict[str, UserState] = {}

    def get(self, user_id: str) -> UserState:
        state = self._states.get(user_id)
        if state is None:
            state = UserState()
            self._states[user_id] = state
        return state
