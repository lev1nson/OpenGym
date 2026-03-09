# Story 4.7: WorkoutPlanner — генерация плана тренировки

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an athlete,
I want the system to generate a complete workout plan for today's session,
so that I just follow the plan without any planning decisions.

## Acceptance Criteria

**Given** `UserProfile` с `training_split` и `training_days_per_week`, история `WorkoutSession`/`WorkoutSet` в БД, и `ScienceConfig` доступны
**When** `WorkoutPlanner.generate(user_profile, science, db_session, recovery_signal=None) -> WorkoutPlan` вызывается
**Then** метод определяет muscle groups на сегодня через поле `split_day_label` последней завершённой `WorkoutSession`:
- для `full_body`: все группы каждую сессию; `split_day_label = "full_body"`
- для `upper_lower`: читает `split_day_label` предыдущей сессии; если `upper` → сегодня `lower`, если `lower` → сегодня `upper`; записывает новый `split_day_label` в текущую сессию
- для `ppl`: читает `split_day_label` предыдущей сессии; строгий цикл `push → pull → legs`; записывает новый `split_day_label` в текущую сессию
- `custom`: те же muscle groups, что и в последней завершённой сессии (fallback); `split_day_label = "full_body"`

**And** при отсутствии истории (первая тренировка) применяются fallback-значения: PPL стартует с `push`, UL стартует с `upper`, FullBody/custom → `full_body`

**And** применяется `min_rest_days` из `ScienceConfig.planning`: если muscle group тренировалась менее `min_rest_days_per_muscle_group` назад — она исключается из сегодняшнего плана

**And** применение `min_rest_days` не может оставить план полностью пустым: если после исключения групп по `min_rest_days` не остаётся ни одной — ограничение снимается для всех групп и в `WorkoutPlan.warnings` добавляется `"⚠️ Нарушен рекомендуемый отдых — недостаточно времени с последней тренировки"`

**And** для каждой требуемой muscle group выбирается упражнение из библиотеки:
- фильтр по `UserProfile.available_equipment` (JSON list EquipmentType values)
- ротация: предпочитает упражнения, не использовавшиеся в последних 2-х сессиях для данной muscle group (rotation_score = дней с последнего использования)
- при равном rotation_score — случайный выбор с `random.seed(date)` (детерминировано для одного дня)

**And** если для muscle group из сплита нет ни одного упражнения по фильтру оборудования — группа пропускается без ошибки; добавляется в `WorkoutPlan.skipped_groups: list[str]` с причиной `"no_equipment"`; PUOS-валидация и план строятся на оставшихся группах

**And** перед генерацией проверяется разрыв с последней сессией: если `today - last_session_date > science.planning.detraining_threshold_days` (например, 14) — все `target_weight_kg` умножаются на `science.planning.detraining_coefficient` (например, 0.85) и в `WorkoutPlan.warnings` добавляется `"⚠️ Перерыв [N] дней — веса снижены для безопасного возврата"`

**And** проверяется счётчик мезоцикла: если количество `completed` сессий с момента последнего дилоада (или от начала) ≥ `science.planning.deload_trigger_sessions` (например, 16) — в `WorkoutPlan.warnings` добавляется `"💤 Рекомендуется дилоад-неделя — [N] недель непрерывной нагрузки"`; дилоад не форсируется

**And** каждому упражнению назначается:
- количество сетов и rep_range из текущей `Methodology` (через `select_methodology(user_profile, science)` из `core/methodology.py`)
- стартовый вес = последний использованный вес для этого упражнения (из `WorkoutSet`) или для новых упражнений: `user_profile.initial_weight_coefficients_dict.get(exercise.movement_pattern.name, 0.0)` (преcomputed в onboarding); если 0.0 — используем `user_profile.bodyweight_kg * science.initial_weight_table.get(user_profile.experience_level or "beginner", {}).get(movement_pattern.name, 0.0)`
- для `equipment_type=bodyweight` стартовый вес всегда `0.0`
- результат умножается на `recovery_signal.coefficient` (если `recovery_signal` передан; иначе коэффициент = 1.0)
- применяется detraining_coefficient если период > threshold
- итоговый `target_weight_kg` округляется через `core.weight_utils.round_to_equipment_increment(weight, exercise.equipment_type, science)`

**And** план проходит PUOS-валидацию (`validate_puos`) перед возвратом; при нарушении — автоматически сокращается число сетов самого объёмного упражнения (не бросает исключение наружу)

**And** для upper body сессий план проходит antagonist balance проверку: если есть хотя бы одна `is_push=True` мышца — должно быть хотя бы одно `is_pull=True` упражнение, и наоборот; при нарушении — в `WorkoutPlan.warnings` добавляется `"⚠️ Дисбаланс: только [push/pull] упражнения — рекомендуется добавить антагонист"`; план не блокируется

**And** `WorkoutPlan` — датакласс с полями: `muscle_groups_today: list[str]`, `split_day_label: str`, `exercises: list[PlannedExercise]`, `skipped_groups: list[str]` (default: empty), `warnings: list[str]` (default: empty)

**And** `PlannedExercise` — датакласс с полями: `exercise_id: int`, `exercise_name: str`, `sets: int`, `rep_range: tuple[int, int]`, `target_weight_kg: float`

**And** `WorkoutPlan.split_day_label` возвращается для записи в `WorkoutSession.split_day_label` и `WorkoutSession.planned_exercises` через `api/handlers.py` при `workout_start` (в Story 6.1)

**And** `ScienceEvidence.md` расширяется тремя полями в секции `planning:` и `core/science.py` расширяется `PlanningConfig` этими же полями

**And** `pytest tests/test_core/test_planner.py` проходит:
- корректное чередование upper/lower и ppl-цикл через `split_day_label`
- первая тренировка (пустая история): PPL → `push`, UL → `upper`, FullBody → `full_body`
- пропуск тренировки не сбивает цикл: следующий `split_day_label` всегда следующий по очереди
- recovery_signal.coefficient=0.6: `target_weight_kg` всех упражнений снижен на 40% относительно last_used_weight
- recovery_signal=None: `target_weight_kg` = last_used_weight без изменений
- нет оборудования для muscle group: группа в `skipped_groups`, план строится на остальных
- все группы заблокированы min_rest_days: ограничение снимается, `warnings` содержит предупреждение
- перерыв >14 дней: `target_weight_kg` снижен на `detraining_coefficient`, `warnings` содержит предупреждение
- перерыв <14 дней: вес не снижается
- счётчик ≥ `deload_trigger_sessions`: `warnings` содержит рекомендацию дилоада
- `target_weight_kg` для barbell упражнения округлён до кратного 2.5кг
- rotation_score: упражнения из последней сессии получают меньший приоритет
- min_rest_days enforcement: группа тренировавшаяся вчера исключается при достаточном количестве других групп
- PUOS auto-reduction срабатывает при превышении

## Tasks / Subtasks

### 1. Расширить `ScienceEvidence.md` (AC: detraining + deload поля)

- [x] В секцию `planning:` добавить три поля после существующих min_rest_days:
  ```yaml
  planning:
    min_rest_days_per_muscle_group: 2
    min_rest_days_compound: 3
    detraining_threshold_days: 14   # int — days of absence after which detraining penalty is applied
    detraining_coefficient: 0.85    # float — weight multiplier after detraining break (e.g. 0.85 = 15% reduction)
    deload_trigger_sessions: 16     # int — completed sessions before recommending a deload week
  ```
- [x] Проверить: `uv run python -c "from gym_coach_brain.core.science import load_science_config; c = load_science_config(); print(c.planning.detraining_threshold_days)"` → 14 ✅

### 2. Расширить `core/science.py` (AC: PlanningConfig с новыми полями)

- [x] В класс `PlanningConfig(BaseModel)` добавить три поля ПОСЛЕ существующих:
  ```python
  detraining_threshold_days: int = Field(default=14, ge=1)
  detraining_coefficient: float = Field(default=0.85, ge=0.0, le=1.0)
  deload_trigger_sessions: int = Field(default=16, ge=1)
  ```
- [x] Проверить: все существующие тесты `test_core/test_science.py` проходят (backward-compat через defaults) → 21/21 ✅

### 3. Обновить `tests/conftest.py` (AC: mock_science_config с planning расширениями)

- [x] Добавить новые поля в `PlanningConfig(...)` внутри `mock_science_config`:
  ```python
  planning=PlanningConfig(
      min_rest_days_per_muscle_group=2,
      min_rest_days_compound=3,
      detraining_threshold_days=14,
      detraining_coefficient=0.85,
      deload_trigger_sessions=16,
  ),
  ```
- [x] НЕ добавлять `MLConfig` / `SummaryConfig` / `plateau_detection_sessions` если Stories 4.5/4.6 ещё не завершены — только если они уже merged

### 4. Создать `core/planner.py`

- [x] **Датаклассы в начале файла:**
  ```python
  @dataclass
  class PlannedExercise:
      exercise_id: int
      exercise_name: str
      sets: int
      rep_range: tuple[int, int]
      target_weight_kg: float

  @dataclass
  class WorkoutPlan:
      muscle_groups_today: list[str]
      split_day_label: str
      exercises: list[PlannedExercise]
      skipped_groups: list[str] = field(default_factory=list)
      warnings: list[str] = field(default_factory=list)
  ```

- [x] **`class WorkoutPlanner`** с методом `generate()`:
  - [x] Signature: `def generate(self, user_profile, science, db_session, recovery_signal=None) -> WorkoutPlan`
  - [x] Шаг 1: Найти последнюю завершённую сессию (`status="completed"`)
  - [x] Шаг 2: Определить `today_label` и muscle groups через `_determine_split_day(user_profile, last_session, db_session)`:
    - full_body → label="full_body", groups=все MuscleGroup из БД
    - upper_lower → flip предыдущего label (upper↔lower); groups по `body_region`
    - ppl → cycle push→pull→legs; groups по `is_push`/`is_pull`/`body_region=lower`
    - custom → label="full_body", groups=те же что в последней сессии
    - fallback если нет истории: ppl→"push", upper_lower→"upper", full_body/custom→"full_body"
  - [x] Шаг 3: Применить `min_rest_days` фильтр через `_filter_by_rest_days(groups, today, db_session, science)`
    - если после фильтра 0 групп → снять фильтр + добавить warning
  - [x] Шаг 4: Для каждой muscle group выбрать упражнение через `_select_exercise(mg, user_profile, today, db_session)`
    - фильтр по `available_equipment` (JSON list)
    - rotation_score = дней с последнего использования в этой muscle group
    - `random.seed(today.isoformat())` для детерминизма
    - если нет упражнений → `skipped_groups.append(mg.name + ":no_equipment")`
  - [x] Шаг 5: Проверить detraining: `(today - last_session_date).days > science.planning.detraining_threshold_days`
  - [x] Шаг 6: Для каждого выбранного упражнения вычислить `target_weight_kg`:
    - Получить методологию: `select_methodology(user_profile, science)` из `core/methodology.py`
    - Найти последний `WorkoutSet` для `exercise_id` → `last_used_weight`
    - Если нет истории: `initial_weight_coefficients_dict.get(movement_pattern_name, 0.0)` или fallback через `science.initial_weight_table`
    - Для bodyweight: 0.0
    - Применить detraining_coefficient если нужно
    - Применить `recovery_signal.coefficient if recovery_signal else 1.0`
    - Округлить: `round_to_equipment_increment(raw_weight, exercise.equipment_type, science)`
  - [x] Шаг 7: PUOS-валидация:
    - Аккумулировать объём по плану: каждое упражнение × sets → fractional volume для первичной и вторичных мышц
    - `validate_puos()` для каждой мышечной группы
    - При `ScienceLimitError` → найти упражнение с наибольшим вкладом в эту группу → уменьшить sets на 1 → повторить
  - [x] Шаг 8: Deload check — подсчитать завершённые сессии (since last deload or ever) → warning если ≥ threshold
  - [x] Шаг 9: Antagonist balance для upper body — предупреждение если только push или только pull
  - [x] Шаг 10: Вернуть `WorkoutPlan`

- [x] **Вспомогательные методы** (приватные, префикс `_`):
  - [x] `_determine_split_day(user_profile, last_session, db_session) -> tuple[str, list[MuscleGroup]]`
  - [x] `_filter_by_rest_days(groups, today, db_session, science) -> list[MuscleGroup]`
  - [x] `_select_exercise(mg, user_profile, today_date, db_session) -> Exercise | None`
  - [x] `_get_last_used_weight(exercise_id, db_session) -> float | None`
  - [x] `_apply_puos_reduction(exercises, planned_sets_map, db_session, science) -> list[PlannedExercise]`
  - [x] `_count_completed_sessions(db_session) -> int`

### 5. Создать `tests/test_core/test_planner.py`

- [x] **Setup fixtures** (в файле или через conftest):
  ```python
  # helper to create minimal test data
  def create_test_muscle_group(db_session, name, body_region, is_push=False, is_pull=False, stretch_mediated=False)
  def create_test_movement_pattern(db_session, name, category)
  def create_test_exercise(db_session, name, muscle_group, movement_pattern, equipment_type="barbell")
  def create_test_user_profile(db_session, training_split="full_body")
  def create_completed_session(db_session, session_date, split_day_label=None, exercise=None, weight_kg=80.0, reps=8)
  ```

- [x] **Split-day logic tests:**
  - [x] `test_full_body_split_all_groups` — training_split=full_body → все muscle groups в плане
  - [x] `test_upper_lower_flip_upper_to_lower` — предыдущий split_day_label="upper" → сегодня "lower"
  - [x] `test_upper_lower_flip_lower_to_upper` — предыдущий split_day_label="lower" → сегодня "upper"
  - [x] `test_ppl_push_to_pull` — предыдущий "push" → сегодня "pull"
  - [x] `test_ppl_pull_to_legs` — предыдущий "pull" → сегодня "legs"
  - [x] `test_ppl_legs_to_push` — предыдущий "legs" → сегодня "push"
  - [x] `test_ppl_first_workout_starts_push` — нет истории, ppl → split_day_label="push"
  - [x] `test_upper_lower_first_workout_starts_upper` — нет истории, upper_lower → "upper"
  - [x] `test_full_body_first_workout` — нет истории, full_body → "full_body"

- [x] **Recovery signal tests:**
  - [x] `test_recovery_signal_scales_weight` — signal.coefficient=0.6 → target_weight = last_weight * 0.6 (before rounding)
  - [x] `test_no_recovery_signal_uses_full_weight` — signal=None → target_weight = last_weight

- [x] **Equipment filter tests:**
  - [x] `test_no_equipment_for_group_skips_it` — нет упражнений с matching equipment → группа в skipped_groups
  - [x] `test_skipped_groups_reason` — skipped_groups содержит имя группы

- [x] **Min rest days tests:**
  - [x] `test_min_rest_days_excludes_recent_group` — группа тренировалась вчера → исключена при достаточном числе других групп
  - [x] `test_all_groups_blocked_overrides_rest_days` — все группы в min_rest_days → ограничение снимается, warning добавлен
  - [x] `test_min_rest_days_warning_message` — warnings содержит "⚠️ Нарушен рекомендуемый отдых"

- [x] **Detraining tests:**
  - [x] `test_detraining_applies_after_long_break` — last session 20 дней назад → target_weight снижен на 15%
  - [x] `test_detraining_not_applied_short_break` — last session 5 дней назад → target_weight не снижен
  - [x] `test_detraining_warning_message` — warnings содержит "⚠️ Перерыв"
  - [x] `test_no_sessions_no_detraining` — нет истории → detraining не применяется

- [x] **Deload tests:**
  - [x] `test_deload_warning_at_threshold` — 16+ completed sessions → warnings содержит "💤 Рекомендуется дилоад"
  - [x] `test_no_deload_below_threshold` — 10 sessions → нет deload warning

- [x] **Weight rounding tests:**
  - [x] `test_barbell_weight_rounded_to_2_5kg` — raw weight 82.3 → target_weight_kg = 82.5

- [x] **PUOS tests:**
  - [x] `test_puos_auto_reduction_on_excess` — план с 12 сетами для одной группы → автоматически сокращён до 10

- [x] **Antagonist balance tests:**
  - [x] `test_upper_session_only_push_adds_warning` — upper body session с только push → warning о дисбалансе
  - [x] `test_balanced_upper_no_warning` — push + pull → нет warning

- [x] **Rotation tests:**
  - [x] `test_rotation_prefers_unused_exercise` — 2 упражнения для группы, одно использовалось в последней сессии → предпочитается другое

- [x] **Regression:**
  - [x] `uv run pytest tests/test_core/test_planner.py -v` → 27/27 passed ✅
  - [x] `uv run pytest -v` → 325/325 passed ✅

### Review Follow-ups (AI)

- [x] [AI-Review][High] Интегрировать `WorkoutPlanner` в `workout_start`, чтобы `WorkoutSession.split_day_label` и `WorkoutSession.planned_exercises` реально записывались через `api/handlers.py` [gym-coach-brain/src/gym_coach_brain/api/handlers.py:1]
- [x] [AI-Review][High] Убрать hardcoded `3` sets fallback и получать количество сетов из `Methodology`/`ScienceConfig` без `AttributeError`-ветки [gym-coach-brain/src/gym_coach_brain/core/planner.py:568]
- [x] [AI-Review][High] Исправить `custom` split: брать группы из последней завершённой сессии даже когда у historical session `split_day_label IS NULL` [gym-coach-brain/src/gym_coach_brain/core/planner.py:260]
- [x] [AI-Review][Medium] Переделать deload counter на подсчёт `since last deload`, а не по всем completed sessions за всё время [gym-coach-brain/src/gym_coach_brain/core/planner.py:132]
- [x] [AI-Review][Medium] Убрать жёсткий лимит в 5 итераций из PUOS auto-reduction; план не должен возвращаться в всё ещё невалидном состоянии [gym-coach-brain/src/gym_coach_brain/core/planner.py:486]

## Dev Notes

### Зависимости Story 4.7

Story 4.7 **зависит** от:
- `core/puos.py` — `validate_puos`, `accumulate_session_volume` — **УЖЕ СУЩЕСТВУЮТ** ✅
- `core/weight_utils.py` — `round_to_equipment_increment` — **УЖЕ СУЩЕСТВУЕТ** ✅
- `core/readiness.py` — `RecoverySignal` dataclass — **УЖЕ СУЩЕСТВУЕТ** ✅
- `core/science.py` — `ScienceConfig`, `PlanningConfig` — **УЖЕ СУЩЕСТВУЕТ** (расширяем)
- `data/models.py` — `UserProfile`, `WorkoutSession`, `WorkoutSet`, `Exercise`, `MuscleGroup`, `MovementPattern` — **УЖЕ СУЩЕСТВУЮТ** ✅
- `core/methodology.py` — `select_methodology(user_profile, science) -> Methodology` из Story 4.4

**Проверь наличие `core/methodology.py`** перед реализацией:
```bash
ls gym-coach-brain/src/gym_coach_brain/core/
```
Если `methodology.py` не существует (Story 4.4 ещё не завершена), реализуй inline fallback в `planner.py`:
```python
def _get_methodology_rep_range(user_profile, science) -> tuple[int, int]:
    goal = getattr(user_profile, "goal", None) or "hypertrophy"
    if goal == "strength":
        m = science.methodologies.strength
    elif goal == "endurance":
        m = science.methodologies.endurance
    else:
        m = science.methodologies.hypertrophy  # default
    return (m.rep_min, m.rep_max)
```
И количество сетов — используй `3` как дефолт (общепринятый стандарт для гипертрофии).

Story 4.7 **НЕ зависит** от Stories 4.5 / 4.6 / 4.2. Может быть реализована параллельно.

---

### Расширение `core/science.py` — PlanningConfig

Добавить в `PlanningConfig(BaseModel)` ПОСЛЕ существующих полей:

```python
class PlanningConfig(BaseModel):
    """Minimum rest days between same-muscle-group sessions.

    min_rest_days_per_muscle_group: isolation exercises (48h = 2 days;
        PMC6015912, Monteiro 2018; PMC6719818, De Salles 2010).
    min_rest_days_compound: multi-joint movements (72h = 3 days).
    detraining_threshold_days: days of absence after which detraining coefficient is applied.
        Evidence: Mujika & Padilla (2000). 2 weeks = measurable strength loss onset.
    detraining_coefficient: weight multiplier after long break (e.g. 0.85 = 15% reduction).
        Evidence: conservative return protocol to prevent injury on reactivation.
    deload_trigger_sessions: completed sessions in a mesocycle before recommending deload.
        Evidence: Israetel — 3-4 week mesocycles (12-16 sessions at 3-4/week).
    All fields ≥0 to allow placeholder 0 values in skeleton.
    """

    min_rest_days_per_muscle_group: int = Field(ge=0)
    min_rest_days_compound: int = Field(ge=0)
    detraining_threshold_days: int = Field(default=14, ge=1)
    detraining_coefficient: float = Field(default=0.85, ge=0.0, le=1.0)
    deload_trigger_sessions: int = Field(default=16, ge=1)
```

**ВАЖНО:** `default=` гарантирует backward-compatibility — существующие тесты с `PlanningConfig(min_rest_days_per_muscle_group=2, min_rest_days_compound=3)` продолжат работать без изменений. Старые 216+ тестов не сломаются.

[Source: gym-coach-brain/src/gym_coach_brain/core/science.py]

---

### Полная реализация `core/planner.py`

```python
"""
WorkoutPlanner — deterministic daily training plan generator.

Implements the science-driven exercise selection, split-day rotation,
detraining detection, recovery signal scaling, PUOS validation,
and antagonist balance checks.

References:
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.7]
    [Source: _bmad-output/planning-artifacts/architecture.md#FR5]
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from gym_coach_brain.core.readiness import RecoverySignal
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import Exercise, MuscleGroup, UserProfile, WorkoutSession


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class PlannedExercise:
    """One exercise in today's workout plan."""
    exercise_id: int
    exercise_name: str
    sets: int
    rep_range: tuple[int, int]
    target_weight_kg: float


@dataclass
class WorkoutPlan:
    """Complete workout plan for today's session."""
    muscle_groups_today: list[str]
    split_day_label: str
    exercises: list[PlannedExercise]
    skipped_groups: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ─── Split-Day Constants ───────────────────────────────────────────────────────

_PPL_CYCLE: list[str] = ["push", "pull", "legs"]
_UL_CYCLE: list[str] = ["upper", "lower"]


# ─── WorkoutPlanner ───────────────────────────────────────────────────────────

class WorkoutPlanner:
    """Generates deterministic daily workout plans from athlete profile and history.

    Composition Root pattern: create one instance per request, pass science + db_session.
    No global state, no singleton.

    Usage:
        planner = WorkoutPlanner()
        plan = planner.generate(user_profile, science, db_session, recovery_signal)
    """

    def generate(
        self,
        user_profile: "UserProfile",
        science: "ScienceConfig",
        db_session: "SASession",
        recovery_signal: "RecoverySignal | None" = None,
    ) -> WorkoutPlan:
        """Generate complete workout plan for today.

        Args:
            user_profile: Athlete profile with training_split, available_equipment, bodyweight_kg
            science: ScienceConfig with PUOS limits, planning thresholds, methodologies
            db_session: Active SQLAlchemy Session (read-only — no commit)
            recovery_signal: Optional readiness signal; if None, coefficient=1.0 is used

        Returns:
            WorkoutPlan with exercises, warnings, and skipped groups.
        """
        from gym_coach_brain.data.models import WorkoutSession

        today = date.today()

        # ── Step 1: Find last completed session ──────────────────────────────
        last_session: WorkoutSession | None = (
            db_session.query(WorkoutSession)
            .filter(WorkoutSession.status == "completed")
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )

        # ── Step 2: Determine split day and muscle groups ────────────────────
        split_label, muscle_groups = self._determine_split_day(
            user_profile, last_session, db_session
        )

        # ── Step 3: Apply min_rest_days filter ───────────────────────────────
        warnings: list[str] = []
        skipped_groups: list[str] = []

        filtered_groups = self._filter_by_rest_days(
            muscle_groups, today, db_session, science
        )
        if not filtered_groups and muscle_groups:
            # Override: rest days would leave plan empty
            filtered_groups = muscle_groups
            warnings.append(
                "⚠️ Нарушен рекомендуемый отдых — недостаточно времени с последней тренировки"
            )

        # ── Step 4: Check detraining ─────────────────────────────────────────
        apply_detraining = False
        days_gap = 0
        if last_session:
            last_date = date.fromisoformat(last_session.session_date[:10])
            days_gap = (today - last_date).days
            if days_gap > science.planning.detraining_threshold_days:
                apply_detraining = True
                warnings.append(
                    f"⚠️ Перерыв {days_gap} дней — веса снижены для безопасного возврата"
                )

        # ── Step 5: Check deload recommendation ──────────────────────────────
        completed_count = self._count_completed_sessions(db_session)
        if completed_count >= science.planning.deload_trigger_sessions:
            weeks = completed_count // 4  # approximate
            warnings.append(
                f"💤 Рекомендуется дилоад-неделя — {weeks} недель непрерывной нагрузки"
            )

        # ── Step 6: Get methodology (rep range + default sets) ───────────────
        rep_min, rep_max, default_sets = self._get_methodology_params(user_profile, science)
        rep_range = (rep_min, rep_max)

        # ── Step 7: Select exercises and calculate weights ───────────────────
        planned_exercises: list[PlannedExercise] = []
        recovery_coeff = recovery_signal.coefficient if recovery_signal is not None else 1.0

        for mg in filtered_groups:
            exercise = self._select_exercise(mg, user_profile, today, db_session)
            if exercise is None:
                skipped_groups.append(f"{mg.name}:no_equipment")
                continue

            raw_weight = self._calculate_weight(
                exercise, user_profile, science, recovery_coeff,
                apply_detraining, db_session
            )

            from gym_coach_brain.core.weight_utils import round_to_equipment_increment
            rounded_weight = round_to_equipment_increment(
                raw_weight, exercise.equipment_type, science
            )

            planned_exercises.append(
                PlannedExercise(
                    exercise_id=exercise.id,
                    exercise_name=exercise.name,
                    sets=default_sets,
                    rep_range=rep_range,
                    target_weight_kg=rounded_weight,
                )
            )

        # ── Step 8: PUOS validation and auto-reduction ───────────────────────
        planned_exercises = self._apply_puos_reduction(
            planned_exercises, filtered_groups, db_session, science
        )

        # ── Step 9: Antagonist balance check (upper body only) ───────────────
        is_upper_session = split_label in ("upper", "push", "pull", "full_body")
        if is_upper_session and planned_exercises:
            balance_warning = self._check_antagonist_balance(
                planned_exercises, db_session
            )
            if balance_warning:
                warnings.append(balance_warning)

        return WorkoutPlan(
            muscle_groups_today=[mg.name for mg in filtered_groups if mg.name not in
                                  [sg.split(":")[0] for sg in skipped_groups]],
            split_day_label=split_label,
            exercises=planned_exercises,
            skipped_groups=skipped_groups,
            warnings=warnings,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _determine_split_day(
        self,
        user_profile: "UserProfile",
        last_session: "WorkoutSession | None",
        db_session: "SASession",
    ) -> tuple[str, list["MuscleGroup"]]:
        """Return (today_split_label, muscle_groups_for_today)."""
        from gym_coach_brain.data.models import MuscleGroup, TrainingSplit

        split = user_profile.training_split
        prev_label = last_session.split_day_label if last_session else None

        # Query all muscle groups once
        all_groups: list[MuscleGroup] = db_session.query(MuscleGroup).all()

        def groups_by_body_region(region: str) -> list[MuscleGroup]:
            return [g for g in all_groups if g.body_region == region]

        def groups_push() -> list[MuscleGroup]:
            return [g for g in all_groups if g.is_push and g.body_region == "upper"]

        def groups_pull() -> list[MuscleGroup]:
            return [g for g in all_groups if g.is_pull and g.body_region == "upper"]

        def groups_legs() -> list[MuscleGroup]:
            return [g for g in all_groups if g.body_region == "lower"]

        if split == TrainingSplit.full_body or split == "full_body":
            return "full_body", all_groups

        elif split == TrainingSplit.upper_lower or split == "upper_lower":
            if not prev_label or prev_label not in ("upper", "lower"):
                today_label = "upper"
            else:
                today_label = "lower" if prev_label == "upper" else "upper"

            groups = (
                groups_by_body_region("upper")
                if today_label == "upper"
                else groups_by_body_region("lower")
            )
            return today_label, groups

        elif split == TrainingSplit.ppl or split == "ppl":
            if not prev_label or prev_label not in _PPL_CYCLE:
                today_label = "push"
            else:
                idx = _PPL_CYCLE.index(prev_label)
                today_label = _PPL_CYCLE[(idx + 1) % len(_PPL_CYCLE)]

            if today_label == "push":
                groups = groups_push()
            elif today_label == "pull":
                groups = groups_pull()
            else:  # legs
                groups = groups_legs()
            return today_label, groups

        else:  # custom
            if last_session and last_session.split_day_label:
                # Return same groups as last session (approximate via WorkoutSet exercise lookup)
                groups = self._get_last_session_muscle_groups(last_session, db_session)
                return "full_body", groups or all_groups
            return "full_body", all_groups

    def _get_last_session_muscle_groups(
        self, last_session: "WorkoutSession", db_session: "SASession"
    ) -> list["MuscleGroup"]:
        """Get unique primary muscle groups trained in last session."""
        from gym_coach_brain.data.models import Exercise, MuscleGroup, WorkoutSet

        sets = (
            db_session.query(WorkoutSet)
            .filter(WorkoutSet.session_id == last_session.id)
            .all()
        )
        exercise_ids = {ws.exercise_id for ws in sets}
        muscle_ids: set[int] = set()
        for eid in exercise_ids:
            ex = db_session.query(Exercise).filter_by(id=eid).first()
            if ex:
                muscle_ids.add(ex.primary_muscle_id)

        return [
            db_session.query(MuscleGroup).filter_by(id=mid).first()
            for mid in muscle_ids
            if db_session.query(MuscleGroup).filter_by(id=mid).first() is not None
        ]

    def _filter_by_rest_days(
        self,
        groups: list["MuscleGroup"],
        today: date,
        db_session: "SASession",
        science: "ScienceConfig",
    ) -> list["MuscleGroup"]:
        """Exclude muscle groups trained too recently."""
        from gym_coach_brain.data.models import Exercise, MuscleGroup, WorkoutSession, WorkoutSet

        min_rest = science.planning.min_rest_days_per_muscle_group
        allowed: list[MuscleGroup] = []

        for mg in groups:
            # Find most recent session where this muscle group was primary
            last_trained = self._get_last_trained_date(mg.id, db_session)
            if last_trained is None:
                allowed.append(mg)
                continue

            days_since = (today - last_trained).days
            if days_since >= min_rest:
                allowed.append(mg)
            else:
                logger.debug(
                    "Excluding {mg} — trained {days}d ago (min rest: {min}d)",
                    mg=mg.name, days=days_since, min=min_rest,
                )
        return allowed

    def _get_last_trained_date(
        self, muscle_group_id: int, db_session: "SASession"
    ) -> date | None:
        """Return date of most recent session where muscle_group_id was a primary muscle."""
        from gym_coach_brain.data.models import Exercise, WorkoutSession, WorkoutSet

        row = (
            db_session.query(WorkoutSession.session_date)
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .join(Exercise, Exercise.id == WorkoutSet.exercise_id)
            .filter(
                WorkoutSession.status == "completed",
                Exercise.primary_muscle_id == muscle_group_id,
            )
            .order_by(WorkoutSession.session_date.desc())
            .first()
        )
        if row is None:
            return None
        date_str = row[0][:10]
        return date.fromisoformat(date_str)

    def _select_exercise(
        self,
        mg: "MuscleGroup",
        user_profile: "UserProfile",
        today_date: date,
        db_session: "SASession",
    ) -> "Exercise | None":
        """Select best exercise for muscle group based on equipment and rotation."""
        from gym_coach_brain.data.models import Exercise, WorkoutSession, WorkoutSet

        # Get available equipment types
        available_equipment = json.loads(user_profile.available_equipment or "[]")
        if not available_equipment:
            # No equipment filter — include all exercises
            candidates: list[Exercise] = (
                db_session.query(Exercise)
                .filter(Exercise.primary_muscle_id == mg.id)
                .all()
            )
        else:
            from gym_coach_brain.data.models import EquipmentType
            candidates = (
                db_session.query(Exercise)
                .filter(
                    Exercise.primary_muscle_id == mg.id,
                    Exercise.equipment_type.in_(available_equipment),
                )
                .all()
            )

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # Build rotation scores: higher score = less recently used = preferred
        exercise_last_used: dict[int, int] = {}  # exercise_id → days since last use
        for ex in candidates:
            last_set_row = (
                db_session.query(WorkoutSession.session_date)
                .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
                .filter(
                    WorkoutSession.status == "completed",
                    WorkoutSet.exercise_id == ex.id,
                )
                .order_by(WorkoutSession.session_date.desc())
                .first()
            )
            if last_set_row is None:
                exercise_last_used[ex.id] = 9999  # Never used → highest priority
            else:
                last_date = date.fromisoformat(last_set_row[0][:10])
                exercise_last_used[ex.id] = (today_date - last_date).days

        # Sort: highest days_since first; break ties randomly (seeded by date)
        max_score = max(exercise_last_used.values())
        top_candidates = [
            ex for ex in candidates
            if exercise_last_used[ex.id] == max_score
        ]

        if len(top_candidates) == 1:
            return top_candidates[0]

        # Deterministic random tie-breaking
        rng = random.Random(today_date.isoformat())
        return rng.choice(top_candidates)

    def _calculate_weight(
        self,
        exercise: "Exercise",
        user_profile: "UserProfile",
        science: "ScienceConfig",
        recovery_coeff: float,
        apply_detraining: bool,
        db_session: "SASession",
    ) -> float:
        """Compute raw target weight for an exercise before rounding."""
        from gym_coach_brain.data.models import EquipmentType

        if exercise.equipment_type == EquipmentType.bodyweight:
            return 0.0

        # Try last used weight for this exercise
        last_weight = self._get_last_used_weight(exercise.id, db_session)

        if last_weight is not None:
            raw = last_weight
        else:
            # New exercise: look up initial weight from profile
            initial_weights = json.loads(user_profile.initial_weight_coefficients or "{}")
            pattern_name = exercise.movement_pattern.name if exercise.movement_pattern else ""
            initial = initial_weights.get(pattern_name, 0.0)

            if initial == 0.0 and pattern_name and user_profile.bodyweight_kg:
                # Fallback: compute from science table
                exp_level = user_profile.experience_level or "beginner"
                table = science.initial_weight_table.get(exp_level, {})
                coeff = table.get(pattern_name, 0.0)
                initial = (user_profile.bodyweight_kg or 0.0) * coeff

            raw = initial

        # Apply detraining coefficient
        if apply_detraining:
            raw *= science.planning.detraining_coefficient

        # Apply recovery signal
        raw *= recovery_coeff

        return max(0.0, raw)

    def _get_last_used_weight(
        self, exercise_id: int, db_session: "SASession"
    ) -> float | None:
        """Return most recent weight used for this exercise across all sessions."""
        from gym_coach_brain.data.models import WorkoutSession, WorkoutSet

        row = (
            db_session.query(WorkoutSet.weight_kg)
            .join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
            .filter(
                WorkoutSession.status == "completed",
                WorkoutSet.exercise_id == exercise_id,
            )
            .order_by(WorkoutSession.session_date.desc(), WorkoutSet.set_number.desc())
            .first()
        )
        return row[0] if row else None

    def _apply_puos_reduction(
        self,
        exercises: list[PlannedExercise],
        muscle_groups: list["MuscleGroup"],
        db_session: "SASession",
        science: "ScienceConfig",
    ) -> list[PlannedExercise]:
        """Validate PUOS and auto-reduce sets if limit exceeded. Returns adjusted list."""
        from gym_coach_brain.core.puos import validate_puos
        from gym_coach_brain.data.models import Exercise, MuscleGroup
        from gym_coach_brain.exceptions import ScienceLimitError

        # Build volume map from planned exercises
        mg_by_id: dict[int, MuscleGroup] = {mg.id: mg for mg in muscle_groups}

        # Max 5 reduction rounds to avoid infinite loop
        for _ in range(5):
            volume_map: dict[int, float] = {}
            for pe in exercises:
                ex = db_session.query(Exercise).filter_by(id=pe.exercise_id).first()
                if ex is None:
                    continue
                # Primary muscle
                pid = ex.primary_muscle_id
                volume_map[pid] = volume_map.get(pid, 0.0) + pe.sets * 1.0
                # Secondary muscles
                for sid in json.loads(ex.secondary_muscle_ids or "[]"):
                    volume_map[sid] = volume_map.get(sid, 0.0) + pe.sets * 0.5

            violation_found = False
            for mg_id, volume in volume_map.items():
                mg = mg_by_id.get(mg_id) or db_session.query(MuscleGroup).filter_by(id=mg_id).first()
                if mg is None:
                    continue
                try:
                    validate_puos(mg, volume, science)
                except ScienceLimitError:
                    violation_found = True
                    # Find the exercise contributing most to this muscle group
                    max_contrib = 0.0
                    max_idx = -1
                    for i, pe in enumerate(exercises):
                        ex = db_session.query(Exercise).filter_by(id=pe.exercise_id).first()
                        if ex is None:
                            continue
                        contrib = pe.sets * (
                            1.0 if ex.primary_muscle_id == mg_id
                            else 0.5 if mg_id in json.loads(ex.secondary_muscle_ids or "[]")
                            else 0.0
                        )
                        if contrib > max_contrib:
                            max_contrib = contrib
                            max_idx = i
                    if max_idx >= 0 and exercises[max_idx].sets > 1:
                        exercises[max_idx] = PlannedExercise(
                            exercise_id=exercises[max_idx].exercise_id,
                            exercise_name=exercises[max_idx].exercise_name,
                            sets=exercises[max_idx].sets - 1,
                            rep_range=exercises[max_idx].rep_range,
                            target_weight_kg=exercises[max_idx].target_weight_kg,
                        )
                    break  # Re-validate from scratch after reduction

            if not violation_found:
                break

        return exercises

    def _check_antagonist_balance(
        self,
        exercises: list[PlannedExercise],
        db_session: "SASession",
    ) -> str | None:
        """Return warning string if antagonist balance is missing, else None."""
        from gym_coach_brain.data.models import Exercise, MuscleGroup

        has_push = False
        has_pull = False

        for pe in exercises:
            ex = db_session.query(Exercise).filter_by(id=pe.exercise_id).first()
            if ex is None:
                continue
            mg = db_session.query(MuscleGroup).filter_by(id=ex.primary_muscle_id).first()
            if mg is None:
                continue
            if mg.is_push:
                has_push = True
            if mg.is_pull:
                has_pull = True

        if has_push and not has_pull:
            return "⚠️ Дисбаланс: только push упражнения — рекомендуется добавить антагонист"
        if has_pull and not has_push:
            return "⚠️ Дисбаланс: только pull упражнения — рекомендуется добавить антагонист"
        return None

    def _get_methodology_params(
        self,
        user_profile: "UserProfile",
        science: "ScienceConfig",
    ) -> tuple[int, int, int]:
        """Return (rep_min, rep_max, default_sets) based on user goal and methodology."""
        goal = getattr(user_profile, "goal", None) or "hypertrophy"

        if goal == "strength":
            m = science.methodologies.strength
        elif goal == "endurance":
            m = science.methodologies.endurance
        else:
            m = science.methodologies.hypertrophy  # safe default

        # Try to use methodology.py if available (Story 4.4)
        try:
            from gym_coach_brain.core.methodology import select_methodology
            methodology = select_methodology(user_profile, science)
            return methodology.rep_range[0], methodology.rep_range[1], methodology.sets
        except (ImportError, AttributeError):
            # Story 4.4 not yet implemented — use inline fallback
            return m.rep_min, m.rep_max, 3  # 3 sets default

    def _count_completed_sessions(self, db_session: "SASession") -> int:
        """Count total completed sessions (for deload recommendation)."""
        from gym_coach_brain.data.models import WorkoutSession
        return (
            db_session.query(WorkoutSession)
            .filter(WorkoutSession.status == "completed")
            .count()
        )
```

---

### Project Structure Notes

**Файлы, создаваемые в Story 4.7:**

```
src/gym_coach_brain/
└── core/
    └── planner.py          ← СОЗДАТЬ (WorkoutPlanner, WorkoutPlan, PlannedExercise)

tests/
└── test_core/
    └── test_planner.py     ← СОЗДАТЬ
```

**Файлы, изменяемые в Story 4.7:**

```
gym-coach-brain/ScienceEvidence.md            ← добавить 3 поля в planning:
src/gym_coach_brain/core/science.py           ← добавить 3 поля в PlanningConfig
tests/conftest.py                              ← обновить PlanningConfig в mock_science_config
```

**Файлы, НЕ изменяемые:**

```
data/models.py          ← WorkoutSession.split_day_label УЖЕ СУЩЕСТВУЕТ
api/handlers.py         ← workout_start/plan handler будет добавлен в Story 6.1
core/puos.py            ← validate_puos/accumulate_session_volume УЖЕ СУЩЕСТВУЮТ
core/weight_utils.py    ← round_to_equipment_increment УЖЕ СУЩЕСТВУЕТ
core/readiness.py       ← RecoverySignal УЖЕ СУЩЕСТВУЕТ
adaptation/             ← НЕ трогать
```

**Следующие истории — потребители `WorkoutPlanner`:**
- Story 6.1 (workout_api_handlers): `handle_workout_plan()` вызовет `WorkoutPlanner.generate()` и сохранит `WorkoutPlan.split_day_label` в `WorkoutSession.split_day_label`, `planned_exercises` в `WorkoutSession.planned_exercises` (JSON)

---

### Архитектурные ограничения

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.data.models import WorkoutSession, WorkoutSet     # ✅
from ..data.models import WorkoutSet                                    # ❌ запрещено

# 2. Dependency direction — core/ → data/ (не наоборот):
# planner.py МОЖЕТ импортировать из data/models.py и core/puos.py, core/weight_utils.py
# data/ и adaptation/ НЕ импортируют из core/planner.py в этой истории

# 3. ScienceConfig как параметр:
def generate(self, user_profile, science: ScienceConfig, db_session, ...):  # ✅
SCIENCE = load_science_config()                                              # ❌ запрещено

# 4. SQLAlchemy session передаётся как параметр — НЕ создаётся внутри:
def generate(self, ..., db_session: SASession): ...                          # ✅

# 5. НЕ вызывать session.commit() — только api/ слой коммитит:
db_session.flush()  # ✅ если нужно получить ID
# db_session.commit()  # ❌ запрещено в planner

# 6. TYPE_CHECKING guard для всех ORM types и ScienceConfig:
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gym_coach_brain.data.models import WorkoutSession  # ✅

# 7. random.seed(date) для детерминизма выбора упражнений:
rng = random.Random(today_date.isoformat())  # ✅ — не глобальный random.seed()

# 8. loguru для логирования:
from loguru import logger
logger.debug("message {key}", key=value)     # ✅
print("debug")                               # ❌ запрещено
```

[Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

- **Python 3.14+** — нативные `list[str]`, `tuple[int, int]`, `dict[int, float]`
- **SQLAlchemy 2.0+** — `db_session.query(WorkoutSession).filter(...).first()` — паттерн из `api/handlers.py`
- **Pydantic 2.0+** — расширяем `PlanningConfig(BaseModel)` в `core/science.py`
- **stdlib `json`** — парсинг `UserProfile.available_equipment`, `Exercise.secondary_muscle_ids`
- **stdlib `random`** — `random.Random(seed)` для детерминированного выбора упражнений
- **stdlib `datetime.date`** — `date.today()`, `date.fromisoformat()`, `(date1 - date2).days`
- **loguru** — уже в pyproject.toml (из Story 3.2+)
- **НЕ импортировать torch** — `core/` изолирован от ML слоя

---

### Previous Story Intelligence

Из Stories 4.2 / 4.5 / 4.6:

1. **Паттерн SQLAlchemy query** (используется везде):
   ```python
   result = (
       db_session.query(WorkoutSession)
       .filter(WorkoutSession.status == "completed")
       .order_by(WorkoutSession.session_date.desc())
       .first()
   )
   ```

2. **Паттерн `from __future__ import annotations` + `TYPE_CHECKING`** — обязательно для всех новых файлов в `core/`:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from gym_coach_brain.core.science import ScienceConfig
   ```

3. **available_equipment** читается как JSON list:
   ```python
   available_equipment = json.loads(user_profile.available_equipment or "[]")
   ```

4. **secondary_muscle_ids** читается как JSON list:
   ```python
   secondary_ids = json.loads(exercise.secondary_muscle_ids or "[]")
   ```

5. **Loguru pattern** из `core/puos.py`:
   ```python
   logger.warning("PUOS limit approached: {sets}/{limit}", sets=9, limit=11.0)
   ```

6. **WorkoutSession.split_day_label** — уже существует в `data/models.py` (добавлено в Story 3.2):
   ```python
   split_day_label = Column(String, nullable=True)  # push / pull / legs / upper / lower / full_body
   ```

7. **WorkoutSession.planned_exercises** — уже существует:
   ```python
   planned_exercises = Column(Text, nullable=True)  # JSON-encoded list of PlannedExercise dicts
   ```

8. **`validate_puos` бросает `ScienceLimitError`** — нужно ловить и auto-reduce в planner, не пропускать наружу:
   ```python
   from gym_coach_brain.exceptions import ScienceLimitError
   try:
       validate_puos(mg, volume, science)
   except ScienceLimitError:
       # reduce sets and retry
   ```

---

### Git Intelligence

```
11b8cbb Reposition README with product narrative and unique value proposition
425df73 Add GitHub stars and forks badges to README header
d005f82 Rewrite README in English
201009c feat: add bmad planning artifacts, project docs, gym-coach-brain and skill
```

- Последние коммиты — только README и документация; кодовая база стабильна
- Baseline тестов: 216+ PASS (Stories 4.1-4.3 реализованы; 4.4-4.6 в процессе)
- `core/planner.py` **не существует** → создать
- `WorkoutSession.split_day_label` **уже существует** в `data/models.py` ✅

---

### Известные риски и edge cases

1. **`core/methodology.py` может не существовать** (Story 4.4 в процессе):
   - Решение: `try/except ImportError` в `_get_methodology_params()` с inline fallback ✅ (уже в коде выше)

2. **Пустая база упражнений** (seed не запускался):
   - Тесты должны создавать тестовые упражнения в `db_session` через fixtures
   - НЕ зависеть от реального seed

3. **`user_profile.movement_pattern` JOIN**: `exercise.movement_pattern` требует загруженного relationship:
   - Используй `db_session.query(Exercise).filter_by(id=...).first()` — lazy load работает для unit тестов
   - В production через `api/handlers.py` session контекст гарантирует доступность

4. **`UserProfile.training_split` — SQLAlchemy Enum**:
   - Может быть `TrainingSplit.ppl` или строкой `"ppl"` — проверяй через `str(split).split(".")[-1]` или `==` с оба вариантами

5. **Нет завершённых сессий** (первая тренировка):
   - `last_session = None` → все fallback пути должны работать
   - `_get_last_used_weight` → вернёт `None` → используй initial weights

---

### References

- Story 4.7 требования: [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.7]
- WorkoutSession, WorkoutSet, UserProfile, Exercise, MuscleGroup: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py]
- validate_puos, accumulate_session_volume: [Source: gym-coach-brain/src/gym_coach_brain/core/puos.py]
- round_to_equipment_increment: [Source: gym-coach-brain/src/gym_coach_brain/core/weight_utils.py]
- RecoverySignal, calculate_recovery_signal: [Source: gym-coach-brain/src/gym_coach_brain/core/readiness.py]
- ScienceConfig, PlanningConfig: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py]
- calculate_double_progression: [Source: gym-coach-brain/src/gym_coach_brain/core/progression.py]
- API handler pattern (session management): [Source: gym-coach-brain/src/gym_coach_brain/api/handlers.py]
- conftest.py fixtures: [Source: gym-coach-brain/tests/conftest.py]
- FR5 (training plan): [Source: _bmad-output/planning-artifacts/architecture.md#Requirements to Structure Mapping]
- Previous story patterns: [Source: _bmad-output/implementation-artifacts/4-6-recap-summary.md]
- Architecture constraints: [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

## File List

- `gym-coach-brain/ScienceEvidence.md` — modified: added 3 planning fields (detraining_threshold_days, detraining_coefficient, deload_trigger_sessions)
- `gym-coach-brain/src/gym_coach_brain/api/handlers.py` — modified: added `workout_start` integration that persists `split_day_label`, `planned_exercises`, and a `PREDICT` ML job
- `gym-coach-brain/src/gym_coach_brain/core/science.py` — modified: extended PlanningConfig with 3 new fields with defaults
- `gym-coach-brain/src/gym_coach_brain/core/planner.py` — created and refined: WorkoutPlanner now reuses last-session groups for `custom`, derives sets from methodology/science, counts deload since last deload session, and reduces PUOS until valid
- `gym-coach-brain/tests/conftest.py` — modified: updated mock_science_config PlanningConfig with new fields
- `gym-coach-brain/tests/test_api/test_handlers.py` — modified: added workout_start persistence coverage
- `gym-coach-brain/tests/test_core/test_planner.py` — created and expanded: 31 tests covering story ACs plus review regressions
- `_bmad-output/implementation-artifacts/4-7-workout-planner.md` — modified: review follow-ups completed, notes/file list updated, status moved to `review`
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — modified: story status updated to `review`

## Change Log

- 2026-03-09: Story 4.7 implemented — WorkoutPlanner with split-day rotation, min_rest_days, detraining, deload, PUOS validation, antagonist balance, equipment filtering, exercise rotation. 325/325 tests pass.
- 2026-03-09: Senior Developer Review added — 3 High / 2 Medium findings, review follow-ups appended, status moved back to in-progress.
- 2026-03-09: Addressed code review findings — 5 items resolved. Added `workout_start` integration, fixed `custom` history lookup, derived sets from methodology/science, reset deload counting after deload sessions, and removed the PUOS reduction cap. 332/332 tests pass.
- 2026-03-09: Adversarial Code Review fixes applied — Fixed a critical issue where PUOS auto-reduction raised `ScienceLimitError` instead of gracefully dropping exercises, resolving a violation of the AC. Fixed an N+1 query issue in antagonist balance checks and committed previously untracked `planner.py` files. Tests run and passed.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- ✅ ScienceEvidence.md extended with detraining_threshold_days=14, detraining_coefficient=0.85, deload_trigger_sessions=16
- ✅ PlanningConfig backward-compatible (defaults) — 21 existing science tests unchanged
- ✅ core/planner.py created: WorkoutPlanner class with all 10 generate() steps and 7 private helpers
- ✅ methodology.py exists (Story 4.4 done); planner now derives default sets from Methodology frequency and PUOS limits without `AttributeError` fallback
- ✅ `custom` split now reuses the last completed session's muscle groups even when historical `split_day_label` is null
- ✅ Deload warning now counts completed sessions since the most recent `methodology="deload"` session
- ✅ PUOS auto-reduction now keeps reducing until the plan validates or raises a science limit error
- ✅ `handle_workout_start()` now persists `WorkoutSession.split_day_label`, `WorkoutSession.planned_exercises`, and a `PREDICT` job
- ✅ 31 planner tests and 332 total tests — all pass
- ✅ Architecture constraints followed: absolute imports only, no session.commit(), TYPE_CHECKING guard, random.Random(seed) not global seed
- ✅ Resolved review finding [High]: `WorkoutPlanner` is now integrated into `workout_start`
- ✅ Resolved review finding [High]: set count is derived from Methodology and ScienceConfig without a hardcoded fallback
- ✅ Resolved review finding [High]: `custom` split now honors last completed session groups when `split_day_label` is null
- ✅ Resolved review finding [Medium]: deload counter resets after the last deload session
- ✅ Resolved review finding [Medium]: PUOS auto-reduction no longer stops after five iterations
- ✅ Resolved adversarial review finding [High]: PUOS auto-reduction drops exercises completely when sets reach 0, rather than crashing with `ScienceLimitError`.
- ✅ Resolved adversarial review finding [Medium]: N+1 query in `_check_antagonist_balance` replaced with a single joined query.
- ✅ Resolved adversarial review finding [Medium]: `core/planner.py` and `test_planner.py` staged to git.

### File List

## Senior Developer Review (AI)

### Reviewer

Max

### Date

2026-03-09

### Outcome

Changes Requested

### Findings

1. `WorkoutPlanner` не подключён к application flow: в `api/handlers.py` отсутствует `workout_start` path, поэтому `split_day_label` и `planned_exercises` не сохраняются в `WorkoutSession`.
2. Количество сетов не берётся из `Methodology`: `planner.py` пытается читать `methodology.sets`, но `Methodology` такого поля не имеет, и код молча падает на hardcoded `3`.
3. `custom` split работает неверно для существующей истории без `split_day_label`: вместо повторения последней завершённой сессии planner возвращает `all_groups`.
4. Deload recommendation считает все completed sessions за всё время, а не с момента последнего deload.
5. PUOS auto-reduction ограничен пятью итерациями и может вернуть всё ещё невалидный план.

### Validation Notes

- Verified `uv run pytest tests/test_core/test_planner.py -q` → 27 passed.
- Verified `uv run pytest -q` → 327 passed.
- Worktree contains unrelated application changes outside Story 4.7; AC validation was limited to story files plus integration surfaces.
