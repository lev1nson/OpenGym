"""
OpenClaw JSON contract handlers — one function per intent.

Handler contract:
- Input: argv (list[str]), session (SQLAlchemy Session, NOT committed here)
- Output: (stdout: str, exit_code: int)
  exit_code 0 = success
  exit_code 1 = user error (invalid input, duplicate, unknown reference)
  exit_code 2 = system error (reserved for api/main.py layer)
- Handler calls session.flush() but NEVER session.commit() — caller commits
"""
import argparse
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gym_coach_brain.adaptation.recap import generate_recap
from gym_coach_brain.adaptation.summary import generate_summary
from gym_coach_brain.core.apre import calculate_apre_adjustment, rpe_from_rir
from gym_coach_brain.core.onboarding import (
    QUESTIONS,
    QuestionType,
    compute_initial_weights,
    get_available_exercises,
    map_answer_to_coefficients,
)
from gym_coach_brain.core.readiness import calculate_recovery_signal
from gym_coach_brain.core.weight_utils import round_to_equipment_increment
from gym_coach_brain.data.models import (
    EquipmentType,
    Exercise,
    MuscleGroup,
    MovementPattern,
    ReadinessLog,
    UserProfile,
    WorkoutSession,
    WorkoutSet,
)
from gym_coach_brain.data.queue import enqueue_predict

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig


def handle_exercise_add(argv: list[str], session: Session) -> tuple[str, int]:
    """Handle exercise_add intent: create a new exercise with full metadata.

    argv format (all flags, NO "exercise add" prefix — intent name is the verb):
        Required: ["--name", "<name>", "--muscle", "<primary>", "--pattern", "<pattern>",
                   "--equipment", "<equip_type>"]
        Optional: ["--secondary", "muscle1,muscle2", "--compound", "true|false",
                   "--stretch", "true|false"]

    Valid muscle names: same as MuscleGroup.name in muscle_groups table
    Valid pattern names: same as MovementPattern.name in movement_patterns table
    Valid equipment values: barbell, dumbbell, machine, cable, bodyweight,
                            resistance_band, pullup_bar, dips_bar
    """
    parser = argparse.ArgumentParser(prog="exercise_add", add_help=False)
    parser.add_argument("--name", required=True)
    parser.add_argument("--muscle", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--equipment", required=True)
    parser.add_argument("--secondary", default="")
    parser.add_argument("--compound", default="true", choices=["true", "false"])
    parser.add_argument("--stretch", default="false", choices=["true", "false"])

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        valid_eq = sorted(e.value for e in EquipmentType)
        return (
            "exercise_add: missing required arguments.\n"
            "Required: --name, --muscle, --pattern, --equipment\n"
            f"Valid equipment: {valid_eq}",
            1,
        )

    # Validate primary muscle group
    muscle = session.query(MuscleGroup).filter_by(name=args.muscle).first()
    if muscle is None:
        return f"Unknown muscle group: {args.muscle!r}", 1

    # Validate movement pattern
    pattern = session.query(MovementPattern).filter_by(name=args.pattern).first()
    if pattern is None:
        return f"Unknown movement pattern: {args.pattern!r}", 1

    # Validate equipment type
    valid_equipment = {e.value for e in EquipmentType}
    if args.equipment not in valid_equipment:
        return (
            f"Invalid equipment type: {args.equipment!r}. "
            f"Valid: {sorted(valid_equipment)}",
            1,
        )

    # Parse and validate secondary muscles
    secondary_ids: list[int] = []
    if args.secondary:
        # Use a set to de-duplicate names while preserving order (via list(dict.fromkeys(...)))
        mg_names = [s.strip() for s in args.secondary.split(",") if s.strip()]
        for mg_name in list(dict.fromkeys(mg_names)):
            mg = session.query(MuscleGroup).filter_by(name=mg_name).first()
            if mg is None:
                return f"Unknown secondary muscle group: {mg_name!r}", 1
            secondary_ids.append(mg.id)

    # Check duplicate name
    existing = session.query(Exercise).filter_by(name=args.name).first()
    if existing is not None:
        return f"Exercise already exists: {args.name!r} (id={existing.id})", 1

    # Create exercise — flush to get ID, caller commits
    exercise = Exercise(
        name=args.name,
        primary_muscle_id=muscle.id,
        movement_pattern_id=pattern.id,
        secondary_muscle_ids=json.dumps(secondary_ids),
        is_compound=(args.compound == "true"),
        stretch_mediated=(args.stretch == "true"),
        equipment_type=args.equipment,
    )
    session.add(exercise)
    session.flush()  # Assigns exercise.id without committing

    return f"Exercise added: {args.name!r} (id={exercise.id})", 0


def _format_question(idx: int, total: int, question) -> str:
    """Format onboarding question for chat output."""
    header = f"Вопрос {idx}/{total}: {question.text}"
    if question.options:
        return f"{header}\nВарианты: {', '.join(question.options)}"
    if question.min_val is not None:
        return f"{header} (диапазон: {question.min_val}-{question.max_val})"
    return header


def _get_or_none(session: Session) -> UserProfile | None:
    """Return first (single) user profile or None."""
    return session.query(UserProfile).first()


def _set_response_data(session: Session, **data: object) -> None:
    """Attach additive JSON payload for the API boundary."""
    payload = session.info.get("response_data", {}).copy()
    payload.update(data)
    session.info["response_data"] = payload


def _load_planned_exercises(workout_session: WorkoutSession) -> list[dict]:
    """Parse planned_exercises safely into a list of dicts."""
    try:
        planned_raw = json.loads(workout_session.planned_exercises or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(planned_raw, list):
        return []
    return [item for item in planned_raw if isinstance(item, dict)]


def _planned_exercises_by_id(workout_session: WorkoutSession) -> dict[int, dict]:
    """Return plan rows keyed by exercise_id, ignoring malformed entries."""
    planned: dict[int, dict] = {}
    for item in _load_planned_exercises(workout_session):
        exercise_id = item.get("exercise_id")
        if isinstance(exercise_id, int):
            planned[exercise_id] = item
    return planned


def _active_workout_session(session: Session) -> WorkoutSession | None:
    """Return the current active workout session, if any."""
    return (
        session.query(WorkoutSession)
        .filter(WorkoutSession.status == "active")
        .order_by(WorkoutSession.id.desc())
        .first()
    )


def handle_onboarding_start(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Start onboarding flow and return first question."""
    del science  # reserved for signature consistency

    parser = argparse.ArgumentParser(prog="onboarding_start", add_help=False)
    parser.add_argument("--reset", action="store_true", default=False)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return "onboarding_start: invalid arguments. Optional: --reset", 1

    profile = _get_or_none(session)
    if profile is not None and profile.onboarding_complete and not args.reset:
        return (
            "⚠️ Профиль уже заполнен. Используйте:\n"
            "  onboarding_start --reset  — начать заново\n"
            "  profile_show              — просмотр профиля\n"
            "  profile_update_*          — обновить отдельные параметры",
            1,
        )

    if profile is None or args.reset:
        if profile is not None and args.reset:
            session.delete(profile)
            session.flush()
        profile = UserProfile()
        session.add(profile)
        session.flush()

    return _format_question(1, len(QUESTIONS), QUESTIONS[0]), 0


def handle_onboarding_answer(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Save onboarding answer and return next question or completion prompt."""
    del science  # reserved for signature consistency

    parser = argparse.ArgumentParser(prog="onboarding_answer", add_help=False)
    parser.add_argument("--question", required=True, dest="question_id")
    parser.add_argument("--answer", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return "onboarding_answer: required --question <id> --answer <value>", 1

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Сначала запустите onboarding_start.", 1

    question = next((q for q in QUESTIONS if q.id == args.question_id), None)
    if question is None:
        return f"Неизвестный вопрос: {args.question_id!r}", 1

    try:
        updates = map_answer_to_coefficients(args.question_id, args.answer)
    except (ValueError, KeyError) as exc:
        return f"Некорректный ответ для вопроса {args.question_id!r}: {exc}", 1

    # Validation: Range check for numeric answers
    if question.type == QuestionType.NUMERIC:
        val = float(args.answer)
        if (question.min_val is not None and val < question.min_val) or \
           (question.max_val is not None and val > question.max_val):
            return (
                f"Значение {args.answer} вне допустимого диапазона "
                f"({question.min_val}-{question.max_val})",
                1,
            )

    for field, value in updates.items():
        setattr(profile, field, value)

    session.flush()

    q_ids = [q.id for q in QUESTIONS]
    current_idx = q_ids.index(args.question_id)
    next_idx = current_idx + 1

    if next_idx < len(QUESTIONS):
        return _format_question(next_idx + 1, len(QUESTIONS), QUESTIONS[next_idx]), 0

    return "Все ответы приняты. Запустите onboarding_complete для завершения.", 0


def handle_onboarding_complete(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Finalize onboarding and compute initial weights."""
    del argv

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Сначала запустите onboarding_start.", 1

    if profile.onboarding_complete:
        return "Профиль уже заполнен. Используйте profile_update_* для изменений.", 1

    if not profile.bodyweight_kg or profile.bodyweight_kg <= 0:
        return "Вес тела не задан. Ответьте на вопрос bodyweight_kg через onboarding_answer.", 1

    try:
        weights = compute_initial_weights(profile, science)
    except ValueError as exc:
        return f"Ошибка вычисления стартовых весов: {exc}", 1

    if weights:
        profile.initial_weight_coefficients = json.dumps(weights)

    profile.onboarding_complete = True
    session.flush()

    weights_summary = (
        "\n".join(f"  {pattern}: {weight} кг" for pattern, weight in weights.items())
        if weights
        else "  (таблица стартовых весов не настроена)"
    )

    return (
        "✅ Онбординг завершён!\n\n"
        "Профиль атлета:\n"
        f"  Вес тела: {profile.bodyweight_kg} кг\n"
        f"  Тренировок в неделю: {profile.training_days_per_week}\n"
        f"  Сплит: {profile.training_split}\n\n"
        f"Стартовые веса по паттернам:\n{weights_summary}",
        0,
    )


def handle_profile_show(argv: list[str], session: Session) -> tuple[str, int]:
    """Show current athlete profile."""
    del argv

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Запустите onboarding_start для создания профиля.", 1

    equipment_list = json.loads(profile.available_equipment or "[]")
    equipment_str = ", ".join(equipment_list) if equipment_list else "не задано"
    weights_dict = json.loads(profile.initial_weight_coefficients or "{}")
    weights_str = (
        "\n".join(f"  {pattern}: {weight} кг" for pattern, weight in weights_dict.items())
        if weights_dict
        else "  не вычислены"
    )
    onboarding_status = "✅ завершён" if profile.onboarding_complete else "⏳ не завершён"

    return (
        "📋 Профиль атлета\n\n"
        f"Статус онбординга: {onboarding_status}\n"
        f"Вес тела: {profile.bodyweight_kg or 'не задан'} кг\n"
        f"Тренировок в неделю: {profile.training_days_per_week}\n"
        f"Сплит: {profile.training_split}\n"
        f"Оборудование: {equipment_str}\n\n"
        f"Стартовые веса:\n{weights_str}",
        0,
    )


def handle_profile_update_equipment(argv: list[str], session: Session) -> tuple[str, int]:
    """Update available equipment in profile."""
    parser = argparse.ArgumentParser(prog="profile_update_equipment", add_help=False)
    parser.add_argument("--equipment", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return "profile_update_equipment: required --equipment <types>", 1

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Запустите onboarding_start.", 1

    try:
        updates = map_answer_to_coefficients("equipment", args.equipment)
    except (ValueError, KeyError) as exc:
        return f"Некорректный тип оборудования: {exc}", 1

    profile.available_equipment = updates["available_equipment"]
    session.flush()

    exercises = get_available_exercises(profile, session)
    equipment_list = json.loads(profile.available_equipment)
    exercise_names = sorted(ex.name for ex in exercises)
    preview_count = 12
    shown = exercise_names[:preview_count]
    shown_text = ", ".join(shown) if shown else "нет"
    overflow = ""
    if len(exercise_names) > preview_count:
        overflow = f"\n… и ещё {len(exercise_names) - preview_count}"

    return (
        f"✅ Оборудование обновлено: {', '.join(equipment_list)}\n"
        f"Всего доступных упражнений: {len(exercises)}\n"
        f"Доступные упражнения: {shown_text}{overflow}",
        0,
    )


def handle_readiness_log(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Handle readiness_log intent: log athlete readiness and compute recovery signal.

    argv format:
        Required: ["--sleep", "<float>", "--stress", "<int>"]
        Optional: ["--hrv", "<float>"]

    sleep: hours slept (positive float, e.g., 7.5)
    stress: stress level 1–10 (int, 1=no stress, 10=max stress)
    hrv: HRV score 0–100 (optional float; omit if no wearable)
    """
    parser = argparse.ArgumentParser(prog="readiness_log", add_help=False)
    parser.add_argument("--sleep", required=True, type=float)
    parser.add_argument("--stress", required=True, type=int)
    parser.add_argument("--hrv", default=None, type=float)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return (
            "readiness_log: missing required arguments.\n"
            "Required: --sleep <hours> --stress <1-10>\n"
            "Optional: --hrv <0-100>",
            1,
        )

    # Validate inputs
    if args.sleep <= 0:
        return "readiness_log: --sleep must be positive (e.g., 7.5 for 7.5 hours)", 1
    if not (1 <= args.stress <= 10):
        return "readiness_log: --stress must be between 1 and 10", 1
    if args.hrv is not None and args.hrv < 0:
        return "readiness_log: --hrv must be >= 0", 1
    if args.hrv is not None and args.hrv > 100:
        return "readiness_log: --hrv must be between 0 and 100", 1

    # Verify user profile exists
    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Сначала запустите onboarding_start.", 1

    session_date = datetime.now(timezone.utc).date().isoformat()

    # Upsert: update existing log for today rather than creating duplicate rows
    log = session.query(ReadinessLog).filter_by(session_date=session_date).first()
    if log is None:
        log = ReadinessLog(
            session_date=session_date,
            sleep_hours=args.sleep,
            stress_level=args.stress,
            hrv_score=args.hrv,
            recovery_score=0.0,
        )
        session.add(log)
    else:
        log.sleep_hours = args.sleep
        log.stress_level = args.stress
        log.hrv_score = args.hrv

    signal = calculate_recovery_signal(log, science)
    log.recovery_score = signal.coefficient

    session.flush()

    hrv_str = f"HRV: {args.hrv:.0f}" if args.hrv is not None else "HRV: не измерен"
    return (
        f"✅ Готовность залоггирована\n\n"
        f"Входные данные:\n"
        f"  Сон: {args.sleep}ч  Стресс: {args.stress}/10  {hrv_str}\n\n"
        f"Коэффициент восстановления: {signal.coefficient:.2f}\n"
        f"  (Компоненты: сон={signal.sleep_component:.2f}, "
        f"стресс={signal.stress_component:.2f}"
        + (f", HRV={signal.hrv_component:.2f}" if signal.hrv_component is not None else "")
        + ")",
        0,
    )


def handle_profile_update_split(argv: list[str], session: Session) -> tuple[str, int]:
    """Update training split and return next workout day hint."""
    split_to_day = {
        "ppl": "push",
        "upper_lower": "upper",
        "full_body": "full_body",
        "custom": "full_body",
    }

    parser = argparse.ArgumentParser(prog="profile_update_split", add_help=False)
    parser.add_argument("--split", required=True, choices=["ppl", "upper_lower", "full_body", "custom"])
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return "profile_update_split: required --split <value>", 1

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Запустите onboarding_start.", 1

    try:
        updates = map_answer_to_coefficients("training_split", args.split)
    except (ValueError, KeyError) as exc:
        return f"Некорректный сплит: {exc}", 1

    profile.training_split = updates["training_split"]
    session.flush()

    return (
        f"✅ Сплит обновлён: {args.split}\n"
        f"Следующая тренировка начнётся с: {split_to_day.get(args.split, 'full_body')}",
        0,
    )


def handle_workout_start(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Generate and persist today's workout plan for the current athlete."""
    from gym_coach_brain.core.planner import WorkoutPlanner

    parser = argparse.ArgumentParser(prog="workout_start", add_help=False)
    parser.add_argument("--sleep-hours", type=float)
    parser.add_argument("--pre-readiness", type=int)
    parser.add_argument("--confirm-second", action="store_true", default=False)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return (
            "workout_start: optional --sleep-hours <5.0|6.5|7.5|9.0> "
            "--pre-readiness <2|5|9> --confirm-second",
            1,
        )

    if args.sleep_hours is not None and args.sleep_hours not in {5.0, 6.5, 7.5, 9.0}:
        return "workout_start: --sleep-hours must be one of 5.0, 6.5, 7.5, 9.0", 1
    if args.pre_readiness is not None and args.pre_readiness not in {2, 5, 9}:
        return "workout_start: --pre-readiness must be one of 2, 5, 9", 1

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Сначала запустите onboarding_start.", 1
    if not profile.onboarding_complete:
        return "Онбординг не завершён. Сначала запустите onboarding_complete.", 1

    today = datetime.now(timezone.utc).date().isoformat()

    active_session = _active_workout_session(session)
    if active_session is not None:
        _set_response_data(
            session,
            orphaned_session=True,
            orphaned_session_id=active_session.id,
            orphaned_session_date=active_session.session_date[:10],
        )
        return (
            "Уже есть активная тренировка. Завершите или разберите текущую сессию перед стартом новой.",
            1,
        )

    completed_today = (
        session.query(WorkoutSession)
        .filter(
            WorkoutSession.status == "completed",
            WorkoutSession.session_date.like(f"{today}%"),
        )
        .order_by(WorkoutSession.id.desc())
        .first()
    )
    if completed_today is not None and not args.confirm_second:
        _set_response_data(
            session,
            second_session_today=True,
            split_day_label=completed_today.split_day_label,
            session_id=completed_today.id,
        )
        return (
            "Сегодня уже есть завершённая тренировка. Повторный старт требует явного подтверждения флагом --confirm-second.",
            1,
        )

    readiness_log = session.query(ReadinessLog).filter_by(session_date=today).first()
    recovery_signal = (
        calculate_recovery_signal(readiness_log, science)
        if readiness_log is not None
        else None
    )

    forced_split_day_label = (
        completed_today.split_day_label
        if completed_today is not None and args.confirm_second
        else None
    )
    plan = WorkoutPlanner().generate(
        profile,
        science,
        session,
        recovery_signal,
        forced_split_day_label=forced_split_day_label,
    )
    planned_exercises = [asdict(exercise) for exercise in plan.exercises]

    workout_session = WorkoutSession(
        session_date=today,
        status="active",
        methodology=getattr(profile, "goal", None) or "hypertrophy",
        planned_exercises=json.dumps(planned_exercises),
        split_day_label=plan.split_day_label,
        sleep_hours=args.sleep_hours,
        pre_readiness=args.pre_readiness,
    )
    session.add(workout_session)
    session.flush()  # assigns workout_session.id

    # Route through data.queue so invariants (idempotency, session_ids format) are enforced
    enqueue_predict(workout_session.id, db_session=session)
    session.flush()

    lines = [
        f"Сегодня — {', '.join(plan.muscle_groups_today)}",
        "",
    ]
    for index, exercise in enumerate(plan.exercises, start=1):
        lines.append(
            f"{index}. {exercise.exercise_name} (id:{exercise.exercise_id}): "
            f"{exercise.sets}x{exercise.rep_range[0]}-{exercise.rep_range[1]} "
            f"@ {exercise.target_weight_kg:.1f}кг"
        )

    if plan.skipped_groups:
        lines.extend(["", f"Пропущенные группы: {', '.join(plan.skipped_groups)}"])
    if plan.warnings:
        lines.extend(["", *plan.warnings])

    _set_response_data(
        session,
        session_id=workout_session.id,
        split_day_label=plan.split_day_label,
    )
    return "\n".join(lines), 0


def handle_workout_status(argv: list[str], session: Session) -> tuple[str, int]:
    """Show the active workout plan plus logged-set progress."""
    del argv

    workout_session = _active_workout_session(session)
    if workout_session is None:
        return "Активная тренировка не найдена.", 1

    planned_by_id = _planned_exercises_by_id(workout_session)
    logged_sets = (
        session.query(WorkoutSet)
        .filter(WorkoutSet.session_id == workout_session.id)
        .order_by(WorkoutSet.exercise_id, WorkoutSet.set_number)
        .all()
    )
    sets_by_exercise: dict[int, list[WorkoutSet]] = defaultdict(list)
    for workout_set in logged_sets:
        sets_by_exercise[workout_set.exercise_id].append(workout_set)

    lines = [
        f"Активная тренировка #{workout_session.id}",
        f"Дата: {workout_session.session_date[:10]}",
    ]
    if workout_session.split_day_label:
        lines.append(f"Сплит: {workout_session.split_day_label}")
    lines.append("")

    for index, exercise in enumerate(_load_planned_exercises(workout_session), start=1):
        exercise_id = exercise.get("exercise_id")
        if not isinstance(exercise_id, int):
            continue
        planned_sets = exercise.get("sets") if isinstance(exercise.get("sets"), int) else 0
        done_sets = len(sets_by_exercise.get(exercise_id, []))
        status = (
            f"✅ {done_sets}/{planned_sets}"
            if done_sets > 0
            else "⏳ not started"
        )
        lines.append(
            f"{index}. {exercise.get('exercise_name', f'exercise_{exercise_id}')} "
            f"(id:{exercise_id}): {status}"
        )
        for logged_set in sets_by_exercise.get(exercise_id, []):
            rir_text = "?" if logged_set.rir is None else str(logged_set.rir)
            rpe_text = "?" if logged_set.rpe is None else f"{logged_set.rpe:.1f}"
            lines.append(
                f"   set {logged_set.set_number}: "
                f"{logged_set.weight_kg:.1f}кг x {logged_set.reps} "
                f"(RIR {rir_text}, RPE {rpe_text})"
            )

    _set_response_data(session, session_id=workout_session.id)
    return "\n".join(lines), 0


def handle_workout_log_set(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Persist one structured set for the active workout session."""
    parser = argparse.ArgumentParser(prog="workout_log_set", add_help=False)
    parser.add_argument("--exercise-id", required=True, type=int)
    parser.add_argument("--set-number", required=True, type=int)
    parser.add_argument("--weight-kg", required=True, type=float)
    parser.add_argument("--reps", required=True, type=int)
    parser.add_argument("--rir", required=True, type=int)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return (
            "workout_log_set: required --exercise-id --set-number --weight-kg --reps --rir",
            1,
        )

    if args.weight_kg < 0.0:
        return "workout_log_set: --weight-kg must be >= 0.0", 1
    if args.reps < 1:
        return "workout_log_set: --reps must be >= 1", 1
    if args.set_number < 1:
        return "workout_log_set: --set-number must be >= 1", 1
    if args.rir not in {0, 1, 2, 3, 4}:
        return "workout_log_set: --rir must be between 0 and 4", 1

    workout_session = _active_workout_session(session)
    if workout_session is None:
        return "Активная тренировка не найдена.", 1

    planned_by_id = _planned_exercises_by_id(workout_session)
    planned_exercise = planned_by_id.get(args.exercise_id)
    if planned_exercise is None:
        return f"exercise_id {args.exercise_id} не найден в активном плане.", 1

    duplicate = (
        session.query(WorkoutSet)
        .filter_by(
            session_id=workout_session.id,
            exercise_id=args.exercise_id,
            set_number=args.set_number,
        )
        .first()
    )
    if duplicate is not None:
        return "Такой подход уже записан для этого упражнения.", 1

    exercise = session.get(Exercise, args.exercise_id)
    if exercise is None:
        return f"Упражнение с id={args.exercise_id} не найдено.", 1

    workout_set = WorkoutSet(
        session_id=workout_session.id,
        exercise_id=args.exercise_id,
        set_number=args.set_number,
        weight_kg=args.weight_kg,
        reps=args.reps,
        rir=args.rir,
        rpe=rpe_from_rir(args.rir),
    )
    session.add(workout_set)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return "Такой подход уже записан для этого упражнения.", 1

    rep_range = planned_exercise.get("rep_range", [])
    target_reps = rep_range[0] if isinstance(rep_range, list) and rep_range else args.reps
    recommended_weight = calculate_apre_adjustment(
        actual_reps=args.reps,
        target_reps=int(target_reps),
        current_weight=args.weight_kg,
        science=science,
    )
    rounded_recommendation = round_to_equipment_increment(
        recommended_weight,
        EquipmentType(exercise.equipment_type),
        science,
    )

    lines = [
        f"✅ Подход записан: {exercise.name} — {args.weight_kg:.1f}кг x {args.reps}",
        f"RIR {args.rir} → RPE {workout_set.rpe:.1f}",
        f"Рекомендация на следующий подход: {rounded_recommendation:.1f}кг",
    ]

    planned_sets = planned_exercise.get("sets") if isinstance(planned_exercise.get("sets"), int) else 0
    if args.set_number > planned_sets:
        lines.append("⚠️ Подход сверх плана сохранён и не был отклонён.")

    _set_response_data(session, session_id=workout_session.id)
    return "\n".join(lines), 0


def handle_workout_finish(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Complete the active workout session and return the generated summary."""
    del argv

    workout_session = _active_workout_session(session)
    if workout_session is None:
        return "Активная тренировка не найдена.", 1

    workout_session.status = "completed"
    session.flush()
    summary = generate_summary(workout_session, session, science)
    _set_response_data(session, session_id=workout_session.id)
    return summary, 0


def handle_workout_recap(argv: list[str], session: Session) -> tuple[str, int]:
    """Return the recap for the latest completed session."""
    del argv
    return generate_recap(session), 0


def handle_workout_summary(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Return a summary for the requested or latest completed session."""
    parser = argparse.ArgumentParser(prog="workout_summary", add_help=False)
    parser.add_argument("--session-id", type=int)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return "workout_summary: optional --session-id <id>", 1

    if args.session_id is not None:
        workout_session = session.get(WorkoutSession, args.session_id)
        if workout_session is None or workout_session.status != "completed":
            return "Завершённая тренировка с таким session_id не найдена.", 1
    else:
        workout_session = (
            session.query(WorkoutSession)
            .filter(WorkoutSession.status == "completed")
            .order_by(WorkoutSession.session_date.desc(), WorkoutSession.id.desc())
            .first()
        )
        if workout_session is None:
            return "История завершённых тренировок пока пуста.", 1

    _set_response_data(session, session_id=workout_session.id)
    return generate_summary(workout_session, session, science), 0
