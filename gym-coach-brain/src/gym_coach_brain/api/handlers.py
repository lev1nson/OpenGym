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
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from gym_coach_brain.core.onboarding import (
    QUESTIONS,
    QuestionType,
    compute_initial_weights,
    get_available_exercises,
    map_answer_to_coefficients,
)
from gym_coach_brain.core.readiness import calculate_recovery_signal
from gym_coach_brain.data.models import (
    EquipmentType,
    Exercise,
    MuscleGroup,
    MovementPattern,
    ReadinessLog,
    UserProfile,
)

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

    # Build ReadinessLog to compute signal (not yet committed)
    log = ReadinessLog(
        session_date=datetime.now(timezone.utc).date().isoformat(),
        sleep_hours=args.sleep,
        stress_level=args.stress,
        hrv_score=args.hrv,
        recovery_score=0.0,  # will be overwritten
    )

    signal = calculate_recovery_signal(log, science)
    log.recovery_score = signal.coefficient

    session.add(log)
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
