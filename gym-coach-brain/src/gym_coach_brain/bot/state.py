"""In-memory per-user state shared by deterministic and agent flows."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol


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
    pending_onboarding: bool = False
    profile_exists: bool = False
    onboarding_status: str = "not_started"
    current_onboarding_question_id: str | None = None
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

    def start_onboarding(self, question_id: str | None) -> None:
        self.profile_exists = True
        self.pending_onboarding = True
        self.onboarding_status = "in_progress"
        self.current_onboarding_question_id = question_id
        self.current_stage = "onboarding"

    def advance_onboarding(self, question_id: str | None) -> None:
        self.profile_exists = True
        self.pending_onboarding = question_id is not None
        self.onboarding_status = "in_progress" if question_id is not None else "ready_to_complete"
        self.current_onboarding_question_id = question_id
        self.current_stage = "onboarding" if question_id is not None else "onboarding_review"

    def complete_onboarding(self) -> None:
        self.profile_exists = True
        self.pending_onboarding = False
        self.onboarding_status = "completed"
        self.current_onboarding_question_id = None
        self.current_stage = "chat"

    def clear_pending(self) -> None:
        self.pending_checkin_sleep = False
        self.pending_checkin_readiness = False
        self.pending_postcheckin = False
        self.pending_onboarding = False
        self.current_onboarding_question_id = None
        self.selected_sleep_hours = None
        self.current_stage = "chat"

    def compact_summary(self) -> dict[str, object]:
        """Return the model-facing summary used by the agent loop."""
        return {
            "active_session_id": self.active_session_id,
            "current_stage": self.current_stage or "chat",
            "profile_exists": self.profile_exists,
            "onboarding_status": self.onboarding_status,
            "pending_checkin_sleep": self.pending_checkin_sleep,
            "pending_checkin_readiness": self.pending_checkin_readiness,
            "pending_postcheckin": self.pending_postcheckin,
            "pending_onboarding": self.pending_onboarding,
            "current_onboarding_question_id": self.current_onboarding_question_id,
            "selected_sleep_bucket": self.selected_sleep_bucket,
            "known_exercises": self.known_exercise_ids,
        }

    def to_dict(self) -> dict[str, object]:
        """Serialize UserState to a dictionary for persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> UserState:
        """Deserialize UserState from a dictionary."""
        # Extract and cast values with proper type handling
        active_session_id_val = data.get("active_session_id")
        active_session_id: int | None = None
        if active_session_id_val is not None and isinstance(active_session_id_val, (int, float, str)):
            active_session_id = int(active_session_id_val)
        
        selected_sleep_hours_val = data.get("selected_sleep_hours")
        selected_sleep_hours: float | None = None
        if selected_sleep_hours_val is not None and isinstance(selected_sleep_hours_val, (int, float, str)):
            selected_sleep_hours = float(selected_sleep_hours_val)
        
        current_stage_val = data.get("current_stage")
        current_stage = str(current_stage_val) if current_stage_val is not None else None
        
        current_onboarding_question_id_val = data.get("current_onboarding_question_id")
        current_onboarding_question_id = str(current_onboarding_question_id_val) if current_onboarding_question_id_val is not None else None
        
        known_exercise_ids_val = data.get("known_exercise_ids", {})
        known_exercise_ids: dict[str, int] = {}
        if isinstance(known_exercise_ids_val, dict):
            for k, v in known_exercise_ids_val.items():
                known_exercise_ids[str(k)] = int(v) if isinstance(v, (int, float, str)) else 0
        
        return cls(
            pending_checkin_sleep=bool(data.get("pending_checkin_sleep", False)),
            pending_checkin_readiness=bool(data.get("pending_checkin_readiness", False)),
            pending_postcheckin=bool(data.get("pending_postcheckin", False)),
            pending_onboarding=bool(data.get("pending_onboarding", False)),
            profile_exists=bool(data.get("profile_exists", False)),
            onboarding_status=str(data.get("onboarding_status", "not_started")),
            current_onboarding_question_id=current_onboarding_question_id,
            active_session_id=active_session_id,
            selected_sleep_hours=selected_sleep_hours,
            current_stage=current_stage,
            known_exercise_ids=known_exercise_ids,
        )


class UserStateStore(Protocol):
    """Protocol for user state storage implementations."""

    def get(self, user_id: str) -> UserState:
        """Get or create user state for the given user_id."""
        ...


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
