"""
SQLAlchemy ORM models — single source of truth for database schema.

ALL schema changes must be made here first, then regenerated via:
    uv run alembic revision --autogenerate -m "description"
"""
import json
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class EquipmentType(str, Enum):
    barbell = "barbell"
    dumbbell = "dumbbell"
    machine = "machine"
    cable = "cable"
    bodyweight = "bodyweight"
    resistance_band = "resistance_band"
    pullup_bar = "pullup_bar"
    dips_bar = "dips_bar"


class TrainingSplit(str, Enum):
    ppl = "ppl"
    upper_lower = "upper_lower"
    full_body = "full_body"
    custom = "custom"


# ─── Reference / Lookup Tables ────────────────────────────────────────────────

class MuscleGroup(Base):
    __tablename__ = "muscle_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    body_region = Column(String, nullable=False)  # upper / lower / core
    is_push = Column(Boolean, nullable=False, default=False)
    is_pull = Column(Boolean, nullable=False, default=False)
    stretch_mediated = Column(Boolean, nullable=False, default=False)

    exercises = relationship(
        "Exercise", back_populates="primary_muscle", foreign_keys="Exercise.primary_muscle_id"
    )


class MovementPattern(Base):
    __tablename__ = "movement_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)  # push / pull / legs / carry

    exercises = relationship("Exercise", back_populates="movement_pattern")


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)  # matches EquipmentType values
    available_home = Column(Boolean, nullable=False, default=False)
    available_gym = Column(Boolean, nullable=False, default=True)


# ─── Core Models ──────────────────────────────────────────────────────────────

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bodyweight_kg = Column(Float, nullable=True)
    # JSON dict {movement_pattern_name: float} — starting weight coefficients
    initial_weight_coefficients = Column(Text, nullable=True)
    # JSON list of EquipmentType values
    available_equipment = Column(Text, nullable=True, default="[]")
    # SQLAlchemyEnum per AC — validated at DB (CHECK constraint) and ORM level
    training_split = Column(
        SAEnum(TrainingSplit, name="trainingsplit"),
        nullable=False,
        default=TrainingSplit.full_body,
    )
    training_days_per_week = Column(Integer, nullable=False, default=3)
    onboarding_complete = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        String, nullable=False,
        server_default=text("strftime('%Y-%m-%dT%H:%M:%S', 'now')"),
    )
    updated_at = Column(
        String, nullable=True,
        onupdate=text("strftime('%Y-%m-%dT%H:%M:%S', 'now')"),
    )

    __table_args__ = (
        CheckConstraint(
            "training_days_per_week >= 3 AND training_days_per_week <= 6",
            name="ck_user_profile_training_days",
        ),
        CheckConstraint(
            "training_split IN ('ppl', 'upper_lower', 'full_body', 'custom')",
            name="ck_user_profile_training_split",
        ),
    )

    @hybrid_property
    def available_equipment_list(self) -> list:
        """JSON list of EquipmentType values."""
        return json.loads(self.available_equipment or "[]")

    @available_equipment_list.setter
    def available_equipment_list(self, value: list) -> None:
        self.available_equipment = json.dumps(value)

    @hybrid_property
    def initial_weight_coefficients_dict(self) -> dict:
        """JSON dict of {movement_pattern_name: float}."""
        return json.loads(self.initial_weight_coefficients or "{}")

    @initial_weight_coefficients_dict.setter
    def initial_weight_coefficients_dict(self, value: dict) -> None:
        self.initial_weight_coefficients = json.dumps(value)


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    primary_muscle_id = Column(Integer, ForeignKey("muscle_groups.id"), nullable=False)
    movement_pattern_id = Column(Integer, ForeignKey("movement_patterns.id"), nullable=False)
    # JSON-encoded list of MuscleGroup IDs
    secondary_muscle_ids = Column(Text, nullable=False, default="[]")
    is_compound = Column(Boolean, nullable=False, default=True)
    stretch_mediated = Column(Boolean, nullable=False, default=False)
    # SQLAlchemyEnum per AC — not a free string; CHECK constraint enforces DB-level validation
    equipment_type = Column(SAEnum(EquipmentType, name="equipmenttype"), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "equipment_type IN ('barbell', 'dumbbell', 'machine', 'cable', "
            "'bodyweight', 'resistance_band', 'pullup_bar', 'dips_bar')",
            name="ck_exercise_equipment_type",
        ),
    )

    primary_muscle = relationship(
        "MuscleGroup", back_populates="exercises", foreign_keys=[primary_muscle_id]
    )
    movement_pattern = relationship("MovementPattern", back_populates="exercises")

    @hybrid_property
    def secondary_muscle_id_list(self) -> list:
        """JSON-decoded list of secondary MuscleGroup IDs."""
        return json.loads(self.secondary_muscle_ids or "[]")

    @secondary_muscle_id_list.setter
    def secondary_muscle_id_list(self, value: list) -> None:
        self.secondary_muscle_ids = json.dumps(value)


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_date = Column(String, nullable=False)  # ISO 8601 UTC
    status = Column(String, nullable=False, default="planned")  # planned / active / completed
    methodology = Column(String, nullable=True)  # strength / hypertrophy / endurance
    # JSON-encoded list of PlannedExercise dicts
    planned_exercises = Column(Text, nullable=True)
    # push / pull / legs / upper / lower / full_body
    split_day_label = Column(String, nullable=True)
    created_at = Column(
        String, nullable=False,
        server_default=text("strftime('%Y-%m-%dT%H:%M:%S', 'now')"),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'active', 'completed')",
            name="ck_workout_session_status",
        ),
    )

    sets = relationship("WorkoutSet", back_populates="session")
    rpe_predictions = relationship("RPEPrediction", back_populates="session")


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    set_number = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    # rpe is COMPUTED: 10.0 - rir. Set by api/handlers.py, NOT by model.
    rpe = Column(Float, nullable=True)
    # rir = Reps In Reserve (0=to failure, 4=very easy). Athlete input.
    rir = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(
        String, nullable=False,
        server_default=text("strftime('%Y-%m-%dT%H:%M:%S', 'now')"),
    )

    __table_args__ = (
        UniqueConstraint("session_id", "exercise_id", "set_number", name="uq_workout_set"),
        CheckConstraint(
            "rir IS NULL OR (rir >= 0 AND rir <= 4)",
            name="ck_workout_set_rir_range",
        ),
    )

    session = relationship("WorkoutSession", back_populates="sets")
    exercise = relationship("Exercise")


class ReadinessLog(Base):
    __tablename__ = "readiness_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_date = Column(String, nullable=False)  # ISO 8601 UTC date
    sleep_hours = Column(Float, nullable=False)
    stress_level = Column(Integer, nullable=False)  # 1–10 scale
    hrv_score = Column(Float, nullable=True)         # optional (wearable)
    recovery_score = Column(Float, nullable=False)   # composite computed score


class MLJob(Base):
    __tablename__ = "ml_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String, nullable=False)     # "FINE_TUNE" | "PREDICT"
    status = Column(String, nullable=False, default="pending")  # pending/processing/done/failed
    session_ids = Column(Text, nullable=False)    # JSON array of session IDs
    created_at = Column(
        String, nullable=False,
        server_default=text("strftime('%Y-%m-%dT%H:%M:%S', 'now')"),
    )
    processed_at = Column(String, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('FINE_TUNE', 'PREDICT')",
            name="ck_ml_job_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')",
            name="ck_ml_job_status",
        ),
    )


class RPEPrediction(Base):
    __tablename__ = "rpe_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.id"), nullable=False)
    # Fixed: ForeignKey added per review — was missing in initial implementation
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    predicted_rpe = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    model_version = Column(String, nullable=False)
    created_at = Column(
        String, nullable=False,
        server_default=text("strftime('%Y-%m-%dT%H:%M:%S', 'now')"),
    )

    session = relationship("WorkoutSession", back_populates="rpe_predictions")
