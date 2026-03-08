# Story 4.2: PUOS валидатор и фракционный объём

Status: done

## Story

As a dev agent,
I want to implement PUOS limit validation and fractional volume tracking in `core/puos.py`,
So that the system blocks unsafe training volumes and tracks muscle group load accurately.

## Acceptance Criteria

**Given** `ScienceConfig` с `puos.max_sets_per_group` и `puos.smh_volume_multiplier` доступен
**When** `validate_puos(muscle_group, planned_sets, science)` вызывается с превышением лимита
**Then** бросается `ScienceLimitError` с описанием нарушения

**When** объём в пределах лимита
**Then** возвращается `FractionalVolume` объект с коэффициентами 1.0 (агонист) / 0.5 (синергист)

**And** если `muscle_group.stretch_mediated = True` — эффективный лимит умножается на `science.puos.smh_volume_multiplier` (например, 1.2): SMH-упражнения (Romanian deadlift, overhead press) переносятся лучше и допускают больший объём согласно Israetel

**And** `accumulate_session_volume(session_sets: list[WorkoutSet], science) -> dict[muscle_group_id, float]` реализует within-session аккумуляцию: для каждого сета суммируется fractional volume (1.0 агонист + 0.5 синергист) по всем задействованным мышцам — если атлет делает жим штангой + жим гантелями + разводку в одной сессии, грудь получает суммарный объём всех трёх; `validate_puos` вызывается на итоговом аккумулированном объёме, не на объёме одного упражнения

**And** при накопленном объёме ≥9 сетов для любой мышечной группы логируется `WARNING` через loguru

**And** `pytest tests/test_core/test_puos.py` проходит:
- блокировка превышения лимита
- корректный фракционный расчёт 1.0/0.5
- SMH multiplier: stretch_mediated мышца допускает `max_sets * smh_volume_multiplier` сетов
- within-session accumulation: жим штангой + жим гантелями = суммарный объём для груди, не независимые проверки

## Tasks / Subtasks

- [x] **Создать dataclass `FractionalVolume` в `core/puos.py`** (AC: возвращаемый тип)
  - [x] `@dataclass FractionalVolume(muscle_group_id, accumulated_sets, effective_limit, agonist_coeff, synergist_coeff)`
  - [x] `agonist_coeff: float = 1.0`, `synergist_coeff: float = 0.5` как константы датакласса

- [x] **Реализовать `validate_puos(muscle_group, planned_sets, science)` в `core/puos.py`** (AC: PUOS validation)
  - [x] Рассчитать `effective_limit = science.puos.max_sets_per_group * (science.puos.smh_volume_multiplier if muscle_group.stretch_mediated else 1.0)`
  - [x] При `planned_sets > effective_limit` → поднять `ScienceLimitError` с сообщением: `f"PUOS limit exceeded for {muscle_group.name}: {planned_sets} sets > {effective_limit} limit"`
  - [x] При `planned_sets <= effective_limit` → вернуть `FractionalVolume(muscle_group_id=muscle_group.id, accumulated_sets=planned_sets, effective_limit=effective_limit)`
  - [x] Логировать `WARNING` через loguru если `planned_sets >= 9`
  - [x] Функция — чистая (pure) кроме loguru side effect

- [x] **Реализовать `accumulate_session_volume(session_sets, science) -> dict[int, float]`** (AC: within-session accumulation)
  - [x] Сигнатура: `accumulate_session_volume(session_sets: list[WorkoutSet], science: ScienceConfig) -> dict[int, float]`
  - [x] Для каждого `WorkoutSet` в `session_sets`: добавить 1.0 к `exercise.primary_muscle_id` и 0.5 к каждому ID в `exercise.secondary_muscle_id_list`
  - [x] Требует доступа к `Exercise` объекту через relationship — `workout_set.exercise` должен быть загружен (eager/joined load)
  - [x] Возвращает `dict[muscle_group_id: int, accumulated_volume: float]`
  - [x] ⚠️ ВАЖНО: эта функция делает DB-вызовы через relationship — не pure function (в отличие от `validate_puos`)

- [x] **Добавить loguru как зависимость** (AC: logging)
  - [x] Проверить наличие `loguru` в `pyproject.toml`
  - [x] `from loguru import logger` в `core/puos.py`

- [x] **Создать тесты `tests/test_core/test_puos.py`** (AC: тесты)
  - [x] Тест: `validate_puos` поднимает `ScienceLimitError` при превышении лимита
  - [x] Тест: `validate_puos` возвращает `FractionalVolume` при соблюдении лимита
  - [x] Тест: коэффициенты `agonist_coeff=1.0`, `synergist_coeff=0.5` в `FractionalVolume`
  - [x] Тест: SMH multiplier — stretch_mediated мышца допускает `max_sets * 1.2` сетов
  - [x] Тест: non-stretch_mediated мышца — точный лимит без multiplier
  - [x] Тест: `accumulate_session_volume` — два упражнения на грудь суммируются (не независимые проверки)
  - [x] Тест: синергистные мышцы получают 0.5 за каждый сет
  - [x] Тест: WARNING логируется при ≥9 сетах (использовать `caplog` или мок loguru)
  - [x] `uv run pytest tests/test_core/test_puos.py -v` — все PASS
  - [x] `uv run pytest -v` — полная регрессия PASS

### Review Follow-ups (AI)

- [x] [AI-Review][Medium] Синхронизировать `File List` с реальными изменениями в Git (добавить `science.py`, `models.py`, `seed.py`) [_bmad-output/implementation-artifacts/4-2-puos-validator.md]
- [x] [AI-Review][Medium] Добавить неотслеживаемые файлы `core/puos.py` и `test_puos.py` в индекс Git (`git add`) [gym-coach-brain/src/gym_coach_brain/core/puos.py]
- [x] [AI-Review][Medium] Уточнить статус `puos.py` в `File List`: помечен как `modified`, но в Git отображается как `untracked/new` [_bmad-output/implementation-artifacts/4-2-puos-validator.md]
- [x] [AI-Review][Low] Рассмотреть возможность удаления неиспользуемого параметра `science` в `accumulate_session_volume` или реализовать его использование [gym-coach-brain/src/gym_coach_brain/core/puos.py:165]

## Dev Notes

### ⚠️ Критические Prerequisites

**Перед началом убедиться что Story 4.1 завершена или пропустить зависимые паттерны:**
```bash
cd gym-coach-brain
uv run pytest -v   # Ожидается: 144+ passed (baseline после Story 3.5)
```

Story 4.2 НЕ зависит от файлов Story 4.1 (`apre.py`, `progression.py`, `weight_utils.py`).
Зависит только от: `core/science.py`, `data/models.py`, `exceptions.py` — все уже существуют.

---

### Текущее состояние `core/puos.py` (СУЩЕСТВУЕТ — расширить, не переписать)

```python
# gym-coach-brain/src/gym_coach_brain/core/puos.py (текущее содержимое)
"""
PUOS (Per-Unit-Of-Set) volume calculation utilities.

fractional_volume: calculates muscle group volume contribution per exercise set.
- Primary muscle: 1.0 (full set counts toward this group)
- Synergist muscle: 0.5 (half set toward this group)
- Non-involved muscle: 0.0
"""
import json
from sqlalchemy.orm import Session
from gym_coach_brain.data.models import Exercise

def fractional_volume(exercise_id: int, muscle_group_id: int, session: Session) -> float:
    """Return fractional volume contribution of an exercise for a muscle group."""
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        return 0.0
    if exercise.primary_muscle_id == muscle_group_id:
        return 1.0
    secondary_ids = json.loads(exercise.secondary_muscle_ids or "[]")
    if muscle_group_id in secondary_ids:
        return 0.5
    return 0.0
```

**Что добавляется в Story 4.2:**
- `FractionalVolume` dataclass
- `validate_puos(muscle_group, planned_sets, science) -> FractionalVolume` — pure (кроме loguru)
- `accumulate_session_volume(session_sets, science) -> dict[int, float]` — DB-доступ через relationship

**Существующую `fractional_volume()` НЕ ТРОГАТЬ** — она используется в других частях системы.

---

### Полная реализация `core/puos.py` (расширенная версия)

```python
"""
PUOS (Per-Unit-Of-Set) volume calculation and validation.

Implements:
- fractional_volume: DB-backed per-exercise contribution (СУЩЕСТВУЮЩАЯ функция)
- FractionalVolume: dataclass для результатов validate_puos
- validate_puos: pure function — PUOS limit enforcement
- accumulate_session_volume: within-session volume aggregation

References:
    Israetel, M. et al. (2019). Scientific Principles of Hypertrophy Training.
    Schoenfeld, B.J. & Grgic, J. (2021). Sports, 9(2), 32. PMC7927075.
"""
import json
from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy.orm import Session

from gym_coach_brain.core.science import ScienceConfig
from gym_coach_brain.data.models import Exercise, MuscleGroup, WorkoutSet
from gym_coach_brain.exceptions import ScienceLimitError

# ─── Constants ────────────────────────────────────────────────────────────────

AGONIST_COEFF: float = 1.0    # Primary muscle: full set contribution
SYNERGIST_COEFF: float = 0.5  # Secondary muscle: half set contribution
PUOS_WARNING_THRESHOLD: int = 9  # Sets: log WARNING if ≥ this value


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class FractionalVolume:
    """Result of a successful PUOS validation for a muscle group.

    Attributes:
        muscle_group_id: PK of the validated MuscleGroup
        accumulated_sets: Planned or accumulated sets for this session
        effective_limit: Actual limit after SMH multiplier (if applicable)
        agonist_coeff: Fractional contribution as primary muscle (always 1.0)
        synergist_coeff: Fractional contribution as synergist (always 0.5)
    """
    muscle_group_id: int
    accumulated_sets: float
    effective_limit: float
    agonist_coeff: float = field(default=AGONIST_COEFF)
    synergist_coeff: float = field(default=SYNERGIST_COEFF)


# ─── Existing function (DO NOT MODIFY) ────────────────────────────────────────

def fractional_volume(exercise_id: int, muscle_group_id: int, session: Session) -> float:
    """Return fractional volume contribution of an exercise for a muscle group.

    Args:
        exercise_id: PK of the Exercise record
        muscle_group_id: PK of the MuscleGroup to check
        session: Active SQLAlchemy session

    Returns:
        1.0 if muscle_group_id is the primary muscle of the exercise
        0.5 if muscle_group_id is a synergist (in secondary_muscle_ids)
        0.0 if muscle_group_id has no meaningful contribution
    """
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        return 0.0
    if exercise.primary_muscle_id == muscle_group_id:
        return 1.0
    secondary_ids = json.loads(exercise.secondary_muscle_ids or "[]")
    if muscle_group_id in secondary_ids:
        return 0.5
    return 0.0


# ─── New functions for Story 4.2 ──────────────────────────────────────────────

def validate_puos(
    muscle_group: MuscleGroup,
    planned_sets: float,
    science: ScienceConfig,
) -> FractionalVolume:
    """Validate planned sets against PUOS limit for a muscle group.

    Pure function (only side effect: loguru WARNING at ≥9 sets).
    Raises ScienceLimitError if planned_sets exceeds effective limit.

    ⚠️ USAGE SCOPE: Call on TOTAL accumulated session volume for a muscle group,
    NOT on per-exercise volume. Use accumulate_session_volume() first to aggregate
    all exercises in the session, then call validate_puos on the result.

    SMH (Stretch-Mediated Hypertrophy) multiplier: exercises that load muscles
    in a stretched position (Romanian deadlift, overhead press, incline curl)
    are better tolerated and allow higher volume per session. If
    muscle_group.stretch_mediated=True, the effective limit is multiplied by
    science.puos.smh_volume_multiplier (e.g., 1.2 → 13.2 sets for 11-set base).

    Args:
        muscle_group: MuscleGroup ORM object with id, name, stretch_mediated fields
        planned_sets: Accumulated sets planned for this muscle group in the session
        science: ScienceConfig with puos.max_sets_per_group and puos.smh_volume_multiplier

    Returns:
        FractionalVolume with accumulated_sets, effective_limit, and coefficients

    Raises:
        ScienceLimitError: If planned_sets > effective_limit

    References:
        [Source: gym-coach-brain/ScienceEvidence.md#PUOS Limits]
        [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
    """
    smh_mult = science.puos.smh_volume_multiplier if muscle_group.stretch_mediated else 1.0
    effective_limit = science.puos.max_sets_per_group * smh_mult

    # Log WARNING when approaching limit (science-informed threshold)
    if planned_sets >= PUOS_WARNING_THRESHOLD:
        logger.warning(
            "PUOS limit approached: {sets}/{limit} sets for {muscle}",
            sets=planned_sets,
            limit=effective_limit,
            muscle=muscle_group.name,
        )

    if planned_sets > effective_limit:
        raise ScienceLimitError(
            f"PUOS limit exceeded for {muscle_group.name}: "
            f"{planned_sets} sets > {effective_limit:.1f} limit"
            + (" (SMH multiplier applied)" if muscle_group.stretch_mediated else "")
        )

    return FractionalVolume(
        muscle_group_id=muscle_group.id,
        accumulated_sets=planned_sets,
        effective_limit=effective_limit,
    )


def accumulate_session_volume(
    session_sets: list[WorkoutSet],
    science: ScienceConfig,
) -> dict[int, float]:
    """Aggregate fractional volume per muscle group across all sets in a session.

    Implements within-session volume tracking using fractional contribution:
    - Primary muscle (agonist): +1.0 per set
    - Secondary muscles (synergists): +0.5 per set each

    Example: bench press (chest primary, triceps/front delt secondary) + dumbbell
    press + cable fly in one session → chest accumulates volume from ALL THREE,
    not independent per-exercise checks. Call validate_puos on the aggregated
    result to enforce PUOS limits.

    ⚠️ REQUIRES: WorkoutSet.exercise relationship must be loaded (eager/joined).
    Use SQLAlchemy selectinload or joinedload when querying WorkoutSets.

    Args:
        session_sets: List of WorkoutSet ORM objects with exercise relationship loaded
        science: ScienceConfig (reserved for future use, e.g., per-exercise overrides)

    Returns:
        dict mapping muscle_group_id (int) → accumulated_volume (float)
        Empty dict if session_sets is empty.

    References:
        [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.2]
        [Source: _bmad-output/planning-artifacts/architecture.md#FR12 fractional volume]
    """
    volume: dict[int, float] = {}

    for workout_set in session_sets:
        exercise = workout_set.exercise
        if exercise is None:
            continue

        # Primary muscle: full contribution
        primary_id = exercise.primary_muscle_id
        volume[primary_id] = volume.get(primary_id, 0.0) + AGONIST_COEFF

        # Secondary muscles: half contribution each
        for secondary_id in exercise.secondary_muscle_id_list:
            volume[secondary_id] = volume.get(secondary_id, 0.0) + SYNERGIST_COEFF

    return volume
```

---

### Тесты — `tests/test_core/test_puos.py`

```python
"""Tests for core/puos.py — PUOS validator and fractional volume accumulation."""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from gym_coach_brain.core.puos import (
    FractionalVolume,
    AGONIST_COEFF,
    SYNERGIST_COEFF,
    PUOS_WARNING_THRESHOLD,
    accumulate_session_volume,
    fractional_volume,
    validate_puos,
)
from gym_coach_brain.data.models import Exercise, MuscleGroup, WorkoutSet
from gym_coach_brain.exceptions import ScienceLimitError


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_muscle_group(
    muscle_id: int,
    name: str = "chest",
    stretch_mediated: bool = False,
) -> MuscleGroup:
    """Create a MuscleGroup without DB — for pure function tests."""
    mg = MuscleGroup.__new__(MuscleGroup)
    mg.id = muscle_id
    mg.name = name
    mg.stretch_mediated = stretch_mediated
    return mg


def make_exercise(
    exercise_id: int,
    primary_muscle_id: int,
    secondary_ids: list[int] = None,
) -> Exercise:
    """Create an Exercise without DB — loads secondary_muscle_ids from list."""
    import json
    ex = Exercise.__new__(Exercise)
    ex.id = exercise_id
    ex.primary_muscle_id = primary_muscle_id
    ex.secondary_muscle_ids = json.dumps(secondary_ids or [])
    return ex


def make_workout_set(exercise: Exercise) -> WorkoutSet:
    """Create a WorkoutSet with pre-loaded exercise relationship."""
    ws = WorkoutSet.__new__(WorkoutSet)
    ws.exercise = exercise
    return ws


# ─── validate_puos: basic cases ───────────────────────────────────────────────

def test_validate_puos_within_limit_returns_fractional_volume(mock_science_config):
    """Under limit: returns FractionalVolume with correct values."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    result = validate_puos(muscle, 8.0, mock_science_config)
    assert isinstance(result, FractionalVolume)
    assert result.muscle_group_id == 1
    assert result.accumulated_sets == pytest.approx(8.0)
    assert result.effective_limit == pytest.approx(11.0)  # no SMH multiplier


def test_validate_puos_exceeds_limit_raises_science_limit_error(mock_science_config):
    """Over limit: raises ScienceLimitError."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    with pytest.raises(ScienceLimitError, match="PUOS limit exceeded"):
        validate_puos(muscle, 12.0, mock_science_config)  # 12 > 11


def test_validate_puos_exact_limit_is_allowed(mock_science_config):
    """Exactly at limit: no error raised."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    result = validate_puos(muscle, 11.0, mock_science_config)
    assert result.accumulated_sets == pytest.approx(11.0)


# ─── validate_puos: FractionalVolume coefficients ─────────────────────────────

def test_fractional_volume_agonist_coeff_is_1_0(mock_science_config):
    """FractionalVolume always has agonist_coeff=1.0."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    result = validate_puos(muscle, 5.0, mock_science_config)
    assert result.agonist_coeff == pytest.approx(AGONIST_COEFF)
    assert result.agonist_coeff == pytest.approx(1.0)


def test_fractional_volume_synergist_coeff_is_0_5(mock_science_config):
    """FractionalVolume always has synergist_coeff=0.5."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    result = validate_puos(muscle, 5.0, mock_science_config)
    assert result.synergist_coeff == pytest.approx(SYNERGIST_COEFF)
    assert result.synergist_coeff == pytest.approx(0.5)


# ─── validate_puos: SMH multiplier ────────────────────────────────────────────

def test_validate_puos_smh_multiplier_expands_limit(mock_science_config):
    """stretch_mediated=True: effective limit = max_sets * smh_volume_multiplier."""
    # mock_science_config: max_sets_per_group=11, smh_volume_multiplier=1.2
    # effective_limit = 11 * 1.2 = 13.2
    muscle = make_muscle_group(2, "hamstrings", stretch_mediated=True)
    result = validate_puos(muscle, 13.0, mock_science_config)  # 13 <= 13.2
    assert result.effective_limit == pytest.approx(11 * 1.2)


def test_validate_puos_smh_allows_volume_above_base_limit(mock_science_config):
    """SMH muscle can have >11 sets without error."""
    muscle = make_muscle_group(2, "hamstrings", stretch_mediated=True)
    # 12 sets: would fail without SMH (12 > 11), but passes with multiplier (12 <= 13.2)
    result = validate_puos(muscle, 12.0, mock_science_config)
    assert result.accumulated_sets == pytest.approx(12.0)


def test_validate_puos_smh_still_blocks_over_multiplied_limit(mock_science_config):
    """SMH muscle: still blocked if exceeds multiplied limit (>13.2)."""
    muscle = make_muscle_group(2, "hamstrings", stretch_mediated=True)
    with pytest.raises(ScienceLimitError):
        validate_puos(muscle, 14.0, mock_science_config)  # 14 > 13.2


def test_validate_puos_non_smh_uses_base_limit_only(mock_science_config):
    """Non-SMH muscle: multiplier = 1.0, uses base max_sets_per_group."""
    muscle = make_muscle_group(1, "chest", stretch_mediated=False)
    result = validate_puos(muscle, 11.0, mock_science_config)
    assert result.effective_limit == pytest.approx(11.0)  # 11 * 1.0


# ─── validate_puos: WARNING logging ───────────────────────────────────────────

def test_validate_puos_logs_warning_at_threshold(mock_science_config):
    """≥9 sets: WARNING is logged via loguru."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    with patch("gym_coach_brain.core.puos.logger") as mock_logger:
        validate_puos(muscle, 9.0, mock_science_config)
        mock_logger.warning.assert_called_once()


def test_validate_puos_no_warning_below_threshold(mock_science_config):
    """<9 sets: no WARNING logged."""
    muscle = make_muscle_group(1, stretch_mediated=False)
    with patch("gym_coach_brain.core.puos.logger") as mock_logger:
        validate_puos(muscle, 8.0, mock_science_config)
        mock_logger.warning.assert_not_called()


# ─── accumulate_session_volume ─────────────────────────────────────────────────

def test_accumulate_session_volume_single_primary(mock_science_config):
    """One set of bench press: chest gets 1.0."""
    chest_id, tricep_id = 1, 2
    bench = make_exercise(1, primary_muscle_id=chest_id, secondary_ids=[tricep_id])
    ws = make_workout_set(bench)

    result = accumulate_session_volume([ws], mock_science_config)
    assert result[chest_id] == pytest.approx(1.0)
    assert result[tricep_id] == pytest.approx(0.5)


def test_accumulate_session_volume_two_exercises_same_primary(mock_science_config):
    """Two chest exercises: volumes are summed, not independent."""
    chest_id = 1
    bench = make_exercise(1, primary_muscle_id=chest_id)
    dbell_press = make_exercise(2, primary_muscle_id=chest_id)
    sets = [make_workout_set(bench), make_workout_set(dbell_press)]

    result = accumulate_session_volume(sets, mock_science_config)
    assert result[chest_id] == pytest.approx(2.0)  # 1.0 + 1.0 (not independent checks)


def test_accumulate_session_volume_three_chest_exercises(mock_science_config):
    """Bench + dumbbell press + cable fly → chest gets 3.0."""
    chest_id = 1
    bench = make_exercise(1, primary_muscle_id=chest_id)
    dbell = make_exercise(2, primary_muscle_id=chest_id)
    fly = make_exercise(3, primary_muscle_id=chest_id)
    sets = [make_workout_set(bench), make_workout_set(dbell), make_workout_set(fly)]

    result = accumulate_session_volume(sets, mock_science_config)
    assert result[chest_id] == pytest.approx(3.0)


def test_accumulate_session_volume_synergist_half_contribution(mock_science_config):
    """Synergist muscle gets 0.5 per set."""
    chest_id, tricep_id = 1, 2
    bench = make_exercise(1, primary_muscle_id=chest_id, secondary_ids=[tricep_id])
    # 2 sets of bench press
    sets = [make_workout_set(bench), make_workout_set(bench)]

    result = accumulate_session_volume(sets, mock_science_config)
    assert result[chest_id] == pytest.approx(2.0)    # 2 × 1.0
    assert result[tricep_id] == pytest.approx(1.0)   # 2 × 0.5


def test_accumulate_session_volume_empty_returns_empty_dict(mock_science_config):
    """Empty session → empty dict."""
    result = accumulate_session_volume([], mock_science_config)
    assert result == {}


def test_accumulate_session_volume_multiple_secondaries(mock_science_config):
    """Exercise with multiple synergists: each gets 0.5."""
    chest_id, tricep_id, front_delt_id = 1, 2, 3
    bench = make_exercise(
        1, primary_muscle_id=chest_id, secondary_ids=[tricep_id, front_delt_id]
    )
    result = accumulate_session_volume([make_workout_set(bench)], mock_science_config)
    assert result[chest_id] == pytest.approx(1.0)
    assert result[tricep_id] == pytest.approx(0.5)
    assert result[front_delt_id] == pytest.approx(0.5)


# ─── Integration: accumulate + validate ───────────────────────────────────────

def test_puos_validate_on_accumulated_volume(mock_science_config):
    """Accumulated volume of 12 sets for chest → ScienceLimitError."""
    chest_id = 1
    chest_ex = make_exercise(1, primary_muscle_id=chest_id)
    # 12 sets total (each WorkoutSet = 1 set)
    sets = [make_workout_set(chest_ex) for _ in range(12)]

    volume = accumulate_session_volume(sets, mock_science_config)
    muscle = make_muscle_group(chest_id, "chest", stretch_mediated=False)

    with pytest.raises(ScienceLimitError):
        validate_puos(muscle, volume[chest_id], mock_science_config)


def test_puos_validate_within_limit_on_accumulated_volume(mock_science_config):
    """Accumulated volume of 11 sets for chest → no error."""
    chest_id = 1
    chest_ex = make_exercise(1, primary_muscle_id=chest_id)
    sets = [make_workout_set(chest_ex) for _ in range(11)]

    volume = accumulate_session_volume(sets, mock_science_config)
    muscle = make_muscle_group(chest_id, "chest", stretch_mediated=False)

    result = validate_puos(muscle, volume[chest_id], mock_science_config)
    assert result.accumulated_sets == pytest.approx(11.0)


# ─── Legacy: fractional_volume (DB-backed) ─────────────────────────────────────

def test_fractional_volume_primary_muscle(db_session):
    """Primary muscle returns 1.0."""
    from gym_coach_brain.data.models import MuscleGroup as MG, MovementPattern, Exercise as Ex
    import json

    # Seed minimal data
    mp = MovementPattern(name="push_horizontal", category="push")
    db_session.add(mp)
    db_session.flush()

    mg = MG(name="chest_test", body_region="upper", is_push=True, is_pull=False)
    db_session.add(mg)
    db_session.flush()

    ex = Ex(
        name="bench_press_test",
        primary_muscle_id=mg.id,
        movement_pattern_id=mp.id,
        equipment_type="barbell",
        secondary_muscle_ids="[]",
    )
    db_session.add(ex)
    db_session.flush()

    result = fractional_volume(ex.id, mg.id, db_session)
    assert result == pytest.approx(1.0)


def test_fractional_volume_nonexistent_exercise_returns_zero(db_session):
    """Non-existent exercise_id → 0.0."""
    result = fractional_volume(99999, 1, db_session)
    assert result == pytest.approx(0.0)
```

---

### Architecture Compliance Constraints

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.core.science import ScienceConfig          # ✅
from gym_coach_brain.data.models import MuscleGroup, WorkoutSet  # ✅
from gym_coach_brain.exceptions import ScienceLimitError         # ✅
from ..data.models import MuscleGroup                            # ❌ запрещено

# 2. ScienceConfig как параметр, НЕ global:
def validate_puos(muscle_group, planned_sets, science: ScienceConfig):  # ✅
SCIENCE = load_science_config()  # ❌ запрещено на module level

# 3. Typed exceptions из internal modules:
raise ScienceLimitError("...")  # ✅ — не raise Exception("error")

# 4. Logging через loguru:
from loguru import logger
logger.warning("PUOS limit approached: ...")  # ✅
print("PUOS limit approached")  # ❌ запрещено

# 5. Python 3.14+ нативный typing:
dict[int, float]      # ✅ нативный
list[WorkoutSet]      # ✅ нативный
Dict[int, float]      # ❌ из typing (устарел)
```

[Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

- **Python 3.14+** — нативные `dict[int, float]`, `list[WorkoutSet]`
- **Pydantic 2.0+** — уже в `science.py` (не меняется)
- **loguru 0.7.3** — `from loguru import logger`; проверить наличие в `pyproject.toml`
- **pytest + unittest.mock** — `patch("gym_coach_brain.core.puos.logger")` для тестирования WARNING
- **НЕ импортировать torch, alembic** в core/ модулях

```bash
# Проверить наличие loguru:
cd gym-coach-brain && grep loguru pyproject.toml
# Если отсутствует: uv add loguru
```

[Source: _bmad-output/planning-artifacts/architecture.md#Infrastructure & Observability]

---

### Testing Requirements

**Fixtures:** Использовать из `tests/conftest.py`:
- `mock_science_config` — содержит `PUOSConfig(max_sets_per_group=11, smh_volume_multiplier=1.2)`
- `db_session` — только для теста legacy `fractional_volume()` (DB-backed)
- `db_engine` — не нужен напрямую

**Стратегия тестирования `validate_puos` и `accumulate_session_volume`:**
- Создавать объекты через `__new__` без DB (pure function tests)
- `fractional_volume` требует `db_session` — тест отдельно

**Запуск:**
```bash
cd gym-coach-brain
uv run pytest tests/test_core/test_puos.py -v
uv run pytest -v   # полная регрессия
```

[Source: _bmad-output/planning-artifacts/architecture.md#Process Patterns (Test Fixtures)]

---

### Previous Story Intelligence (Story 4.1)

Story 4.1 была создана (статус: ready-for-dev), но может ещё не быть реализована.
**Файлы из Story 4.1, которые могут или не могут существовать к началу 4.2:**
- `core/apre.py` — НЕ нужен для Story 4.2
- `core/progression.py` — НЕ нужен для Story 4.2
- `core/weight_utils.py` — НЕ нужен для Story 4.2

**Если Story 4.1 реализована:** baseline тестов вырос выше 144. Запусти `uv run pytest -v` для подтверждения.

**Паттерны из Story 4.1, применимые к 4.2:**
1. Pure functions в `core/` — никаких DB-вызовов (кроме `accumulate_session_volume`, которая работает с relationship)
2. `ScienceConfig` всегда как параметр функции
3. Dataclass вместо dict для структурированных результатов
4. `conftest.py` mock не делает реальных I/O — используй `mock_science_config` везде

**Паттерн mock loguru (стандартный для Python):**
```python
from unittest.mock import patch

def test_warning_logged(mock_science_config):
    muscle = make_muscle_group(1)
    with patch("gym_coach_brain.core.puos.logger") as mock_logger:
        validate_puos(muscle, 9.0, mock_science_config)
        mock_logger.warning.assert_called_once()
```

---

### Git Intelligence

```
11b8cbb Reposition README with product narrative
425df73 Add GitHub stars and forks badges
d005f82 Rewrite README in English
```

**Выводы:**
- Последние коммиты — только README, кодовая база `core/puos.py` стабильна
- Story 4.2 расширяет `core/puos.py` — добавляет новые функции, не изменяет существующие
- Существующая `fractional_volume()` тестируется в других тестах — не сломать её
- Dev agent НЕ делает git commit (только если явно попросят)

---

### Project Structure Notes

**После Story 4.2 `src/gym_coach_brain/core/` будет содержать:**
```
core/
├── __init__.py
├── science.py          ← существующий (НЕ меняется)
├── puos.py             ← РАСШИРЯЕТСЯ (+ FractionalVolume, validate_puos, accumulate_session_volume)
├── onboarding.py       ← существующий (НЕ трогать)
├── apre.py             ← из Story 4.1 (если реализована)
├── progression.py      ← из Story 4.1 (если реализована)
└── weight_utils.py     ← из Story 4.1 (если реализована)
```

**Новые тестовые файлы:**
```
tests/test_core/
└── test_puos.py        ← СОЗДАТЬ (расширенный, заменяет placeholder если существует)
```

**Следующие истории после Story 4.2:**
- Story 4.3: Readiness log → `core/readiness.py` (новый файл, не зависит от puos.py)
- Story 4.4: Methodology selector → `core/methodology.py`
- Story 4.5: Adaptation Engine — вызывает `validate_puos` + `accumulate_session_volume`

**Важные зависимости по данным:**
- `accumulate_session_volume` требует `WorkoutSet.exercise` relationship быть загруженным
- При вызове из `adaptation/engine.py` в Story 4.5: использовать `selectinload(WorkoutSet.exercise)`

---

### References

- Story 4.2 требования: [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.2]
- Существующий `core/puos.py`: [Source: gym-coach-brain/src/gym_coach_brain/core/puos.py]
- Architecture enforcement: [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
- `MuscleGroup.stretch_mediated` field: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#MuscleGroup]
- `WorkoutSet` model: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#WorkoutSet]
- `ScienceConfig.puos`: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py#PUOSConfig]
- `ScienceLimitError`: [Source: gym-coach-brain/src/gym_coach_brain/exceptions.py]
- Conftest fixtures: [Source: gym-coach-brain/tests/conftest.py]
- Loguru logging patterns: [Source: _bmad-output/planning-artifacts/architecture.md#Communication Patterns]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Test failure: `MuscleGroup.__new__(MuscleGroup)` doesn't initialize SQLAlchemy ORM instrumentation state; fixed by switching to `types.SimpleNamespace` for all pure-function test helpers (`make_muscle_group`, `make_exercise`, `make_workout_set`). DB-backed tests (`test_fractional_volume_*`) still use real ORM objects via `db_session`.

### Completion Notes List

- Extended `core/puos.py` with `FractionalVolume` dataclass, `validate_puos()` pure function, and `accumulate_session_volume()`.
- Existing `fractional_volume()` function unchanged.
- `validate_puos` enforces PUOS limits, applies SMH multiplier for `stretch_mediated` muscles, logs WARNING via loguru at ≥9 sets.
- `accumulate_session_volume` aggregates session volume: primary +1.0, synergists +0.5 each, across all sets.
- `loguru` already present in `pyproject.toml` — no dependency change required.
- Created `tests/test_core/test_puos.py` with 21 tests covering all ACs.
- All 216 tests pass (21 new + 195 pre-existing), zero regressions.
- ✅ Resolved review finding [Medium]: File List synced — added science.py, models.py, seed.py with accurate change descriptions
- ✅ Resolved review finding [Medium]: puos.py status corrected from "modified" to "new" in File List
- ✅ Resolved review finding [Medium]: puos.py and test_puos.py staged in git index
- ✅ Resolved review finding [Low]: `science` parameter in `accumulate_session_volume` retained as reserved API — docstring documents forward-compatible intent; Story 4.5 (Adaptation Engine) will use it for per-exercise overrides

### Change Log

- 2026-03-08: Story 4.2 implemented — PUOS validator and fractional volume accumulation added to `core/puos.py`; 21 new tests in `tests/test_core/test_puos.py`
- 2026-03-08: Addressed code review findings — 4 items resolved (Date: 2026-03-08)

### File List

- `gym-coach-brain/src/gym_coach_brain/core/puos.py` (new — FractionalVolume dataclass, validate_puos, accumulate_session_volume; fractional_volume legacy kept)
- `gym-coach-brain/tests/test_core/test_puos.py` (new — 21 tests)
- `gym-coach-brain/src/gym_coach_brain/core/science.py` (modified — ConfigError import, EquipmentIncrementsConfig added)
- `gym-coach-brain/src/gym_coach_brain/data/models.py` (modified — UserProfile: age, goal, experience_level, sleep_quality_score, stress_score fields added)
- `gym-coach-brain/src/gym_coach_brain/data/seed.py` (modified — updated CLI entrypoint, added Exercise/Equipment imports and seeding)
