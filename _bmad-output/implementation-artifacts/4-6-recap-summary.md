# Story 4.6: Recap и Summary генераторы

Status: done

## Story

As an athlete,
I want to receive a Recap before my workout and a Summary after,
so that I stay informed about my progress and recovery without manual analysis.

## Acceptance Criteria

**Given** история тренировок атлета в БД и адаптированный план готовы
**When** OpenClaw отправляет интент `workout_recap`
**Then** `adaptation/recap.py` возвращает журнал предыдущей тренировки: список упражнений, веса и количество повторений по каждому подходу
**And** Recap — фактические данные из БД (последняя `WorkoutSession` со `status="completed"`), без LLM-генерации
**And** формат: по одной строке на упражнение, все подходы через запятую, например: `"Жим лёжа: 80кг × 8, 80кг × 7, 77.5кг × 8"`
**And** если предыдущей завершённой сессии нет — возвращается строка `"Первая тренировка — история пока пуста"`

**When** OpenClaw отправляет интент `workout_summary`
**Then** `adaptation/summary.py` возвращает оценку завершённой тренировки на основе данных БД
**And** Summary включает: общий объём выполненных подходов (целое число)
**And** Summary включает оценку усталости по RPE-тренду:
- средний RPE < `science.summary.rpe_easy_threshold` → `"Объёмы хорошие 💪"` (спокойная тренировка)
- средний RPE >= `science.summary.rpe_fatigue_threshold` OR веса снижались к концу сессии → `"Видно что устал 😤"` (высокая нагрузка)
- иначе (между порогами) → `"Нормальная нагрузка"`
- пороги берутся из `ScienceConfig.summary.rpe_easy_threshold` и `rpe_fatigue_threshold` (не hardcoded)
**And** Summary включает сравнение плана и факта:
- план читается из `WorkoutSession.planned_exercises` (JSON list)
- пропущенные упражнения отмечаются строкой `"❌ Пропущено: [название]"`
- выполненные сверхплана отмечаются строкой `"➕ Дополнительно: [название]"`
- при полном совпадении — дополнительные строки не добавляются
**And** `core/science.py` расширяется классом `SummaryConfig(BaseModel)` с `rpe_easy_threshold: float` (default 7.0) и `rpe_fatigue_threshold: float` (default 8.0); `ScienceConfig` получает поле `summary: SummaryConfig`
**And** `ScienceEvidence.md` расширяется секцией `summary:` с обоими порогами
**And** `tests/conftest.py` обновляется: `SummaryConfig` добавляется в импорты и `mock_science_config`

**And** `pytest tests/test_adaptation/test_recap.py` и `tests/test_adaptation/test_summary.py` проходят с seed-данными сессий:
- Recap: пустая история → `"Первая тренировка — история пока пуста"`
- Recap: есть одна завершённая сессия → правильный формат строки
- Summary: полное выполнение плана → нет `❌`, нет `➕`
- Summary: пропуск упражнения → `❌ Пропущено` присутствует
- Summary: сверхплановое упражнение → `➕ Дополнительно` присутствует
- Summary: avg_rpe < easy_threshold → `"Объёмы хорошие"`
- Summary: avg_rpe >= fatigue_threshold → `"Видно что устал"`

## Tasks / Subtasks

- [x] **Расширить `ScienceEvidence.md`** (AC: summary thresholds)
  - [x] Добавить после секции `ml:` секцию `summary:` с двумя порогами:
    ```yaml
    summary:
      rpe_easy_threshold: 7.0      # float — avg RPE below which session is "easy"
      rpe_fatigue_threshold: 8.0   # float — avg RPE above which session shows fatigue
    ```
  - [x] Проверить: `uv run python -c "from gym_coach_brain.core.science import load_science_config; c = load_science_config(); print(c.summary.rpe_easy_threshold)"`

- [x] **Расширить `core/science.py`** (AC: SummaryConfig)
  - [x] Добавить после `MLConfig`:
    ```python
    class SummaryConfig(BaseModel):
        rpe_easy_threshold: float = Field(default=7.0, ge=0.0, le=10.0)
        rpe_fatigue_threshold: float = Field(default=8.0, ge=0.0, le=10.0)
    ```
  - [x] Добавить поле `summary: SummaryConfig = Field(default_factory=SummaryConfig)` в `ScienceConfig`
  - [x] Проверить: существующие тесты `test_core/test_science.py` PASS (backward-compat default_factory)

- [x] **Обновить `tests/conftest.py`** (AC: mock_science_config с summary)
  - [x] Добавить `SummaryConfig` в импорт из `gym_coach_brain.core.science`
  - [x] Добавить `summary=SummaryConfig(rpe_easy_threshold=7.0, rpe_fatigue_threshold=8.0)` в `mock_science_config`

- [x] **Создать `adaptation/recap.py`** (AC: generate_recap функция)
  - [x] Реализовать `generate_recap(db_session, user_profile_id) -> str`:
    - [x] Найти последнюю `WorkoutSession` со `status="completed"` для данного `user_profile_id` или глобально (если нет user_id FK)
    - [x] Если не найдена → вернуть `"Первая тренировка — история пока пуста"`
    - [x] Для каждого уникального `exercise_id` в `WorkoutSet` → сгруппировать подходы по упражнению
    - [x] Для каждого упражнения: `"{exercise_name}: {w1}кг × {r1}, {w2}кг × {r2}, ..."` (по `set_number`)
    - [x] Для bodyweight (weight_kg=0.0): формат `"Подтягивания: × 12, × 10, × 11"` (без веса)
    - [x] Вернуть все строки через `\n`

- [x] **Создать `adaptation/summary.py`** (AC: generate_summary функция)
  - [x] Реализовать `generate_summary(session, db_session, science) -> str`:
    - [x] `session` — завершённая `WorkoutSession` ORM объект
    - [x] Собрать все `WorkoutSet` для сессии, вычислить:
      - `total_sets` — общее количество подходов
      - `avg_rpe` — средний RPE по всем подходам (где rpe не None)
      - `weight_trend` — сравнить первый и последний подход для каждого упражнения (снизился ли вес к концу)
    - [x] Оценка усталости через пороги из `science.summary`
    - [x] Сравнение плана и факта:
      - `planned_names` = `{ex["exercise_name"] for ex in json.loads(session.planned_exercises or "[]")}`
      - `actual_names` = `{WorkoutSet.exercise.name}` по всем сетам сессии (через join с exercises)
      - Пропущенные: `planned_names - actual_names`
      - Дополнительные: `actual_names - planned_names`
    - [x] Собрать финальную строку и вернуть

- [x] **Создать `tests/test_adaptation/__init__.py`** (если не создан в Story 4.5)
  - [x] Пустой файл — обеспечивает корректное обнаружение pytest

- [x] **Создать `tests/test_adaptation/test_recap.py`** (AC: Recap тесты)
  - [x] `test_recap_empty_history` — нет завершённых сессий → возвращает "Первая тренировка..."
  - [x] `test_recap_formats_sets_correctly` — сессия с 3 подходами → правильный формат `"Жим лёжа: 80.0кг × 8, ..."`
  - [x] `test_recap_bodyweight_omits_weight` — weight_kg=0.0 → формат без веса `"Подтягивания: × 12"`
  - [x] `test_recap_latest_completed_session` — несколько сессий → возвращает именно последнюю completed
  - [x] `test_recap_ignores_non_completed_sessions` — сессия со status="planned" → игнорируется

- [x] **Создать `tests/test_adaptation/test_summary.py`** (AC: Summary тесты)
  - [x] `test_summary_no_missed_no_extra` — plan = actual → нет `❌`, нет `➕`
  - [x] `test_summary_missed_exercise` — упражнение в плане, не выполнено → `❌ Пропущено`
  - [x] `test_summary_extra_exercise` — выполнено сверхплана → `➕ Дополнительно`
  - [x] `test_summary_easy_rpe` — avg_rpe 5.0 (< 7.0) → `"Объёмы хорошие"`
  - [x] `test_summary_high_rpe` — avg_rpe 9.0 (>= 8.0) → `"Видно что устал"`
  - [x] `test_summary_total_sets_count` — 3 упражнения × 3 подхода → `total_sets=9` в выводе
  - [x] `test_summary_thresholds_from_science_config` — меняем пороги в mock → оценка меняется

- [x] **Регрессионная проверка:**
  - [x] `uv run pytest tests/test_adaptation/ -v` — 12 passed
  - [x] `uv run pytest -v` — полная регрессия: 296 passed

### Review Follow-ups (AI)

- [x] [AI-Review][High] Honor the weight-decline fatigue rule even when RPE is missing; `generate_summary()` currently returns `"Нормальная нагрузка"` before checking `weight_declined`, which misses an explicit AC branch. [gym-coach-brain/src/gym_coach_brain/adaptation/summary.py:102]
- [x] [AI-Review][High] Make recap selection deterministic for same-timestamp completed sessions; ordering only by `session_date` reproduced a stale recap from the older row instead of the latest completed workout. [gym-coach-brain/src/gym_coach_brain/adaptation/recap.py:44]
- [x] [AI-Review][Medium] Guard `planned_exercises` parsing in `generate_summary()`; malformed JSON currently raises `JSONDecodeError` and aborts summary generation instead of degrading safely. [gym-coach-brain/src/gym_coach_brain/adaptation/summary.py:64]
- [x] [AI-Review][Medium] Reconcile Story 4.6 documentation with the current worktree: the File List omits modified application files, and the story explicitly says `adaptation/engine.py` / `explanation.py` are not changed even though git shows changes there. [_bmad-output/implementation-artifacts/4-6-recap-summary.md:618]

## Dev Notes

### Зависимости Story 4.6

Story 4.6 **не зависит** от Stories 4.2, 4.3, 4.4, 4.5. Она независима и может быть реализована параллельно с другими историями Epic 4. Зависит только от:
- `data/models.py` — `WorkoutSession`, `WorkoutSet`, `Exercise` — **УЖЕ СУЩЕСТВУЮТ**
- `core/science.py` — `ScienceConfig` — **УЖЕ СУЩЕСТВУЕТ** (добавляем `SummaryConfig`)

**Если Story 4.5 ещё не реализована** — `tests/test_adaptation/__init__.py` нужно создать здесь.
**Если Story 4.5 уже реализована** — `__init__.py` уже есть, просто добавляем новые тест-файлы.

---

### Расширение `core/science.py`

Добавить после класса `MLConfig` (добавленного в Story 4.5):

```python
class SummaryConfig(BaseModel):
    """RPE thresholds for post-workout fatigue assessment.

    rpe_easy_threshold: avg RPE below this → session classified as "easy"
    rpe_fatigue_threshold: avg RPE at or above this → "fatigued" classification

    Based on: Borg RPE scale application to resistance training feedback.
    RPE 7 = 3 RIR (3 reps in reserve) — comfortable working zone.
    RPE 8 = 2 RIR — approaching challenging territory.
    """
    rpe_easy_threshold: float = Field(default=7.0, ge=0.0, le=10.0)
    rpe_fatigue_threshold: float = Field(default=8.0, ge=0.0, le=10.0)
```

Обновить `ScienceConfig`:
```python
class ScienceConfig(BaseModel):
    # ... все существующие поля ...
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
```

**ВАЖНО:** `default_factory=SummaryConfig` гарантирует backward-compatibility — старые `ScienceConfig(...)` без `summary=` продолжат работать. Все существующие 216 тестов не сломаются.

[Source: gym-coach-brain/src/gym_coach_brain/core/science.py]

---

### Расширение `ScienceEvidence.md`

Добавить секцию после существующей или планируемой `ml:` секции:

```yaml
summary:
  rpe_easy_threshold: 7.0    # float — avg RPE below which session is "easy" (3 RIR = comfortable)
  rpe_fatigue_threshold: 8.0 # float — avg RPE above which athlete shows fatigue (2 RIR = hard)
```

[Source: gym-coach-brain/ScienceEvidence.md]

---

### Полная реализация `adaptation/recap.py`

```python
"""
Pre-workout Recap generator.

Implements FR15: pre-workout Recap of previous session.
Pure DB read — no LLM, no computation. Data is presented as-is
from the most recent completed WorkoutSession.

References:
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.6]
    [Source: _bmad-output/planning-artifacts/architecture.md#FR15: Recap]
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

_NO_HISTORY_MSG = "Первая тренировка — история пока пуста"


def generate_recap(db_session: "SASession") -> str:
    """Generate pre-workout Recap from the most recent completed session.

    Reads last WorkoutSession with status='completed', groups WorkoutSet
    records by exercise, and formats one line per exercise with all sets.

    Format per exercise:
        "Жим лёжа: 80.0кг × 8, 80.0кг × 7, 77.5кг × 8"
    For bodyweight exercises (weight_kg=0.0):
        "Подтягивания: × 12, × 10, × 11"

    Args:
        db_session: Active SQLAlchemy Session (read-only, no commit)

    Returns:
        Formatted recap string, or _NO_HISTORY_MSG if no completed sessions.
    """
    from gym_coach_brain.data.models import WorkoutSession, WorkoutSet, Exercise

    # Find the most recent completed session
    last_session = (
        db_session.query(WorkoutSession)
        .filter(WorkoutSession.status == "completed")
        .order_by(WorkoutSession.session_date.desc())
        .first()
    )

    if last_session is None:
        return _NO_HISTORY_MSG

    # Load all sets for this session ordered by exercise + set_number
    sets = (
        db_session.query(WorkoutSet)
        .filter(WorkoutSet.session_id == last_session.id)
        .order_by(WorkoutSet.exercise_id, WorkoutSet.set_number)
        .all()
    )

    if not sets:
        return _NO_HISTORY_MSG

    # Group sets by exercise, preserving order
    exercise_sets: dict[int, list[WorkoutSet]] = defaultdict(list)
    exercise_names: dict[int, str] = {}

    for ws in sets:
        exercise_sets[ws.exercise_id].append(ws)
        if ws.exercise_id not in exercise_names:
            exercise = db_session.query(Exercise).filter_by(id=ws.exercise_id).first()
            exercise_names[ws.exercise_id] = exercise.name if exercise else f"exercise_{ws.exercise_id}"

    lines: list[str] = []
    for exercise_id, ex_sets in exercise_sets.items():
        name = exercise_names[exercise_id]
        set_strs: list[str] = []
        for ws in ex_sets:
            if ws.weight_kg == 0.0:
                set_strs.append(f"× {ws.reps}")
            else:
                set_strs.append(f"{ws.weight_kg}кг × {ws.reps}")
        lines.append(f"{name}: {', '.join(set_strs)}")

    return "\n".join(lines)
```

---

### Полная реализация `adaptation/summary.py`

```python
"""
Post-workout Summary generator.

Implements FR16: post-workout Summary with fatigue assessment and plan/actual comparison.
Deterministic — all data from DB and ScienceConfig, no LLM.

References:
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.6]
    [Source: _bmad-output/planning-artifacts/architecture.md#FR16: Summary]
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import WorkoutSession
    from sqlalchemy.orm import Session as SASession


def generate_summary(
    session: "WorkoutSession",
    db_session: "SASession",
    science: "ScienceConfig",
) -> str:
    """Generate post-workout Summary for a completed session.

    Computes:
    - Total sets performed
    - Average RPE and fatigue assessment (vs science.summary thresholds)
    - Plan vs actual exercise comparison (missed / extra exercises)

    Args:
        session: Completed WorkoutSession ORM object (status='completed')
        db_session: Active SQLAlchemy Session (read-only)
        science: ScienceConfig with summary.rpe_easy_threshold and rpe_fatigue_threshold

    Returns:
        Multi-line summary string for stdout → Telegram.
    """
    from gym_coach_brain.data.models import WorkoutSet, Exercise

    sets = (
        db_session.query(WorkoutSet)
        .filter(WorkoutSet.session_id == session.id)
        .order_by(WorkoutSet.exercise_id, WorkoutSet.set_number)
        .all()
    )

    total_sets = len(sets)

    # ── RPE trend ────────────────────────────────────────────────────────────
    rpe_values = [ws.rpe for ws in sets if ws.rpe is not None]
    avg_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None

    # Weight decline trend: check if last set weight < first set weight per exercise
    weight_declined = _detect_weight_decline(sets)

    fatigue_label = _assess_fatigue(avg_rpe, weight_declined, science)

    # ── Plan vs actual ───────────────────────────────────────────────────────
    planned_names: set[str] = set()
    planned_raw = json.loads(session.planned_exercises or "[]")
    for ex in planned_raw:
        planned_names.add(ex.get("exercise_name", ""))

    actual_exercise_ids = {ws.exercise_id for ws in sets}
    actual_names: set[str] = set()
    for eid in actual_exercise_ids:
        exercise = db_session.query(Exercise).filter_by(id=eid).first()
        if exercise:
            actual_names.add(exercise.name)

    missed = planned_names - actual_names
    extra = actual_names - planned_names

    # ── Build output ─────────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"📊 Итоги тренировки")
    lines.append(f"Выполнено подходов: {total_sets}")

    if avg_rpe is not None:
        lines.append(f"Средний RPE: {avg_rpe:.1f} — {fatigue_label}")
    else:
        lines.append(f"RPE: не зафиксирован — {fatigue_label}")

    for name in sorted(missed):
        lines.append(f"❌ Пропущено: {name}")
    for name in sorted(extra):
        lines.append(f"➕ Дополнительно: {name}")

    return "\n".join(lines)


def _assess_fatigue(
    avg_rpe: float | None,
    weight_declined: bool,
    science: "ScienceConfig",
) -> str:
    """Return fatigue label based on avg_rpe and weight trend."""
    if avg_rpe is None:
        return "Нормальная нагрузка"
    if avg_rpe >= science.summary.rpe_fatigue_threshold or weight_declined:
        return "Видно что устал 😤"
    if avg_rpe < science.summary.rpe_easy_threshold:
        return "Объёмы хорошие 💪"
    return "Нормальная нагрузка"


def _detect_weight_decline(sets: list) -> bool:
    """Return True if any exercise had a weight decline from first to last set."""
    from collections import defaultdict
    exercise_sets: dict[int, list] = defaultdict(list)
    for ws in sets:
        exercise_sets[ws.exercise_id].append(ws)

    for ex_sets in exercise_sets.values():
        sorted_sets = sorted(ex_sets, key=lambda s: s.set_number)
        if len(sorted_sets) >= 2:
            first_w = sorted_sets[0].weight_kg
            last_w = sorted_sets[-1].weight_kg
            if last_w < first_w:
                return True
    return False
```

---

### `tests/conftest.py` — обновление

Добавить `SummaryConfig` в импорты и `mock_science_config`:

```python
from gym_coach_brain.core.science import (
    ScienceConfig,
    PUOSConfig,
    ProgressionConfig,
    RecoveryConfig,
    MethodologySpec,
    MethodologiesConfig,
    PlanningConfig,
    MLConfig,        # добавлено в Story 4.5
    SummaryConfig,   # добавляется в Story 4.6
)
```

Дополнить `mock_science_config`:
```python
return ScienceConfig(
    # ... все существующие поля ...
    ml=MLConfig(confidence_threshold=0.6),       # добавлено в Story 4.5
    plateau_detection_sessions=3,                 # добавлено в Story 4.5
    summary=SummaryConfig(                        # добавляется в Story 4.6
        rpe_easy_threshold=7.0,
        rpe_fatigue_threshold=8.0,
    ),
)
```

**Если Story 4.5 ещё не реализована:** `MLConfig` и `plateau_detection_sessions` ещё не существуют — пропустите их. Добавьте только `SummaryConfig`.

[Source: gym-coach-brain/tests/conftest.py]

---

### Пример тестов

```python
# tests/test_adaptation/test_recap.py

def test_recap_empty_history(db_session):
    from gym_coach_brain.adaptation.recap import generate_recap
    result = generate_recap(db_session)
    assert result == "Первая тренировка — история пока пуста"


def test_recap_formats_sets_correctly(db_session):
    from gym_coach_brain.adaptation.recap import generate_recap
    from gym_coach_brain.data.models import (
        WorkoutSession, WorkoutSet, Exercise, MuscleGroup, MovementPattern
    )

    # Setup: muscle group, movement pattern, exercise
    mg = MuscleGroup(name="chest", body_region="upper", is_push=True, is_pull=False, stretch_mediated=False)
    mp = MovementPattern(name="horizontal_push", category="push")
    db_session.add_all([mg, mp])
    db_session.flush()

    ex = Exercise(
        name="Жим лёжа", primary_muscle_id=mg.id, movement_pattern_id=mp.id,
        is_compound=True, stretch_mediated=False, equipment_type="barbell",
    )
    db_session.add(ex)
    db_session.flush()

    # Completed session with 3 sets
    sess = WorkoutSession(session_date="2026-03-08", status="completed")
    db_session.add(sess)
    db_session.flush()

    for i, (w, r) in enumerate([(80.0, 8), (80.0, 7), (77.5, 8)], start=1):
        db_session.add(WorkoutSet(
            session_id=sess.id, exercise_id=ex.id,
            set_number=i, weight_kg=w, reps=r
        ))
    db_session.flush()

    result = generate_recap(db_session)
    assert "Жим лёжа" in result
    assert "80.0кг × 8" in result
    assert "77.5кг × 8" in result


def test_recap_latest_completed_session(db_session):
    """Returns the most recent completed session, not an older one."""
    from gym_coach_brain.adaptation.recap import generate_recap
    from gym_coach_brain.data.models import WorkoutSession, WorkoutSet, Exercise, MuscleGroup, MovementPattern

    # ... setup exercises and two completed sessions on different dates ...
    # Assert result contains sets from the LATER session
```

```python
# tests/test_adaptation/test_summary.py

def test_summary_no_missed_no_extra(db_session, mock_science_config):
    from gym_coach_brain.adaptation.summary import generate_summary
    import json
    from gym_coach_brain.data.models import (
        WorkoutSession, WorkoutSet, Exercise, MuscleGroup, MovementPattern
    )

    # ... setup exercise, session with planned_exercises matching actual sets ...
    result = generate_summary(session, db_session, mock_science_config)
    assert "❌" not in result
    assert "➕" not in result


def test_summary_missed_exercise(db_session, mock_science_config):
    """Exercise in plan but not performed → ❌ Пропущено."""
    from gym_coach_brain.adaptation.summary import generate_summary
    # ... planned: ["Жим лёжа", "Тяга"], actual: ["Жим лёжа"] ...
    result = generate_summary(session, db_session, mock_science_config)
    assert "❌ Пропущено: Тяга" in result


def test_summary_easy_rpe(db_session, mock_science_config):
    """avg_rpe < easy_threshold → 'Объёмы хорошие'."""
    from gym_coach_brain.adaptation.summary import generate_summary
    # sets with rpe=5.0 (all below 7.0 threshold)
    result = generate_summary(session, db_session, mock_science_config)
    assert "Объёмы хорошие" in result


def test_summary_high_rpe(db_session, mock_science_config):
    """avg_rpe >= fatigue_threshold → 'Видно что устал'."""
    from gym_coach_brain.adaptation.summary import generate_summary
    # sets with rpe=9.0 (above 8.0 threshold)
    result = generate_summary(session, db_session, mock_science_config)
    assert "Видно что устал" in result


def test_summary_thresholds_from_science_config(db_session):
    """Changing thresholds changes classification — confirms not hardcoded."""
    from gym_coach_brain.adaptation.summary import generate_summary
    from gym_coach_brain.core.science import ScienceConfig, SummaryConfig

    # Use threshold of 6.0 — same avg_rpe=7.5 now above threshold
    custom_science = ...  # build ScienceConfig with rpe_fatigue_threshold=6.0
    result = generate_summary(session, db_session, custom_science)
    assert "Видно что устал" in result
```

---

### Архитектурные ограничения

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.data.models import WorkoutSession, WorkoutSet      # ✅
from ..data.models import WorkoutSet                                     # ❌ запрещено

# 2. Dependency direction — adaptation/ → data/ (не наоборот):
# recap.py и summary.py МОГУТ импортировать из data/models.py
# data/ НЕ импортирует из adaptation/

# 3. ScienceConfig как параметр:
def generate_summary(session, db_session, science: ScienceConfig): ...  # ✅
SCIENCE = load_science_config()                                          # ❌ запрещено

# 4. SQLAlchemy session передаётся как параметр — НЕ создаётся внутри функций:
def generate_recap(db_session: SASession) -> str: ...                   # ✅

# 5. НЕ вызывать session.commit() — это делает вызывающий (api/ слой):
session.add(...)
session.flush()  # ✅ если нужно получить ID
# session.commit()  # ❌ запрещено в handlers, но recap/summary только читают

# 6. TYPE_CHECKING guard для всех ORM types:
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gym_coach_brain.data.models import WorkoutSession  # ✅
```

[Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

- **Python 3.14+** — нативные `str | None`, `dict[int, list]`
- **SQLAlchemy 2.0+** — `db_session.query(WorkoutSession).filter(...).first()` — паттерн из `api/handlers.py`
- **Pydantic 2.0+** — `SummaryConfig(BaseModel)` добавляется в `core/science.py`
- **stdlib `json`** — парсинг `WorkoutSession.planned_exercises`
- **stdlib `collections.defaultdict`** — группировка сетов по упражнению
- **НЕ импортировать torch** — `adaptation/` не использует PyTorch

---

### Project Structure Notes

**Файлы, создаваемые в Story 4.6:**

```
src/gym_coach_brain/
└── adaptation/
    ├── recap.py            ← СОЗДАТЬ (generate_recap)
    └── summary.py          ← СОЗДАТЬ (generate_summary)

tests/
└── test_adaptation/
    ├── __init__.py         ← СОЗДАТЬ если не существует (Story 4.5 может уже создать)
    ├── test_recap.py       ← СОЗДАТЬ
    └── test_summary.py     ← СОЗДАТЬ
```

**Файлы, изменяемые в Story 4.6:**

```
gym-coach-brain/ScienceEvidence.md       ← добавить summary: секцию
src/gym_coach_brain/core/science.py      ← добавить SummaryConfig
tests/conftest.py                        ← добавить SummaryConfig в импорты и mock
```

**Файлы, НЕ изменяемые:**

```
data/models.py     ← НЕ трогать (WorkoutSession, WorkoutSet, Exercise уже существуют)
api/handlers.py    ← НЕ трогать (handlers для workout_recap/summary будут добавлены в Story 6.1)
adaptation/engine.py, explanation.py    ← НЕ трогать (Story 4.5)
core/apre.py, progression.py, puos.py, readiness.py  ← НЕ трогать
```

**Следующие истории — потребители `recap.py`/`summary.py`:**
- Story 6.1 (workout_api_handlers): `api/handlers.py` получит `handle_workout_recap()` и `handle_workout_summary()`, которые вызовут `generate_recap()` и `generate_summary()`

---

### Previous Story Intelligence

Из Story 4.5 (`adaptation/engine.py`):

1. **Паттерн группировки сетов по упражнению** (точно такой же нужен для Recap):
   ```python
   from collections import defaultdict
   exercise_sets: dict[int, list] = defaultdict(list)
   for row in rows:
       exercise_sets[row.exercise_id].append(row)
   ```

2. **Запрос WorkoutSet через SQLAlchemy** (аналогичный паттерн):
   ```python
   sets = (
       db_session.query(WorkoutSet)
       .filter(WorkoutSet.session_id == session.id)
       .order_by(WorkoutSet.exercise_id, WorkoutSet.set_number)
       .all()
   )
   ```

3. **`from __future__ import annotations` + `TYPE_CHECKING`** — обязательно для всех новых файлов.

4. **Pure functions** — `generate_recap()` и `generate_summary()` не делают DB-writes, принимают session как параметр.

5. **Формат вывода** — строки для Telegram (через OpenClaw stdout), никакого JSON.

---

### Git Intelligence

```
11b8cbb Reposition README with product narrative and unique value proposition
425df73 Add GitHub stars and forks badges to README header
d005f82 Rewrite README in English
201009c feat: add bmad planning artifacts, project docs, gym-coach-brain and skill
```

- Последние коммиты — README-only
- Кодовая база стабильна: `adaptation/__init__.py` существует, `recap.py`/`summary.py` **не существуют** → создать
- Текущий baseline: **216 тестов** PASS (подтверждено перед созданием этой истории)
- Story 4.6 не ломает существующие тесты: все изменения в `science.py` используют `default_factory`

---

### References

- Story 4.6 требования: [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.6]
- WorkoutSession, WorkoutSet, Exercise: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py]
- API handler pattern: [Source: gym-coach-brain/src/gym_coach_brain/api/handlers.py]
- ScienceConfig structure: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py]
- conftest.py fixtures: [Source: gym-coach-brain/tests/conftest.py]
- FR15 (Recap), FR16 (Summary): [Source: _bmad-output/planning-artifacts/architecture.md#Requirements to Structure Mapping]
- Enforcement rules: [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]
- Previous story patterns: [Source: _bmad-output/implementation-artifacts/4-5-adaptation-engine.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Reproduced the three open code findings with focused pytest cases before patching `recap.py` and `summary.py`.
- Revalidated with focused adaptation tests, full repo regression, and a direct `load_science_config()` threshold probe after the fixes.

### Completion Notes List

- Implemented `generate_recap(db_session) -> str` in `adaptation/recap.py`. Pure DB read, groups WorkoutSet by exercise_id, formats lines with weight or bodyweight style.
- Implemented `generate_summary(session, db_session, science) -> str` in `adaptation/summary.py`. Computes total_sets, avg_rpe fatigue label (via ScienceConfig.summary thresholds), and plan/actual comparison.
- Added `SummaryConfig(BaseModel)` to `core/science.py` with `rpe_easy_threshold` and `rpe_fatigue_threshold` fields; added `summary` field to `ScienceConfig` using `default_factory=SummaryConfig` for backward compat.
- Extended `ScienceEvidence.md` frontmatter with `summary:` section (both thresholds).
- Updated `tests/conftest.py`: added `SummaryConfig` to imports and `mock_science_config`.
- Created 12 tests: 5 for recap (empty history, format, bodyweight, latest session, non-completed ignored), 7 for summary (plan/actual, RPE thresholds, total sets, configurable thresholds).
- Added review regression tests for same-timestamp recap ordering, fatigue from weight decline without RPE, and malformed `planned_exercises` JSON fallback.
- `generate_recap()` now breaks tied `session_date` values with `id DESC`, which makes latest completed-session selection deterministic.
- `generate_summary()` now honors the weight-decline fatigue rule even when RPE is missing and falls back to an empty plan when `planned_exercises` contains malformed JSON.
- Reconciled the story File List with the current `gym-coach-brain` worktree, including parallel edits already present during validation.
- Validation after fixes: `uv run pytest tests/test_adaptation/test_recap.py tests/test_adaptation/test_summary.py -v` → 15 passed; `uv run pytest -v` → 336 passed; `uv run python -c "from gym_coach_brain.core.science import load_science_config; ..."` → `7.0 8.0`.

### File List

_Current `gym-coach-brain` worktree observed during validation:_

gym-coach-brain/ScienceEvidence.md
gym-coach-brain/src/gym_coach_brain/adaptation/engine.py
gym-coach-brain/src/gym_coach_brain/adaptation/explanation.py
gym-coach-brain/src/gym_coach_brain/adaptation/recap.py
gym-coach-brain/src/gym_coach_brain/adaptation/summary.py
gym-coach-brain/src/gym_coach_brain/api/handlers.py
gym-coach-brain/src/gym_coach_brain/core/planner.py
gym-coach-brain/src/gym_coach_brain/core/readiness.py
gym-coach-brain/src/gym_coach_brain/core/science.py
gym-coach-brain/src/gym_coach_brain/data/features.py
gym-coach-brain/tests/conftest.py
gym-coach-brain/tests/test_adaptation/test_engine.py
gym-coach-brain/tests/test_adaptation/test_explanation.py
gym-coach-brain/tests/test_adaptation/test_recap.py
gym-coach-brain/tests/test_adaptation/test_summary.py
gym-coach-brain/tests/test_api/test_handlers.py
gym-coach-brain/tests/test_api/test_readiness_handler.py
gym-coach-brain/tests/test_core/test_planner.py

### Senior Developer Review (AI)

**Reviewer:** Max  
**Date:** 2026-03-09  
**Outcome:** Changes Requested

**Scope loaded**
- Story 4.6 implementation artifact, Epic 4 requirements, architecture, and project-context
- No UX design artifact was present for this story
- Tech stack confirmed from project context: Python 3.14, SQLAlchemy 2.x, Pydantic 2.x, SQLite, pytest

**Validation performed**
- `uv run pytest tests/test_adaptation/test_recap.py tests/test_adaptation/test_summary.py -q` → 12 passed
- `uv run pytest -q` → 298 passed
- `uv run python -c "from gym_coach_brain.core.science import load_science_config; ..."` → summary thresholds load as `7.0 / 8.0`
- Targeted runtime probes reproduced two defects:
  - weight drop with no RPE still reports `"Нормальная нагрузка"`
  - two completed sessions with identical `session_date` return the older recap

**Findings**
1. **High:** `generate_summary()` short-circuits to `"Нормальная нагрузка"` when `avg_rpe is None`, so the required `weight_declined` fatigue path is never evaluated unless RPE was logged. This misses the AC branch `fatigue_threshold OR weights declined`. [gym-coach-brain/src/gym_coach_brain/adaptation/summary.py:102]
2. **High:** `generate_recap()` orders completed sessions only by `session_date DESC`. With two completed rows sharing the same timestamp, SQLite returned the older row in a reproduction, so the recap is not reliably the latest workout. [gym-coach-brain/src/gym_coach_brain/adaptation/recap.py:44]
3. **Medium:** `generate_summary()` trusts `session.planned_exercises` blindly. A malformed JSON payload raises `JSONDecodeError` and aborts summary generation instead of falling back to an empty plan or a controlled error path. [gym-coach-brain/src/gym_coach_brain/adaptation/summary.py:64]
4. **Medium:** The story documentation no longer matches the worktree. The story says `adaptation/engine.py` and `explanation.py` are not modified and omits several changed application files from the File List, but git currently shows changes in `adaptation/engine.py`, `adaptation/explanation.py`, `data/features.py`, `tests/test_adaptation/test_engine.py`, and `tests/test_adaptation/test_explanation.py`. [_bmad-output/implementation-artifacts/4-6-recap-summary.md:618]

**Git vs Story discrepancies**
- Files changed in git but absent from the story File List: `gym-coach-brain/src/gym_coach_brain/adaptation/engine.py`, `gym-coach-brain/src/gym_coach_brain/adaptation/explanation.py`, `gym-coach-brain/src/gym_coach_brain/data/features.py`, `gym-coach-brain/tests/test_adaptation/test_engine.py`, `gym-coach-brain/tests/test_adaptation/test_explanation.py`
- Story File List entries for the 4.6 files do correspond to current changes
- No staged changes were present during review

**References**
- Python `json` library docs: `json.loads()` raises `JSONDecodeError` on invalid documents
- SQLite SELECT semantics: ordering among ties needs an explicit tie-breaker to be deterministic

## Change Log

| Date | Change |
|------|--------|
| 2026-03-09 | Story 4.6 implemented: added SummaryConfig to science.py, ScienceEvidence.md; created adaptation/recap.py (generate_recap) and adaptation/summary.py (generate_summary); added 12 tests covering all ACs; 296 tests pass. |
| 2026-03-09 | Senior Developer Review (AI): Changes requested. Added 4 follow-up items, moved status to `in-progress`, and synced sprint tracking. |
| 2026-03-09 | Addressed code review findings: fixed same-timestamp recap ordering, honored fatigue from weight decline without RPE, hardened malformed `planned_exercises` parsing, synced the File List with the current worktree, and revalidated with 15 focused tests plus 336 full-suite passes. |
| 2026-03-09 | Adversarial Code Review: Fixed N+1 queries in recap and summary, improved drop set fatigue heuristic, added strict list check for planned_exercises, formatting fixes, tracked files in git. Status moved to done. |
