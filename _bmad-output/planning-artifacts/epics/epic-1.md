# Epic 1: Научная методология

Разработать production-ready ScienceEvidence.md — полноценную методологическую базу данных с научно обоснованными формулами, коэффициентами и прогрессивной системой методик для всех уровней атлетов.

**Блокирует:** Epic 2, Epic 3, Epic 4
**Пререквизит для:** FR1-FR8, FR12-FR14

## Story 1.1: Ресёрч спортивной науки

As a dev agent,
I want to run the domain-research workflow on sports science topics,
So that I have verified numerical coefficients and principles for ScienceEvidence.md.

**Acceptance Criteria:**

**Given** domain-research workflow доступен и web search работает
**When** агент вызывает `Skill("bmad-domain-research")` с темой "APRE, Double Progression, PUOS, фракционный объём (1.0/0.5), SMH stretch_mediated, коэффициенты восстановления (сон, стресс, HRV), тренировочные методологии (гипертрофия, сила, выносливость), минимальный отдых между тренировками одной группы мышц (min_rest_days)"
**Then** research report сохранён в `_bmad-output/planning-artifacts/research/` (имя файла генерируется workflow автоматически; фактический файл: `domain-sports-science-research-2026-03-04.md`)
**And** документ содержит числовые значения для каждой темы с источниками/обоснованиями
**And** все 7 тематических областей покрыты (APRE, DP, PUOS, fractional volume, SMH, recovery, methodologies)
**And** для каждой методологии определены: диапазон повторений, тип прогрессии, рекомендуемая частота тренировок
**And** все источники являются peer-reviewed публикациями или работами признанных S&C исследователей (Schoenfeld, Helms, Israetel, Baraki, Zourdos) — общие сайты, форумы и YouTube-контент не принимаются
**And** для каждого числового коэффициента указана ссылка на конкретный источник (автор, год, или DOI)

## Story 1.2: Проектирование YAML-схемы ScienceEvidence.md

As a dev agent,
I want to design the YAML frontmatter schema for ScienceEvidence.md,
So that core/science.py has a typed Pydantic model to parse at startup.

**Acceptance Criteria:**

**Given** research report из Story 1.1 и Architecture.md доступны
**When** агент запускает technical-research workflow с темой "YAML schema design for Pydantic ScienceConfig"
**Then** skeleton `ScienceEvidence.md` создан в project root с YAML-frontmatter
**And** frontmatter содержит секции: `version`, `puos`, `progression`, `recovery`, `exercises`, `methodologies`, `planning` (включает `min_rest_days_per_muscle_group: int` — минимальное количество дней отдыха между тренировками одной группы мышц)
**And** секция `puos` включает поле `smh_volume_multiplier: float` — множитель лимита объёма для stretch-mediated упражнений (научное обоснование: Israetel; типичное значение 1.2–1.3); значение определяется ресёрчем из Story 1.1
**And** каждое поле имеет тип и placeholder-значение (e.g. `max_sets_per_group: 0`)
**And** markdown body содержит заголовки секций для научных обоснований (пока пустые)
**And** файл парсируется базовым Pydantic-классом без ошибок
**And** `core/science.py` НЕ создаётся в этой истории — только файл схемы

## Story 1.3: Наполнение ScienceEvidence.md

As a dev agent,
I want to fill ScienceEvidence.md with research data and scientific justifications,
So that ScienceConfig loads production-ready coefficients at runtime.

**Acceptance Criteria:**

**Given** skeleton из Story 1.2 и research report из Story 1.1 доступны
**When** агент заполняет все поля YAML-frontmatter числовыми значениями из ресёрча
**Then** каждое числовое поле содержит реальное значение (не 0 и не placeholder)
**And** markdown body содержит научное обоснование для каждой секции
**And** `python -c "from gym_coach_brain.core.science import load_science_config; cfg = load_science_config(); assert cfg.puos.max_sets_per_group > 0"` выполняется без ошибок (конкретное значение определяется ресёрчем из Story 1.1 и фиксируется в ScienceEvidence.md до написания теста)
**And** `cfg.version` содержит непустую строку (e.g. `"1.0.0"`)
**And** `cfg.planning.min_rest_days_per_muscle_group` содержит числовое значение (научно обоснованное, типично 48–72 часа = 2–3 дня)

## Story 1.2.5: Реализация `core/science.py` и Pydantic ScienceConfig

As a dev agent,
I want to implement `core/science.py` with a Pydantic ScienceConfig model,
So that Story 1.3 can load and validate ScienceEvidence.md at runtime.

**Acceptance Criteria:**

**Given** skeleton `ScienceEvidence.md` создан (Story 1.2) с YAML-frontmatter
**When** агент реализует `gym_coach_brain/core/science.py`
**Then** файл содержит Pydantic-модели для всех секций frontmatter: `PUOSConfig`, `ProgressionConfig`, `RecoveryConfig`, `PlanningConfig`, `ScienceConfig` (корневая)
**And** функция `load_science_config() -> ScienceConfig` читает YAML-frontmatter из `ScienceEvidence.md` и возвращает валидированный объект
**And** `python -c "from gym_coach_brain.core.science import load_science_config"` выполняется без ошибок
**And** `pytest tests/test_core/test_science.py` проходит: модель парсит skeleton с placeholder-значениями без ValidationError

## ⚠️ Note: Версионирование коэффициентов

Поле `version` в ScienceEvidence.md фиксирует версию коэффициентов. При обновлении значений старые тренировки пересчитывать не нужно (допустимо для MVP). Однако каждая `WorkoutSession` в БД должна логировать `science_version` (строку из `ScienceConfig.version`) — для будущей трассировки какие коэффициенты применялись. Это требование к Story 3.2 (data models): добавить поле `science_version: str` в модель `WorkoutSession`.

---
