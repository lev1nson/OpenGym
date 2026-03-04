# Requirements Inventory

## Functional Requirements

FR1: Система выполняет инкрементальный Fine-tuning локальной модели (threshold-triggered, default N=5 завершённых сессий).
FR2: Система прогнозирует индивидуальный RPE с расчетом Confidence Score (MC Dropout).
FR3: Система выполняет автоматическую оптимизацию памяти VPS (Memory Management) после циклов обучения.
FR4: Система версионирует веса нейросети и выполняет Diff-анализ точности (model_v*.pt + сравнение с базовыми формулами).
FR5: Система рассчитывает план тренировки на основе SMH-метаданных и истории атлета (APRE + Double Progression).
FR6: Система блокирует превышение лимита PUOS (11 сетов на группу) — raises ScienceLimitError.
FR7: Система автоматически откатывается к Double Progression при низком Confidence Score ИИ (confidence < 0.6).
FR8: Система предоставляет обоснование изменений веса со ссылками на ScienceEvidence.md (Recap + Summary протокол).
FR9: Атлет проходит интерактивный онбординг (Closed-loop questions).
FR10: Система поддерживает профили оборудования (Gym Environment JSON, user_profile table).
FR11: Система выполняет асинхронный JSON-обмен данными с OpenClaw {intent, argv, stdout, exit_code}.
FR12: Система генерирует историческую аналитику фракционного объема нагрузки (1.0 агонист / 0.5 синергист).
FR13: Каждый ответ онбординга мапится на конкретные числовые коэффициенты в БД (возраст → коэффициент объема, опыт → шаг прогрессии).
FR14: Логика адаптации (APRE, Double Progression) строится на программных алгоритмах, исключающих свободную интерпретацию параметров со стороны LLM.
FR15: Перед началом тренировки система обязана выдать Recap: сравнение с прошлой сессией и план на сегодня.
FR16: В конце тренировки система обязана выдать Summary: оценку выполнения плана и прогноз восстановления.
FR17: Система учитывает образ жизни (lifestyle) пользователя через коэффициенты восстановления (сна, стресса), вносимые через readiness-лог.

## NonFunctional Requirements

NFR1: Performance — отсутствие жесткого лимита времени на ответ; приоритет точности расчетов; асинхронное выполнение тяжелых ML-операций.
NFR2: Scalability — базовая работа на 16 ГБ RAM с архитектурной поддержкой масштабирования до 32 ГБ.
NFR3: Reliability — атомарность записей в SQLite (транзакции); обязательный бэкап весов модели перед дообучением.
NFR4: Privacy — Zero Cloud Leak; все вычисления и хранение данных строго локально на VPS атлета.

## Additional Requirements

- **ScienceEvidence.md — Research & Development (BLOCKER — Отдельный Эпик)**: Файл `workspace/skills/gym-coach/ScienceEvidence.md` является пустым плейсхолдером. Требует отдельного эпика до начала разработки: (1) AI-агент проводит ресёрч спортивной науки (APRE, Double Progression, PUOS, фракционный объём 1.0/0.5, коэффициенты восстановления, SMH stretch_mediated флаги) используя научные источники + web research; (2) проектирует YAML-схему (version, puos.max_sets_per_group, progression.step_kg, recovery коэффициенты, exercise SMH-метаданные); (3) заполняет файл конкретными числовыми значениями + научными обоснованиями в markdown. Результат: production-ready ScienceEvidence.md, который разблокирует реализацию `core/science.py` и всей цепочки ScienceConfig.
- **Starter Template**: `uv init --package gym-coach-brain` (src layout) — первая история реализации. Инициализация: `uv add sqlalchemy alembic "pydantic[yaml]" loguru torch` + `uv add --dev pytest pytest-cov`
- **Migration Strategy (ADR-003)**: Brownfield модульная переработка. Внешний JSON-контракт с OpenClaw {intent, argv, stdout, exit_code} — invariant на всё время миграции. Порядок: зафиксировать поведение → Alembic init → переписать модули → заменять постепенно → удалить gym_coach.py
- **ML Layer Isolation (ADR-001)**: ML Worker — изолированный процесс (multiprocessing + systemd MemoryLimit=8G); падение PyTorch не роняет основное ядро
- **ScienceConfig Loading (ADR-002)**: parse-at-startup → ScienceConfig (Pydantic) с version field; O(1) доступ в runtime
- **Schema Evolution**: Alembic init на существующей схеме БД как первый шаг — данные мигрируют, не теряются
- **ScienceEvidence.md YAML schema**: определить skeleton (version, puos, progression секции) до реализации core/science.py
- **DB path конфигурация**: DATABASE_URL env var с дефолтом `sqlite:///gym_coach.sqlite`
- **Model backup strategy**: model_v{n}.pt → model_v{n}.backup.pt в той же директории (atomic) перед fine-tuning
- **CI**: GitHub Actions для тестов (pytest) при push/PR
- **Two systemd services**: gym-coach-brain.service (main API) + gym-coach-brain-ml.service (ML Worker daemon)
- **Contract tests**: зафиксировать поведение gym_coach.py через pytest перед началом миграции
- **Dependency direction**: api → adaptation → core → data (data не импортирует выше); только absolute imports
- **Threshold-triggered fine-tuning**: threshold-based (N=5 default, configurable), не after-every-session

## Architectural Decisions (Party Mode)

- **Greenfield approach**: gym_coach.py и gym_coach.sqlite удаляются в Epic 3. Никакой migration. Никакого переноса данных.
- **ScienceEvidence.md как источник формул**: Epic 4 не содержит алгоритмов из gym_coach.py — все формулы (APRE, Double Progression, PUOS, чередование, восстановление) берутся исключительно из ScienceEvidence.md, разработанного в Epic 1.
- **Epic 4 заблокирован Epic 1**: работа над детерминированным ядром не начинается до завершения ScienceEvidence.md.
- **Epic 3 и Epic 4 независимы**: могут разрабатываться параллельно после завершения Epic 1 и Epic 2.
- **Dual-gate система прогрессии**: методики в ScienceEvidence.md имеют `gate: hard` (абсолютные минимумы безопасности/техники) и `gate: soft` (ML + статистика определяют готовность). Soft gates могут разблокироваться раньше при исключительном прогрессе атлета.
- **Knowledge Base foundation**: таксономия мышц, библиотека упражнений и каталог оборудования — мастер-данные, необходимые для корректной работы PUOS (фракционный объём 1.0/0.5) и ML feature engineering. Реализуются в Epic 2 до начала разработки ядра.
- **Методологии — pluggable**: APRE и Double Progression — фундаментальные алгоритмы (всегда присутствуют в коде); тренировочные методологии (гипертрофия/сила/выносливость) — подключаемые, описаны в ScienceEvidence.md секции `methodologies`.

## FR Coverage Map

| FR | Эпик |
|---|---|
| FR1: threshold-triggered fine-tuning | Epic 5 — AI-персонализация |
| FR2: RPE prediction + Confidence Score | Epic 5 — AI-персонализация |
| FR3: memory management (systemd MemoryLimit) | Epic 5 — AI-персонализация |
| FR4: model versioning + Diff-анализ | Epic 5 — AI-персонализация |
| FR5: training plan (APRE/Double Progression) | Epic 4 — Детерминированное ядро |
| FR6: PUOS blocking (ScienceLimitError) | Epic 4 — Детерминированное ядро |
| FR7: Confidence-Based Fallback (< 0.6) | Epic 5 — AI-персонализация |
| FR8: justification + Recap/Summary protocol | Epic 4 — Детерминированное ядро |
| FR9: interactive onboarding (closed-loop) | Epic 3 — Основа и профиль |
| FR10: equipment profiles (Gym Environment JSON) | Epic 3 — Основа и профиль |
| FR11: async JSON API для OpenClaw | Epic 6 — Интеграция и деплой |
| FR12: fractional volume analytics | Epic 6 — Интеграция и деплой |
| FR13: onboarding answers → DB coefficients | Epic 3 — Основа и профиль |
| FR14: deterministic algorithms (no LLM interpretation) | Epic 3 — Основа и профиль |
| FR15: pre-workout Recap (обязательный) | Epic 4 — Детерминированное ядро |
| FR16: post-workout Summary (обязательный) | Epic 4 — Детерминированное ядро |
| FR17: lifestyle coefficients (readiness log) | Epic 4 — Детерминированное ядро |
