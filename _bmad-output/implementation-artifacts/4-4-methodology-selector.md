# Story 4.4: Селектор тренировочной методологии

Status: done

## Story

As an athlete,
I want the system to select and apply a training methodology based on my profile,
so that my workout plan matches my goals using science-backed protocols.

## Acceptance Criteria

**Given** `UserProfile` с целью атлета и `ScienceConfig` с секцией `methodologies` доступны
**When** `select_methodology(user_profile, science)` вызывается
**Then** возвращается `Methodology` объект с `rep_range`, `progression_type`, `frequency`
**And** выбор детерминирован: одинаковый профиль → одинаковая методология
**And** методология применяется как надстройка — передаётся в APRE/Double Progression как параметры
**And** смена методологии не требует изменения кода — только обновления ScienceEvidence.md
**And** `pytest tests/test_core/test_methodology.py` проходит: все методологии из ScienceConfig корректно применяются

## Tasks / Subtasks

- [x] **Создать `core/methodology.py`** (AC: Methodology dataclass + select_methodology)
  - [x] Определить `RepRange` NamedTuple: `min: int, max: int`
  - [x] Определить `ProgressionType` str-Enum: `DOUBLE_PROGRESSION = "double_progression"`, `APRE = "apre"`
  - [x] Определить dataclass `Methodology(name, rep_range, progression_type, frequency_min, frequency_max)`
  - [x] Реализовать `select_methodology(user_profile, science) -> Methodology` — pure function
  - [x] Маппинг `user_profile.goal` → методология из `science.methodologies`:
    - `"strength"` → `science.methodologies.strength` + ProgressionType.APRE
    - `"hypertrophy"` или `None` или unknown → `science.methodologies.hypertrophy` + ProgressionType.DOUBLE_PROGRESSION
    - `"endurance"` → `science.methodologies.endurance` + ProgressionType.DOUBLE_PROGRESSION
  - [x] Case-insensitive маппинг: `"Strength"`, `"STRENGTH"` → strength
  - [x] `get_progression_type(goal: str | None) -> ProgressionType` — вспомогательная чистая функция
  - [x] Функция детерминирована: нет randomness, нет DB-вызовов, нет side effects

- [x] **Создать тесты `tests/test_core/test_methodology.py`** (AC: all methodologies from ScienceConfig)
  - [x] Тест: goal="strength" → Methodology с rep_range=(1,5), progression_type=APRE
  - [x] Тест: goal="hypertrophy" → Methodology с rep_range=(6,12), progression_type=DOUBLE_PROGRESSION
  - [x] Тест: goal="endurance" → Methodology с rep_range=(15,30), progression_type=DOUBLE_PROGRESSION
  - [x] Тест: goal=None → default hypertrophy methodology
  - [x] Тест: goal="STRENGTH" (upper case) → strength methodology (case-insensitive)
  - [x] Тест: goal="unknown_goal" → default hypertrophy methodology
  - [x] Тест: детерминизм — два вызова с одинаковым профилем возвращают идентичные результаты
  - [x] Тест: rep_range берётся из ScienceConfig, не захардкожен
  - [x] Тест: frequency_min/max берётся из ScienceConfig, не захардкожен
  - [x] `uv run pytest tests/test_core/test_methodology.py -v` — все PASS
  - [x] `uv run pytest -v` — полная регрессия PASS (≥172 passed baseline)

## Dev Notes

### ⚠️ Критические Prerequisites

```bash
cd gym-coach-brain
uv run pytest -v   # Ожидается: 172+ passed (baseline перед Story 4.4)
```

Story 4.4 **не зависит** от Stories 4.1, 4.2, 4.3 (независима). Зависит только от:
- `core/science.py` — `MethodologiesConfig`, `MethodologySpec`, `ScienceConfig` — УЖЕ СУЩЕСТВУЮТ
- `data/models.py` — `UserProfile` с полями `goal` и `experience_level` — УЖЕ СУЩЕСТВУЕТ
- `tests/conftest.py` — `mock_science_config` с methodologies — УЖЕ СОДЕРЖИТ нужные данные

---

### Критически важные поля `UserProfile` из models.py

```python
# gym-coach-brain/src/gym_coach_brain/data/models.py (строки 90+)
class UserProfile(Base):
    __tablename__ = "user_profiles"

    goal = Column(String, nullable=True)              # "strength" | "hypertrophy" | "endurance" | None
    experience_level = Column(String, nullable=True)  # "beginner" | "intermediate" | "advanced"
    training_split = Column(...)                      # TrainingSplit enum
```

**Ключевой факт:** `goal` — nullable String. Функция должна обрабатывать `None` без ошибки.

[Source: gym-coach-brain/src/gym_coach_brain/data/models.py#UserProfile]

---

### Существующая структура `ScienceConfig.methodologies`

```python
# Уже реализовано в core/science.py:
class MethodologySpec(BaseModel):
    rep_min: int = Field(ge=0)
    rep_max: int = Field(ge=0)
    frequency_per_week_min: int = Field(ge=0)
    frequency_per_week_max: int = Field(ge=0)

class MethodologiesConfig(BaseModel):
    strength: MethodologySpec
    hypertrophy: MethodologySpec
    endurance: MethodologySpec

class ScienceConfig(BaseModel):
    ...
    methodologies: MethodologiesConfig
```

Реальные значения из `ScienceEvidence.md`:
- `strength`: rep_min=1, rep_max=5, frequency_per_week_min=2, frequency_per_week_max=4
- `hypertrophy`: rep_min=6, rep_max=12, frequency_per_week_min=2, frequency_per_week_max=4
- `endurance`: rep_min=15, rep_max=30, frequency_per_week_min=3, frequency_per_week_max=5

[Source: gym-coach-brain/src/gym_coach_brain/core/science.py#MethodologiesConfig]
[Source: gym-coach-brain/ScienceEvidence.md#Training Methodologies]

---

### Полная реализация `core/methodology.py`

```python
"""
Training methodology selection for workout planning.

Implements the pluggable methodology pattern from architecture ADR-002:
selecting a training methodology based on UserProfile.goal maps to
a MethodologySpec from ScienceConfig. Zero hardcoded rep ranges — all
values come from ScienceConfig, so methodology updates require only
updating ScienceEvidence.md.

References:
    Schoenfeld, B.J. & Grgic, J. (2021). PMC7927075.
    [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.4]
    [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig
    from gym_coach_brain.data.models import UserProfile


# ─── Types ────────────────────────────────────────────────────────────────────

class RepRange(NamedTuple):
    """Inclusive rep range for a given methodology."""
    min: int
    max: int


class ProgressionType(str, Enum):
    """Which progression algorithm to use for this methodology."""
    DOUBLE_PROGRESSION = "double_progression"   # default for hypertrophy/endurance
    APRE = "apre"                                # used for strength goal


# ─── Methodology Result ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Methodology:
    """Resolved methodology parameters for a training session.

    All values are derived from ScienceConfig — never hardcoded.
    The frozen dataclass ensures immutability (deterministic per call).

    Attributes:
        name: Methodology name ("strength" | "hypertrophy" | "endurance")
        rep_range: Inclusive rep range (min, max) from ScienceConfig
        progression_type: Which progression algorithm to apply
        frequency_min: Minimum training sessions per muscle group per week
        frequency_max: Maximum training sessions per muscle group per week
    """
    name: str
    rep_range: RepRange
    progression_type: ProgressionType
    frequency_min: int
    frequency_max: int


# ─── Goal → Progression Type Mapping ─────────────────────────────────────────

def get_progression_type(goal: str | None) -> ProgressionType:
    """Return the appropriate progression algorithm for a given goal.

    Strength training uses APRE (auto-regulatory) for near-maximal loads.
    Hypertrophy and endurance use Double Progression (volume-first progression).

    Args:
        goal: User's training goal. Case-insensitive. None → hypertrophy default.

    Returns:
        ProgressionType enum value.
    """
    if goal is not None and goal.lower() == "strength":
        return ProgressionType.APRE
    return ProgressionType.DOUBLE_PROGRESSION


# ─── Core Selector ────────────────────────────────────────────────────────────

def select_methodology(
    user_profile: "UserProfile",
    science: "ScienceConfig",
) -> Methodology:
    """Select and return a training methodology based on the athlete's goal.

    Pure function — no side effects, no DB calls, no randomness.
    Methodology parameters come entirely from ScienceConfig (zero hardcoding).

    Goal → Methodology mapping:
        "strength"            → science.methodologies.strength + APRE
        "hypertrophy" / None  → science.methodologies.hypertrophy + DOUBLE_PROGRESSION
        "endurance"           → science.methodologies.endurance + DOUBLE_PROGRESSION
        <any other value>     → default hypertrophy (safe fallback)

    Matching is case-insensitive: "STRENGTH", "Strength", "strength" all match.

    Args:
        user_profile: UserProfile ORM object with .goal (nullable string)
        science: ScienceConfig instance with .methodologies section

    Returns:
        Methodology with rep_range and progression_type from ScienceConfig.

    References:
        [Source: gym-coach-brain/ScienceEvidence.md#Training Methodologies]
        [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002 ScienceConfig Loading]
    """
    goal = user_profile.goal
    normalized = goal.lower() if goal is not None else None

    if normalized == "strength":
        spec = science.methodologies.strength
        name = "strength"
    elif normalized == "endurance":
        spec = science.methodologies.endurance
        name = "endurance"
    else:
        # Default: hypertrophy (covers None, "hypertrophy", any unknown goal)
        spec = science.methodologies.hypertrophy
        name = "hypertrophy"

    return Methodology(
        name=name,
        rep_range=RepRange(min=spec.rep_min, max=spec.rep_max),
        progression_type=get_progression_type(goal),
        frequency_min=spec.frequency_per_week_min,
        frequency_max=spec.frequency_per_week_max,
    )
```

---

### Тесты — `tests/test_core/test_methodology.py`

```python
"""Tests for core/methodology.py — methodology selection."""
import pytest

from gym_coach_brain.core.methodology import (
    Methodology,
    ProgressionType,
    RepRange,
    get_progression_type,
    select_methodology,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_user_profile(goal=None, experience_level="intermediate"):
    """Create UserProfile-like object without DB."""
    from gym_coach_brain.data.models import UserProfile
    profile = UserProfile.__new__(UserProfile)
    profile.goal = goal
    profile.experience_level = experience_level
    return profile


# ─── ProgressionType mapping ──────────────────────────────────────────────────

def test_strength_goal_uses_apre():
    assert get_progression_type("strength") == ProgressionType.APRE

def test_hypertrophy_goal_uses_double_progression():
    assert get_progression_type("hypertrophy") == ProgressionType.DOUBLE_PROGRESSION

def test_endurance_goal_uses_double_progression():
    assert get_progression_type("endurance") == ProgressionType.DOUBLE_PROGRESSION

def test_none_goal_uses_double_progression():
    assert get_progression_type(None) == ProgressionType.DOUBLE_PROGRESSION

def test_unknown_goal_uses_double_progression():
    assert get_progression_type("powerlifting") == ProgressionType.DOUBLE_PROGRESSION


# ─── Methodology selection ────────────────────────────────────────────────────

def test_strength_goal_selects_strength_methodology(mock_science_config):
    profile = make_user_profile(goal="strength")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "strength"
    assert m.rep_range == RepRange(min=1, max=5)
    assert m.progression_type == ProgressionType.APRE
    assert m.frequency_min == 2
    assert m.frequency_max == 4


def test_hypertrophy_goal_selects_hypertrophy_methodology(mock_science_config):
    profile = make_user_profile(goal="hypertrophy")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"
    assert m.rep_range == RepRange(min=6, max=12)
    assert m.progression_type == ProgressionType.DOUBLE_PROGRESSION
    assert m.frequency_min == 2
    assert m.frequency_max == 4


def test_endurance_goal_selects_endurance_methodology(mock_science_config):
    profile = make_user_profile(goal="endurance")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "endurance"
    assert m.rep_range == RepRange(min=15, max=30)
    assert m.progression_type == ProgressionType.DOUBLE_PROGRESSION
    assert m.frequency_min == 3
    assert m.frequency_max == 5


def test_none_goal_defaults_to_hypertrophy(mock_science_config):
    profile = make_user_profile(goal=None)
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"
    assert m.progression_type == ProgressionType.DOUBLE_PROGRESSION


def test_unknown_goal_defaults_to_hypertrophy(mock_science_config):
    profile = make_user_profile(goal="powerlifting")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"


# ─── Case insensitivity ───────────────────────────────────────────────────────

def test_strength_goal_case_insensitive_upper(mock_science_config):
    profile = make_user_profile(goal="STRENGTH")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "strength"
    assert m.progression_type == ProgressionType.APRE


def test_strength_goal_case_insensitive_mixed(mock_science_config):
    profile = make_user_profile(goal="Strength")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "strength"


def test_hypertrophy_goal_case_insensitive(mock_science_config):
    profile = make_user_profile(goal="HYPERTROPHY")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "hypertrophy"


def test_endurance_goal_case_insensitive(mock_science_config):
    profile = make_user_profile(goal="ENDURANCE")
    m = select_methodology(profile, mock_science_config)
    assert m.name == "endurance"


# ─── Determinism ─────────────────────────────────────────────────────────────

def test_same_profile_returns_identical_methodology(mock_science_config):
    """Same input → same output (no randomness)."""
    profile = make_user_profile(goal="strength")
    m1 = select_methodology(profile, mock_science_config)
    m2 = select_methodology(profile, mock_science_config)
    assert m1 == m2


def test_methodology_from_science_config_not_hardcoded(mock_science_config):
    """Rep range must come from ScienceConfig, not hardcoded values.

    We verify by checking the returned values match the mock_science_config
    (not some fixed number). If someone hardcodes '6' instead of reading
    spec.rep_min, this test would catch it when mock is changed.
    """
    profile = make_user_profile(goal="hypertrophy")
    m = select_methodology(profile, mock_science_config)
    spec = mock_science_config.methodologies.hypertrophy
    assert m.rep_range.min == spec.rep_min
    assert m.rep_range.max == spec.rep_max
    assert m.frequency_min == spec.frequency_per_week_min
    assert m.frequency_max == spec.frequency_per_week_max
```

---

### Architecture Compliance Constraints

```python
# 1. ТОЛЬКО абсолютные импорты:
from gym_coach_brain.core.science import ScienceConfig        # ✅
from gym_coach_brain.data.models import UserProfile            # ✅
from gym_coach_brain.core.methodology import select_methodology # ✅
from ..data.models import UserProfile                          # ❌ запрещено

# 2. ScienceConfig как параметр:
def select_methodology(user_profile, science: ScienceConfig): # ✅
SCIENCE = load_science_config()  # ❌ запрещено на module level

# 3. TYPE_CHECKING guard для избегания circular imports:
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gym_coach_brain.core.science import ScienceConfig    # ✅

# 4. Dependency direction — core/ НЕ импортирует из api/:
# core/ → data/ (only for TYPE_CHECKING)
# api/ → core/ (to call select_methodology)

# 5. Frozen dataclass (immutability):
@dataclass(frozen=True)
class Methodology: ...                                         # ✅

# 6. НЕ добавлять torch импорты — core/ детерминированное ядро
```

[Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

---

### Library & Framework Requirements

- **Python 3.14+** — `from __future__ import annotations`, нативный `str | None`
- **Pydantic 2.0+** — `ScienceConfig`, `MethodologiesConfig` — уже существуют, не изменяются
- **SQLAlchemy 2.0+** — `UserProfile` — уже существует, не изменяется; тесты используют `__new__` без DB
- **pytest** — тесты используют `mock_science_config` fixture из `conftest.py`
- **НЕ импортировать torch** — `core/methodology.py` — чистое детерминированное ядро

---

### Testing Requirements

**Fixtures** из `tests/conftest.py`:
- `mock_science_config` — содержит полные `MethodologiesConfig`:
  - `strength`: rep_min=1, rep_max=5, frequency=2-4
  - `hypertrophy`: rep_min=6, rep_max=12, frequency=2-4
  - `endurance`: rep_min=15, rep_max=30, frequency=3-5
- `db_session` — **НЕ НУЖЕН** для `test_methodology.py` (pure function без DB)

**Стратегия тестирования:**
- `select_methodology` — pure function, тесты без DB
- `UserProfile` создаётся через `UserProfile.__new__(UserProfile)` — без DB
- Тесты проверяют: все 3 методологии, case-insensitivity, детерминизм, привязку к ScienceConfig

**Запуск:**
```bash
cd gym-coach-brain
uv run pytest tests/test_core/test_methodology.py -v
uv run pytest -v   # полная регрессия
```

---

### Project Structure Notes

**Файлы, изменяемые в Story 4.4:**

```
src/gym_coach_brain/core/
└── methodology.py          ← СОЗДАТЬ (новый файл)

tests/test_core/
└── test_methodology.py     ← СОЗДАТЬ (новый файл)
```

**Файлы, не изменяемые:**
```
core/science.py             ← НЕ трогать (MethodologiesConfig уже есть)
data/models.py              ← НЕ трогать (UserProfile уже есть)
api/handlers.py             ← НЕ трогать (Story 4.4 не добавляет handler)
tests/conftest.py           ← НЕ трогать (fixtures уже содержат methodologies)
```

**Следующие истории — потребители `Methodology`:**
- Story 4.5: `AdaptationEngine.adapt(...)` получает `Methodology` как параметр
- Story 4.7: `WorkoutPlanner.generate(...)` вызывает `select_methodology()` перед генерацией плана

**Критический интерфейс для Story 4.5/4.7:**
```python
# Способ вызова в следующих историях:
methodology = select_methodology(user_profile, science)
# methodology.rep_range.min → нижняя граница диапазона
# methodology.rep_range.max → верхняя граница диапазона
# methodology.progression_type → APRE или DOUBLE_PROGRESSION
# methodology.frequency_min/max → частота в неделю
```

---

### Previous Story Intelligence (Story 4.3)

Паттерны из Story 4.3, применимые к Story 4.4:

1. **`from __future__ import annotations` + `TYPE_CHECKING`** guard:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from gym_coach_brain.data.models import UserProfile
   ```

2. **Dataclass для структурированных результатов:**
   ```python
   @dataclass
   class RecoverySignal: ...    # Story 4.3 паттерн
   @dataclass(frozen=True)
   class Methodology: ...       # Story 4.4: frozen для immutability
   ```

3. **Pure function без side effects:**
   ```python
   def calculate_recovery_signal(readiness_log, science): ...  # Story 4.3
   def select_methodology(user_profile, science): ...          # Story 4.4
   ```

4. **`UserProfile.__new__(UserProfile)` в тестах** — без DB:
   ```python
   log = ReadinessLog.__new__(ReadinessLog)   # Story 4.3 паттерн
   profile = UserProfile.__new__(UserProfile) # Story 4.4
   ```

5. **НЕ использовать `Optional[T]`** — нативный Python 3.14+ union: `str | None`

---

### Git Intelligence

```
11b8cbb Reposition README with product narrative and unique value proposition
425df73 Add GitHub stars and forks badges to README header
d005f82 Rewrite README in English
e324018 Replace README header banner with logo image
201009c feat: add bmad planning artifacts, project docs, gym-coach-brain and skill
```

**Выводы:**
- Последние 4 коммита — только README, кодовая база gym-coach-brain не менялась
- Вся модульная структура в коммите `201009c` — `core/science.py` с `MethodologiesConfig` уже существует
- Story 4.4 добавляет только `core/methodology.py` (новый файл) и `tests/test_core/test_methodology.py`
- Dev agent НЕ делает git commit (только если явно попросят)

---

### References

- Story 4.4 требования: [Source: _bmad-output/planning-artifacts/epics/epic-4.md#Story 4.4]
- MethodologiesConfig: [Source: gym-coach-brain/src/gym_coach_brain/core/science.py#MethodologiesConfig]
- UserProfile.goal: [Source: gym-coach-brain/src/gym_coach_brain/data/models.py#UserProfile]
- mock_science_config fixture: [Source: gym-coach-brain/tests/conftest.py]
- Architecture ADR-002: [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
- ScienceEvidence methodologies: [Source: gym-coach-brain/ScienceEvidence.md#Training Methodologies]
- Architecture enforcement: [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Summary]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `UserProfile.__new__(UserProfile)` не инициализирует SQLAlchemy instrumented attributes — исправлено на `UserProfile(goal=goal, experience_level=experience_level)` по паттерну из `test_onboarding.py`.

### Completion Notes List

- Создан `core/methodology.py`: `RepRange` NamedTuple, `ProgressionType` str-Enum, `Methodology` frozen dataclass, `get_progression_type()`, `select_methodology()` — все pure functions без side effects
- Все значения берутся из `ScienceConfig.methodologies`, нет hardcoded чисел
- Case-insensitive маппинг goal → methodology через `.lower()`
- Создан `tests/test_core/test_methodology.py`: 16 тестов — все PASS
- Полная регрессия: 249 passed (baseline был 172+)
- Архитектурные требования соблюдены: `TYPE_CHECKING` guard, абсолютные импорты, `frozen=True`

### File List

- `gym-coach-brain/src/gym_coach_brain/core/methodology.py` (создан)
- `gym-coach-brain/tests/test_core/test_methodology.py` (создан)
- `gym-coach-brain/src/gym_coach_brain/core/puos.py` (изменён — Story 4.2 residue)
- `gym-coach-brain/tests/test_core/test_puos.py` (изменён — Story 4.2 residue)
- `gym-coach-brain/src/gym_coach_brain/core/science.py` (изменён)
- `gym-coach-brain/src/gym_coach_brain/data/models.py` (изменён)

### Change Log

- 2026-03-08: Story 4.4 implemented — methodology selector module with 18 tests, 251 total passed.
- 2026-03-08: [AI-Review Fix] Refactored `select_methodology` to use mapping dict for better maintainability.
- 2026-03-08: [AI-Review Fix] Parametrized config-binding tests to verify all methodologies (strength, hypertrophy, endurance).
- 2026-03-08: [AI-Review Fix] Synchronized File List with actual git repository state.
