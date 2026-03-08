# Story 3.5: API handlers онбординга, профиля оборудования и просмотра профиля

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an athlete,
I want to complete onboarding through OpenClaw chat and view my profile,
so that gym-coach-brain personalizes my training based on my parameters.

## Acceptance Criteria

**Given** `core/onboarding.py` и `data/models.py` готовы (Stories 3.3 и 3.4 завершены)

**When** OpenClaw отправляет интент `onboarding_start`
**Then** возвращается первый вопрос из шаблона в формате `{"intent": "onboarding_start", "stdout": "...", "exit_code": 0}`

**And** интент `onboarding_answer` с `--question <id> --answer <value>` сохраняет коэффициент в `UserProfile` и возвращает следующий вопрос (или подтверждение если это последний)

**And** интент `onboarding_complete` вызывает `compute_initial_weights`, сохраняет `UserProfile.initial_weight_coefficients` как JSON и устанавливает `onboarding_complete=True`; возвращает подтверждение

**And** интент `profile_show` возвращает читаемый текст со всеми параметрами атлета и оборудованием

**And** повторный `onboarding_start` при существующем профиле с `onboarding_complete=True` возвращает предупреждение с опцией перезаписи (`--reset` flag)

**And** интент `profile_update_equipment --equipment <type1,type2,...>` обновляет `UserProfile.available_equipment`; возвращает подтверждение с обновлённым списком доступных упражнений

**And** интент `profile_update_split --split <value>` обновляет `UserProfile.training_split`; возвращает подтверждение с новым сплитом и информацией о следующей стартовой тренировке (PPL → `push`, UL → `upper`, full_body → `full_body`)

**And** `pytest tests/test_api/test_handlers.py` покрывает все 6 новых интентов (happy path + key error cases)

## Tasks / Subtasks

- [x] **Верифицировать prerequisites** (AC: baseline)
  - [x] Подтвердить Story 3.3 выполнена: `tests/conftest.py` существует с fixtures `db_session`, `mock_science_config`
  - [x] Подтвердить Story 3.4 выполнена: `src/gym_coach_brain/core/onboarding.py` существует
  - [x] `cd gym-coach-brain && uv run pytest` — убедиться baseline тесты PASS (97 + Story 3.3 тесты + Story 3.4 тесты)

- [x] **Добавить `handle_onboarding_start` в `api/handlers.py`** (AC: onboarding_start)
  - [x] Сигнатура: `handle_onboarding_start(argv: list[str], session: Session, science: ScienceConfig) -> tuple[str, int]`
  - [x] Проверить существующий `UserProfile` в session (первая запись)
  - [x] Если профиль существует И `onboarding_complete=True`: проверить `--reset` flag; если нет флага — вернуть предупреждение с инструкцией, `exit_code=1`
  - [x] Если `--reset` указан или профиль не существует: создать новый `UserProfile()`, добавить в session, flush
  - [x] Вернуть текст первого вопроса из `QUESTIONS[0]` с опциями, `exit_code=0`
  - [x] Формат ответа: `"Вопрос 1/9: {question.text}\nВарианты: {options}"` для choice, `"Вопрос 1/9: {question.text} (диапазон: {min}-{max})"` для numeric

- [x] **Добавить `handle_onboarding_answer` в `api/handlers.py`** (AC: onboarding_answer)
  - [x] Сигнатура: `handle_onboarding_answer(argv: list[str], session: Session, science: ScienceConfig) -> tuple[str, int]`
  - [x] Аргументы: `--question <question_id>` (required), `--answer <value>` (required)
  - [x] Найти `UserProfile` (первая запись); если нет — вернуть ошибку: "Сначала запустите onboarding_start", `exit_code=1`
  - [x] Найти вопрос в `QUESTIONS` по `question_id`; если не найден — `exit_code=1`
  - [x] Вызвать `map_answer_to_coefficients(question_id, answer)` и применить результат к `UserProfile` через `setattr`
  - [x] Если `map_answer_to_coefficients` бросает `ValueError` — поймать, вернуть `exit_code=1` с описанием ошибки
  - [x] Сохранить ответ `experience_level` в `user_profile._experience_level` (необходим для `compute_initial_weights` в `onboarding_complete`)
  - [x] `session.flush()`
  - [x] Определить следующий вопрос: найти следующий после `question_id` в `QUESTIONS`
  - [x] Если есть следующий вопрос: вернуть его текст с опциями, `exit_code=0`
  - [x] Если это был последний вопрос: вернуть подсказку `"Все ответы приняты. Запустите onboarding_complete для завершения."`, `exit_code=0`

- [x] **Добавить `handle_onboarding_complete` в `api/handlers.py`** (AC: onboarding_complete)
  - [x] Сигнатура: `handle_onboarding_complete(argv: list[str], session: Session, science: ScienceConfig) -> tuple[str, int]`
  - [x] Найти `UserProfile`; если нет — `exit_code=1`
  - [x] Если `onboarding_complete=True` — вернуть `exit_code=1`: "Профиль уже заполнен. Используйте profile_update_* для изменений."
  - [x] Проверить `bodyweight_kg` задан и > 0; если нет — `exit_code=1`
  - [x] Вызвать `compute_initial_weights(user_profile, science)` — если бросает `ValueError`: `exit_code=1`
  - [x] Сохранить `user_profile.initial_weight_coefficients = json.dumps(weights_dict)` (если weights_dict непустой)
  - [x] Установить `user_profile.onboarding_complete = True`
  - [x] `session.flush()`
  - [x] Вернуть подтверждение с summary профиля, `exit_code=0`

- [x] **Добавить `handle_profile_show` в `api/handlers.py`** (AC: profile_show)
  - [x] Сигнатура: `handle_profile_show(argv: list[str], session: Session) -> tuple[str, int]`
  - [x] Найти `UserProfile`; если нет — `exit_code=1`: "Профиль не найден. Запустите onboarding_start"
  - [x] Вернуть форматированный текст: bodyweight, training_split, training_days_per_week, onboarding_complete статус, available_equipment list, initial_weight_coefficients dict (если есть)
  - [x] `exit_code=0`

- [x] **Добавить `handle_profile_update_equipment` в `api/handlers.py`** (AC: profile_update_equipment)
  - [x] Сигнатура: `handle_profile_update_equipment(argv: list[str], session: Session) -> tuple[str, int]`
  - [x] Аргументы: `--equipment <type1,type2,...>` (required, comma-separated или JSON list)
  - [x] Найти `UserProfile`; если нет — `exit_code=1`
  - [x] Вызвать `map_answer_to_coefficients("equipment", args.equipment)` для валидации и получения JSON
  - [x] Применить `user_profile.available_equipment = result["available_equipment"]`
  - [x] `session.flush()`
  - [x] Загрузить список упражнений через `get_available_exercises(user_profile, session)` для отображения
  - [x] Вернуть подтверждение с новым списком оборудования и количеством доступных упражнений, `exit_code=0`

- [x] **Добавить `handle_profile_update_split` в `api/handlers.py`** (AC: profile_update_split)
  - [x] Сигнатура: `handle_profile_update_split(argv: list[str], session: Session) -> tuple[str, int]`
  - [x] Аргументы: `--split <value>` (required; valid: `ppl`, `upper_lower`, `full_body`, `custom`)
  - [x] Найти `UserProfile`; если нет — `exit_code=1`
  - [x] Вызвать `map_answer_to_coefficients("training_split", args.split)` для валидации и маппинга
  - [x] Если бросает `ValueError` — `exit_code=1`
  - [x] Применить `user_profile.training_split = result["training_split"]`
  - [x] `session.flush()`
  - [x] Определить fallback стартовый день: `ppl` → `push`, `upper_lower` → `upper`, `full_body` → `full_body`, `custom` → `full_body`
  - [x] Вернуть подтверждение с новым сплитом и стартовым днём следующей тренировки, `exit_code=0`

- [x] **Добавить тесты в `tests/test_api/test_handlers.py`** (AC: все тесты PASS)
  - [x] Тест: `test_onboarding_start_returns_first_question` — проверить exit_code=0, stdout содержит текст первого вопроса
  - [x] Тест: `test_onboarding_start_with_existing_complete_profile_warns` — exit_code=1, stdout содержит предупреждение
  - [x] Тест: `test_onboarding_start_reset_creates_new_profile` — `--reset` flag, exit_code=0
  - [x] Тест: `test_onboarding_answer_bodyweight` — `--question bodyweight_kg --answer 75`, exit_code=0, profile.bodyweight_kg==75.0
  - [x] Тест: `test_onboarding_answer_training_split` — `--question training_split --answer full_body`, exit_code=0
  - [x] Тест: `test_onboarding_answer_invalid_question_id` — exit_code=1
  - [x] Тест: `test_onboarding_answer_invalid_split_value` — `--answer invalid`, exit_code=1
  - [x] Тест: `test_onboarding_complete_computes_weights` — полный профиль с bodyweight+experience_level → exit_code=0, profile.initial_weight_coefficients содержит JSON dict, profile.onboarding_complete=True
  - [x] Тест: `test_onboarding_complete_without_bodyweight_fails` — exit_code=1
  - [x] Тест: `test_profile_show_returns_formatted_text` — exit_code=0, stdout содержит ключевые поля
  - [x] Тест: `test_profile_show_no_profile_returns_error` — exit_code=1
  - [x] Тест: `test_profile_update_equipment_valid` — `--equipment bodyweight,barbell`, exit_code=0
  - [x] Тест: `test_profile_update_equipment_invalid_type` — `--equipment invalid_equip`, exit_code=1
  - [x] Тест: `test_profile_update_split_ppl` — `--split ppl`, exit_code=0, stdout содержит "push"
  - [x] Тест: `test_profile_update_split_invalid` — `--split invalid`, exit_code=1

- [x] **Финальная верификация**
  - [x] `uv run pytest tests/test_api/test_handlers.py -v` — все тесты PASS
  - [x] `uv run pytest -v` — все тесты PASS (baseline + Story 3.3 + 3.4 + новые)

### Review Follow-ups (AI)
- [x] [AI-Review][HIGH] Include initial weights summary in `handle_onboarding_complete` output [handlers.py:214]
- [x] [AI-Review][HIGH] Return full list of available exercises in `handle_profile_update_equipment` [handlers.py:284]
- [x] [AI-Review][MEDIUM] Track and stage newly created files: handlers.py and test_handlers.py
- [x] [AI-Review][MEDIUM] Sync implementation with Dev Notes logic (missing summaries) [handlers.py]
- [x] [AI-Review][LOW] Remove redundant transient attribute `_experience_level` and use persistent column [handlers.py:177]
- [x] [AI-Review][LOW] Polish output formatting for consistency with UX designs [handlers.py]

## Dev Notes

### ⚠️ Критические пререквизиты

**Обязательно проверить перед началом:**
1. Story 3.3 завершена: `tests/conftest.py` существует с `db_session`, `mock_science_config`
2. Story 3.4 завершена: `src/gym_coach_brain/core/onboarding.py` существует с `QUESTIONS`, `map_answer_to_coefficients`, `compute_initial_weights`, `get_available_exercises`
3. `uv run pytest` baseline проходит без ошибок

---

### Текущее состояние codebase (актуально на 2026-03-08)

**Что УЖЕ существует:**
```
src/gym_coach_brain/
├── api/
│   └── handlers.py        ← СУЩЕСТВУЕТ (handle_exercise_add) — ДОБАВЛЯТЬ функции, не заменять файл
├── core/
│   ├── science.py         ← СУЩЕСТВУЕТ (ScienceConfig, load_science_config)
│   └── onboarding.py      ← СОЗДАЁТСЯ в Story 3.4 (prerequisite)
├── data/
│   ├── models.py          ← СУЩЕСТВУЕТ (UserProfile, Exercise, EquipmentType, TrainingSplit)
│   └── seed.py            ← СУЩЕСТВУЕТ
└── exceptions.py          ← СУЩЕСТВУЕТ
tests/
├── conftest.py            ← СОЗДАЁТСЯ в Story 3.3 (prerequisite)
└── test_api/
    ├── __init__.py        ← СУЩЕСТВУЕТ
    └── test_handlers.py   ← СУЩЕСТВУЕТ (7 тестов для exercise_add) — ДОБАВЛЯТЬ тесты, не заменять
```

**Что создаётся/изменяется в Story 3.5:**
```
src/gym_coach_brain/api/
└── handlers.py            ← ИЗМЕНИТЬ: добавить 6 новых handler функций
tests/test_api/
└── test_handlers.py       ← ИЗМЕНИТЬ: добавить ~15 новых тестов для новых handlers
```

**⚠️ ВАЖНО: ТОЛЬКО ДОБАВЛЯТЬ в существующие файлы — НЕ удалять `handle_exercise_add` и существующие тесты!**

---

### Полная реализация `api/handlers.py` — новые функции

```python
# Добавить в начало файла (к существующим imports):
import argparse
import json
from datetime import datetime

from sqlalchemy.orm import Session

from gym_coach_brain.core.onboarding import (
    QUESTIONS,
    compute_initial_weights,
    get_available_exercises,
    map_answer_to_coefficients,
)
from gym_coach_brain.data.models import EquipmentType, Exercise, MuscleGroup, MovementPattern, TrainingSplit, UserProfile

# NOTE: ScienceConfig import — используй TYPE_CHECKING для избежания circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig


def _format_question(idx: int, total: int, question) -> str:
    """Format a question for display."""
    header = f"Вопрос {idx}/{total}: {question.text}"
    if question.options:
        opts = ", ".join(question.options)
        return f"{header}\nВарианты: {opts}"
    elif question.min_val is not None:
        return f"{header} (диапазон: {question.min_val}–{question.max_val})"
    return header


def _get_or_none(session: Session) -> "UserProfile | None":
    """Return the first (and only) UserProfile, or None."""
    return session.query(UserProfile).first()


def handle_onboarding_start(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Handle onboarding_start: returns first question or warns if profile exists.

    argv format (all optional):
        ["--reset"]   — force re-onboarding even if profile already complete
    """
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

    first_q = QUESTIONS[0]
    return _format_question(1, len(QUESTIONS), first_q), 0


def handle_onboarding_answer(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Handle onboarding_answer: save answer to UserProfile, return next question.

    argv format:
        Required: ["--question", "<question_id>", "--answer", "<value>"]
    """
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

    # Validate question exists
    question = next((q for q in QUESTIONS if q.id == args.question_id), None)
    if question is None:
        valid_ids = [q.id for q in QUESTIONS]
        return f"Неизвестный вопрос: {args.question_id!r}. Допустимые: {valid_ids}", 1

    # Map answer to coefficients and apply to profile
    try:
        updates = map_answer_to_coefficients(args.question_id, args.answer)
    except (ValueError, KeyError) as exc:
        return f"Некорректный ответ для вопроса {args.question_id!r}: {exc}", 1

    for field, value in updates.items():
        setattr(profile, field, value)

    # Persist experience_level as transient attribute for use by onboarding_complete
    if args.question_id == "experience_level":
        profile._experience_level = args.answer  # type: ignore[attr-defined]

    session.flush()

    # Find next question
    q_ids = [q.id for q in QUESTIONS]
    current_idx = q_ids.index(args.question_id)
    next_idx = current_idx + 1

    if next_idx < len(QUESTIONS):
        next_q = QUESTIONS[next_idx]
        return _format_question(next_idx + 1, len(QUESTIONS), next_q), 0
    else:
        return (
            "✅ Все ответы приняты!\n"
            "Запустите onboarding_complete для завершения и вычисления стартовых весов.",
            0,
        )


def handle_onboarding_complete(
    argv: list[str], session: Session, science: "ScienceConfig"
) -> tuple[str, int]:
    """Handle onboarding_complete: compute initial weights, finalize profile.

    argv format: no arguments required
    """
    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Сначала запустите onboarding_start.", 1

    if profile.onboarding_complete:
        return (
            "Профиль уже заполнен. Используйте profile_update_* для изменений.",
            1,
        )

    if not profile.bodyweight_kg or profile.bodyweight_kg <= 0:
        return (
            "Вес тела не задан. Ответьте на вопрос bodyweight_kg через onboarding_answer.",
            1,
        )

    try:
        weights = compute_initial_weights(profile, science)
    except ValueError as exc:
        return f"Ошибка вычисления стартовых весов: {exc}", 1

    if weights:
        profile.initial_weight_coefficients = json.dumps(weights)

    profile.onboarding_complete = True
    session.flush()

    weights_summary = "\n".join(
        f"  {pattern}: {weight} кг" for pattern, weight in weights.items()
    ) if weights else "  (таблица стартовых весов не настроена)"

    return (
        f"✅ Онбординг завершён!\n\n"
        f"Профиль атлета:\n"
        f"  Вес тела: {profile.bodyweight_kg} кг\n"
        f"  Тренировок в неделю: {profile.training_days_per_week}\n"
        f"  Сплит: {profile.training_split}\n\n"
        f"Стартовые веса по паттернам:\n{weights_summary}",
        0,
    )


def handle_profile_show(argv: list[str], session: Session) -> tuple[str, int]:
    """Handle profile_show: return formatted athlete profile.

    argv format: no arguments
    """
    profile = _get_or_none(session)
    if profile is None:
        return (
            "Профиль не найден. Запустите onboarding_start для создания профиля.",
            1,
        )

    equipment_list = json.loads(profile.available_equipment or "[]")
    equipment_str = ", ".join(equipment_list) if equipment_list else "не задано"

    weights_dict = json.loads(profile.initial_weight_coefficients or "{}")
    if weights_dict:
        weights_str = "\n".join(
            f"  {p}: {w} кг" for p, w in weights_dict.items()
        )
    else:
        weights_str = "  не вычислены"

    status = "✅ завершён" if profile.onboarding_complete else "⏳ не завершён"

    return (
        f"📋 Профиль атлета\n\n"
        f"Статус онбординга: {status}\n"
        f"Вес тела: {profile.bodyweight_kg or 'не задан'} кг\n"
        f"Тренировок в неделю: {profile.training_days_per_week}\n"
        f"Сплит: {profile.training_split}\n"
        f"Оборудование: {equipment_str}\n\n"
        f"Стартовые веса:\n{weights_str}",
        0,
    )


def handle_profile_update_equipment(
    argv: list[str], session: Session
) -> tuple[str, int]:
    """Handle profile_update_equipment: update available_equipment in UserProfile.

    argv format:
        Required: ["--equipment", "barbell,bodyweight"]  or JSON list
    """
    parser = argparse.ArgumentParser(prog="profile_update_equipment", add_help=False)
    parser.add_argument("--equipment", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        valid_eq = sorted(e.value for e in EquipmentType)
        return (
            f"profile_update_equipment: required --equipment <types>\n"
            f"Valid types: {valid_eq}",
            1,
        )

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Запустите onboarding_start.", 1

    try:
        updates = map_answer_to_coefficients("equipment", args.equipment)
    except (ValueError, KeyError) as exc:
        return f"Некорректный тип оборудования: {exc}", 1

    profile.available_equipment = updates["available_equipment"]
    session.flush()

    # Load available exercises for summary
    exercises = get_available_exercises(profile, session)
    equipment_list = json.loads(profile.available_equipment)
    equipment_str = ", ".join(equipment_list) if equipment_list else "нет"

    return (
        f"✅ Оборудование обновлено: {equipment_str}\n"
        f"Доступно упражнений: {len(exercises)}",
        0,
    )


def handle_profile_update_split(
    argv: list[str], session: Session
) -> tuple[str, int]:
    """Handle profile_update_split: update training_split in UserProfile.

    argv format:
        Required: ["--split", "ppl|upper_lower|full_body|custom"]
    """
    _SPLIT_NEXT_DAY = {
        "ppl": "push",
        "upper_lower": "upper",
        "full_body": "full_body",
        "custom": "full_body",
    }

    parser = argparse.ArgumentParser(prog="profile_update_split", add_help=False)
    parser.add_argument(
        "--split",
        required=True,
        choices=["ppl", "upper_lower", "full_body", "custom"],
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return (
            "profile_update_split: required --split <value>\n"
            "Valid: ppl, upper_lower, full_body, custom",
            1,
        )

    profile = _get_or_none(session)
    if profile is None:
        return "Профиль не найден. Запустите onboarding_start.", 1

    try:
        updates = map_answer_to_coefficients("training_split", args.split)
    except (ValueError, KeyError) as exc:
        return f"Некорректный сплит: {exc}", 1

    profile.training_split = updates["training_split"]
    session.flush()

    next_day = _SPLIT_NEXT_DAY.get(args.split, "full_body")
    return (
        f"✅ Сплит обновлён: {args.split}\n"
        f"Следующая тренировка начнётся с: {next_day}",
        0,
    )
```

---

### Полная реализация тестов (добавить в конец `tests/test_api/test_handlers.py`)

```python
# ─── NEW IMPORTS (добавить к существующим) ────────────────────────────────────
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gym_coach_brain.api.handlers import (
    handle_onboarding_answer,
    handle_onboarding_complete,
    handle_onboarding_start,
    handle_profile_show,
    handle_profile_update_equipment,
    handle_profile_update_split,
)
from gym_coach_brain.core.science import ScienceConfig
from gym_coach_brain.data.models import Base, TrainingSplit, UserProfile
from gym_coach_brain.data.seed import seed_all


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def onboarding_session():
    """In-memory session with seed data for onboarding tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_all(session)
        session.commit()
        yield session


@pytest.fixture
def mock_science():
    """Minimal ScienceConfig with initial_weight_table for testing."""
    cfg = ScienceConfig(version="test-1.0")
    cfg.__dict__["initial_weight_table"] = {
        "beginner": {
            "horizontal_push": 0.40, "vertical_push": 0.30,
            "horizontal_pull": 0.35, "vertical_pull": 0.30,
            "squat": 0.60, "hinge": 0.50, "carry": 0.25,
        },
        "intermediate": {
            "horizontal_push": 0.70, "vertical_push": 0.55,
            "horizontal_pull": 0.60, "vertical_pull": 0.55,
            "squat": 1.00, "hinge": 0.90, "carry": 0.45,
        },
    }
    return cfg


# ─── onboarding_start ─────────────────────────────────────────────────────────

def test_onboarding_start_returns_first_question(onboarding_session, mock_science):
    stdout, exit_code = handle_onboarding_start([], onboarding_session, mock_science)
    assert exit_code == 0
    assert "Вопрос 1/" in stdout  # First question


def test_onboarding_start_creates_user_profile(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)
    profile = onboarding_session.query(UserProfile).first()
    assert profile is not None


def test_onboarding_start_with_existing_complete_profile_warns(onboarding_session, mock_science):
    profile = UserProfile(onboarding_complete=True)
    onboarding_session.add(profile)
    onboarding_session.flush()

    stdout, exit_code = handle_onboarding_start([], onboarding_session, mock_science)
    assert exit_code == 1
    assert "Профиль уже заполнен" in stdout


def test_onboarding_start_reset_flag_allowed(onboarding_session, mock_science):
    profile = UserProfile(onboarding_complete=True)
    onboarding_session.add(profile)
    onboarding_session.flush()

    stdout, exit_code = handle_onboarding_start(["--reset"], onboarding_session, mock_science)
    assert exit_code == 0


# ─── onboarding_answer ────────────────────────────────────────────────────────

def test_onboarding_answer_bodyweight(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "bodyweight_kg", "--answer", "75"],
        onboarding_session, mock_science,
    )
    assert exit_code == 0
    profile = onboarding_session.query(UserProfile).first()
    assert profile.bodyweight_kg == 75.0


def test_onboarding_answer_training_split(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "training_split", "--answer", "full_body"],
        onboarding_session, mock_science,
    )
    assert exit_code == 0
    profile = onboarding_session.query(UserProfile).first()
    assert profile.training_split == TrainingSplit.full_body


def test_onboarding_answer_unknown_question_id_fails(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "nonexistent_q", "--answer", "value"],
        onboarding_session, mock_science,
    )
    assert exit_code == 1


def test_onboarding_answer_invalid_split_value_fails(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_answer(
        ["--question", "training_split", "--answer", "invalid_split"],
        onboarding_session, mock_science,
    )
    assert exit_code == 1


def test_onboarding_answer_no_profile_fails(onboarding_session, mock_science):
    stdout, exit_code = handle_onboarding_answer(
        ["--question", "bodyweight_kg", "--answer", "75"],
        onboarding_session, mock_science,
    )
    assert exit_code == 1


# ─── onboarding_complete ──────────────────────────────────────────────────────

def _setup_profile_for_complete(session, science, bodyweight=70.0, experience="intermediate"):
    """Helper: create and answer onboarding questions to enable onboarding_complete."""
    handle_onboarding_start([], session, science)
    handle_onboarding_answer(["--question", "bodyweight_kg", "--answer", str(bodyweight)], session, science)
    handle_onboarding_answer(["--question", "experience_level", "--answer", experience], session, science)
    handle_onboarding_answer(["--question", "training_split", "--answer", "full_body"], session, science)
    handle_onboarding_answer(["--question", "training_days_per_week", "--answer", "4"], session, science)
    handle_onboarding_answer(["--question", "equipment", "--answer", "bodyweight"], session, science)


def test_onboarding_complete_finalizes_profile(onboarding_session, mock_science):
    _setup_profile_for_complete(onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_complete([], onboarding_session, mock_science)
    assert exit_code == 0

    profile = onboarding_session.query(UserProfile).first()
    assert profile.onboarding_complete is True


def test_onboarding_complete_computes_initial_weights(onboarding_session, mock_science):
    _setup_profile_for_complete(onboarding_session, mock_science, bodyweight=80.0, experience="intermediate")

    stdout, exit_code = handle_onboarding_complete([], onboarding_session, mock_science)
    assert exit_code == 0

    profile = onboarding_session.query(UserProfile).first()
    weights = json.loads(profile.initial_weight_coefficients or "{}")
    # intermediate, 80kg: squat = 80 * 1.00 = 80.0
    assert weights.get("squat") == pytest.approx(80.0, rel=1e-2)


def test_onboarding_complete_without_bodyweight_fails(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_complete([], onboarding_session, mock_science)
    assert exit_code == 1


def test_onboarding_complete_twice_fails(onboarding_session, mock_science):
    _setup_profile_for_complete(onboarding_session, mock_science)
    handle_onboarding_complete([], onboarding_session, mock_science)

    stdout, exit_code = handle_onboarding_complete([], onboarding_session, mock_science)
    assert exit_code == 1


# ─── profile_show ─────────────────────────────────────────────────────────────

def test_profile_show_returns_formatted_text(onboarding_session, mock_science):
    _setup_profile_for_complete(onboarding_session, mock_science)
    handle_onboarding_complete([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_show([], onboarding_session)
    assert exit_code == 0
    assert "Профиль атлета" in stdout
    assert "Вес тела" in stdout
    assert "Сплит" in stdout


def test_profile_show_no_profile_returns_error(onboarding_session):
    stdout, exit_code = handle_profile_show([], onboarding_session)
    assert exit_code == 1


# ─── profile_update_equipment ─────────────────────────────────────────────────

def test_profile_update_equipment_valid(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_equipment(
        ["--equipment", "bodyweight,barbell"],
        onboarding_session,
    )
    assert exit_code == 0
    profile = onboarding_session.query(UserProfile).first()
    eq = json.loads(profile.available_equipment)
    assert "bodyweight" in eq
    assert "barbell" in eq


def test_profile_update_equipment_invalid_type_fails(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_equipment(
        ["--equipment", "invalid_equipment_type"],
        onboarding_session,
    )
    assert exit_code == 1


def test_profile_update_equipment_no_profile_fails(onboarding_session):
    stdout, exit_code = handle_profile_update_equipment(
        ["--equipment", "bodyweight"],
        onboarding_session,
    )
    assert exit_code == 1


# ─── profile_update_split ─────────────────────────────────────────────────────

def test_profile_update_split_ppl(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_split(["--split", "ppl"], onboarding_session)
    assert exit_code == 0
    assert "push" in stdout  # PPL → starts with push


def test_profile_update_split_upper_lower(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_split(["--split", "upper_lower"], onboarding_session)
    assert exit_code == 0
    assert "upper" in stdout


def test_profile_update_split_saves_to_db(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    handle_profile_update_split(["--split", "ppl"], onboarding_session)
    profile = onboarding_session.query(UserProfile).first()
    assert profile.training_split == TrainingSplit.ppl


def test_profile_update_split_invalid_fails(onboarding_session, mock_science):
    handle_onboarding_start([], onboarding_session, mock_science)

    stdout, exit_code = handle_profile_update_split(["--split", "invalid_split"], onboarding_session)
    assert exit_code == 1


def test_profile_update_split_no_profile_fails(onboarding_session):
    stdout, exit_code = handle_profile_update_split(["--split", "ppl"], onboarding_session)
    assert exit_code == 1
```

---

### Architecture Compliance Constraints

**Обязательные паттерны для Story 3.5:**

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.core.onboarding import QUESTIONS, map_answer_to_coefficients  # ✅
from ..core.onboarding import QUESTIONS  # ❌ запрещено

# 2. Handler сигнатура — caller commits (НЕ handler):
session.flush()   # ✅ — в handler
session.commit()  # ❌ — только в caller (main.py)

# 3. exit_code semantics:
# exit_code=0: успех
# exit_code=1: user error (некорректный ввод, профиль не найден, дубликат)
# exit_code=2: system error — только в api/main.py

# 4. ScienceConfig как параметр (НЕ global):
def handle_onboarding_complete(argv, session, science):  # ✅
science = load_science_config()  # ❌ внутри handler — запрещено

# 5. TYPE_CHECKING для ScienceConfig в handlers.py (избегаем circular):
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig

# 6. SQLAlchemy Session — context manager в тестах:
with Session(engine) as session:  # ✅
```

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

**Python 3.14+:**
- `tuple[str, int]` — нативный тип, без `Tuple`
- `list[str] | None` — нативный Python 3.10+

**SQLAlchemy 2.0+:**
- `session.query(UserProfile).first()` — совместимо с SQLAlchemy 2.0
- `session.flush()` — без commit в handlers
- Тесты: `Base.metadata.create_all(engine)` — НЕ alembic

**Argparse:**
- `add_help=False` — все handlers используют этот паттерн (как в `handle_exercise_add`)
- Перехват `SystemExit` → возвращать `exit_code=1` с описанием
- `choices=` только для `--split` (ограниченный набор), НЕ для `--equipment` (валидируется через `map_answer_to_coefficients`)

**Source:** [Source: gym-coach-brain/pyproject.toml]
**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Starter Template Evaluation]

---

### File Structure Requirements

**Файлы, изменяемые в этой истории:**
```
gym-coach-brain/
├── src/gym_coach_brain/api/
│   └── handlers.py          ← ИЗМЕНИТЬ: добавить 6 новых handler функций + imports
└── tests/test_api/
    └── test_handlers.py     ← ИЗМЕНИТЬ: добавить ~20 новых тестов (fixture + test functions)
```

**Файлы, которые Story 3.5 НЕ создаёт:**
- `src/gym_coach_brain/api/main.py` — роутер (не в этой истории)
- `src/gym_coach_brain/api/contract.py` — JSON builder (не в этой истории)
- `src/gym_coach_brain/core/apre.py` — Epic 4

**Рабочая директория:** `gym-coach-brain/` (внутри проекта OpenGym)

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory Structure]

---

### Testing Requirements

**Паттерн тестов:**
- Каждый тест файл определяет fixtures локально (НЕ полагается только на conftest.py)
- `onboarding_session` — fixture с `seed_all()` для полного набора seed данных
- `mock_science` — локальная fixture с `initial_weight_table` для тестов `onboarding_complete`
- Все тесты используют `sqlite:///:memory:` — никаких файловых БД
- `handler_session` из Story 2.4 (существующий файл) остаётся без изменений

**Запуск:**
```bash
cd gym-coach-brain
uv run pytest tests/test_api/test_handlers.py -v   # только api тесты
uv run pytest -v                                    # все тесты
```

**Примечание по conftest.py:** Story 3.3 создаёт `tests/conftest.py` с `db_session` и `mock_science_config`. Story 3.5 НЕ зависит от этих fixtures напрямую — тесты определяют свои локальные fixtures. Это соответствует паттерну существующего `test_handlers.py`.

**Source:** [Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns (Test Fixtures)]

---

### Previous Story Intelligence (Story 3.4)

**Ключевые выводы из Story 3.4:**
1. `QUESTIONS` содержит 9 вопросов в порядке: `age`, `experience_level`, `goal`, `bodyweight_kg`, `equipment`, `training_days_per_week`, `training_split`, `sleep_quality`, `stress_level`
2. `map_answer_to_coefficients("equipment", ...)` принимает comma-separated строку ИЛИ JSON list
3. `compute_initial_weights` использует `getattr(user_profile, "_experience_level", "beginner")` — нужно устанавливать до вызова
4. `UserProfile.available_equipment` — JSON TEXT (`json.dumps([...])`)
5. `UserProfile.training_split` — `SAEnum(TrainingSplit)` — принимает `TrainingSplit.full_body`, не строку
6. `get_available_exercises` возвращает пустой список при пустом `available_equipment`
7. `handlers.py` уже содержит `handle_exercise_add` — ТОЛЬКО ДОБАВЛЯТЬ новые функции

**Source:** [Source: _bmad-output/implementation-artifacts/3-4-onboarding-template.md]

---

### Git Intelligence

```
Последние коммиты:
11b8cbb Reposition README with product narrative
425df73 Add GitHub stars and forks badges
d005f82 Rewrite README in English
```

**Выводы:**
- Последние коммиты касаются README — не gymcoach логики
- Story 3.3 и 3.4 ещё выполняются — убедиться что они завершены перед началом 3.5
- Dev agent НЕ делает git commit (только если явно попросят)
- `api/handlers.py` стабилен — безопасно добавлять функции

---

### Project Structure Notes

**После Story 3.5 `api/handlers.py` будет содержать:**
```python
handle_exercise_add(argv, session)                    ← из Story 2.4
handle_onboarding_start(argv, session, science)       ← Story 3.5
handle_onboarding_answer(argv, session, science)      ← Story 3.5
handle_onboarding_complete(argv, session, science)    ← Story 3.5
handle_profile_show(argv, session)                    ← Story 3.5
handle_profile_update_equipment(argv, session)        ← Story 3.5
handle_profile_update_split(argv, session)            ← Story 3.5
```

**После Story 3.5 `test_api/test_handlers.py` будет содержать:**
- 7 тестов для `handle_exercise_add` (существующих)
- ~20 новых тестов для 6 новых handlers

**Следующие шаги после Story 3.5:**
- Epic 4 — детерминированное тренировочное ядро (`core/apre.py`, `core/progression.py`)
- `api/main.py` — роутер интентов (когда все handlers готовы)

---

### References

- Story 3.5 требования: [Source: _bmad-output/planning-artifacts/epics/epic-3.md#Story 3.5]
- Architecture enforcement: [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
- Architecture handlers pattern: [Source: _bmad-output/planning-artifacts/architecture.md#Format Patterns]
- UserProfile model: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py]
- Onboarding functions: [Source: gym-coach-brain/src/gym_coach_brain/core/onboarding.py] (Story 3.4)
- Previous story: [Source: _bmad-output/implementation-artifacts/3-4-onboarding-template.md]
- Existing handlers: [Source: gym-coach-brain/src/gym_coach_brain/api/handlers.py]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `uv run pytest tests/test_api/test_handlers.py -v` → 22 passed
- `uv run pytest -v` → 144 passed, 1 warning (existing deprecation in `data/features.py`)
- `uv run pytest tests/test_api/test_handlers.py -v` (follow-ups) → 22 passed
- `uv run pytest -v` (full regression) → 144 passed, 1 warning (existing deprecation in `data/features.py`)

### Completion Notes List

- Реализованы 6 новых API handler-функций в `api/handlers.py`: `handle_onboarding_start`, `handle_onboarding_answer`, `handle_onboarding_complete`, `handle_profile_show`, `handle_profile_update_equipment`, `handle_profile_update_split`.
- Добавлены вспомогательные функции `_format_question` и `_get_or_none` для единообразного вывода вопросов и поиска профиля.
- Реализована полная обработка ошибок пользовательского ввода с `exit_code=1` и сохранением контракта handler-слоя (`session.flush()` без `commit`).
- Расширены тесты `tests/test_api/test_handlers.py` для покрытия всех новых интентов и ключевых error-path сценариев.
- Выполнена финальная регрессионная проверка всего репозитория (`144 passed`).
- ✅ Resolved review finding [HIGH]: `handle_onboarding_complete` теперь возвращает summary профиля и блок "Стартовые веса по паттернам".
- ✅ Resolved review finding [HIGH]: `handle_profile_update_equipment` теперь возвращает список доступных упражнений (с ограничением preview + overflow).
- ✅ Resolved review finding [MEDIUM]: выводы handler-ов синхронизированы с шаблоном из Dev Notes (расширенные summary-блоки).
- ✅ Resolved review finding [LOW]: удалено transient-поле `profile._experience_level`; используется persist-поле `experience_level` из `UserProfile`.
- ✅ Resolved review finding [LOW]: улучшена согласованность форматирования UX-ответов (`profile_show` включает статус онбординга).

### File List

- `gym-coach-brain/src/gym_coach_brain/api/handlers.py` (modified)
- `gym-coach-brain/tests/test_api/test_handlers.py` (modified)
- `_bmad-output/implementation-artifacts/3-5-onboarding-api-handlers.md` (modified)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified)

## Change Log

- 2026-03-08: Story 3.5 implemented. Added onboarding/profile handlers, expanded API handler tests, and completed full test-suite validation.
- 2026-03-08: Addressed AI review follow-ups (6/6). Updated onboarding/profile output summaries, removed transient experience attribute usage, and re-ran API + full regression tests.
