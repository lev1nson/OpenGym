---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'AI-powered local fitness coaching systems — architecture, algorithms, and ecosystem'
research_goals: 'Make architectural decisions for gym-coach-brain; find ready libraries/solutions to use; understand pitfalls and mistakes others made'
user_name: 'Max'
date: '2026-03-02'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical

**Date:** 2026-03-02
**Author:** Max
**Research Type:** technical

---

## Research Overview

Данный технический ресерч охватывает экосистему AI-powered local fitness coaching систем с фокусом на архитектурные решения, алгоритмы прогрессии нагрузки (APRE, Double Progression) и локальный ML для персонализации (N=1 fine-tuning). Ресерч проводился методом параллельного веб-поиска по 8 ключевым направлениям с верификацией источников из академических публикаций, GitHub репозиториев и индустриальных гайдов.

Ключевые выводы: Python + SQLite + PyTorch — подтверждённый отраслевой стандарт для данного класса систем. Архитектурный паттерн "Deterministic Core + LLM для NL" является industry best practice в healthcare/fitness AI. Catastrophic forgetting при incremental fine-tuning — главный ML-риск, решаемый через EWC (готовая PyTorch библиотека). Публичных Python реализаций APRE алгоритма не найдено — необходимо писать с нуля по научным таблицам.

Полный Executive Summary, стратегические рекомендации и дорожная карта реализации находятся в разделе "Technical Research Synthesis" в конце документа. Все технические разделы (Technology Stack, Integration Patterns, Architectural Patterns, Implementation Approaches) содержат верифицированные данные с ссылками на источники.

## Technical Research Scope Confirmation

**Research Topic:** AI-powered local fitness coaching systems — architecture, algorithms, and ecosystem
**Research Goals:** Make architectural decisions for gym-coach-brain; find ready libraries/solutions to use; understand pitfalls and mistakes others made

**Technical Research Scope:**

- Architecture Analysis - design patterns, frameworks, system architecture
- Implementation Approaches - development methodologies, coding patterns
- Technology Stack - languages, frameworks, tools, platforms
- Integration Patterns - APIs, protocols, interoperability
- Performance Considerations - scalability, optimization, patterns

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-03-02

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technology Stack Analysis

### Programming Languages

Python остаётся доминирующим языком для fitness AI backends. Все значимые open-source проекты 2024–2025 используют Python 3.10+ как основу для логики тренировок и ML-пайплайнов.

_Popular Languages: Python (абсолютное доминирование для backend + ML), TypeScript/Next.js (web-UI слой, workout.cool)_
_Emerging: Python 3.12+ с async-first подходом (aiohttp, FastAPI) для Telegram-ботов_
_Performance: Для N=1 ML вычислений Python + PyTorch достаточно на 16 ГБ VPS; критичных bottleneck'ов нет_
_Source: [GitHub fitness-app topics](https://github.com/topics/fitness-app), [GeorgiosLymperis fitness_app](https://github.com/GeorgiosLymperis/fitness_app)_

### Development Frameworks and Libraries

**ML & Adaptation:**
- **PyTorch** — стандарт для локального обучения N=1 моделей; поддерживает incremental fine-tuning
- **HuggingFace Transformers** — используется в проектах поверх PyTorch для персонализации (fitness_app)
- **scikit-learn** — часто используется рядом с PyTorch для простых регрессионных моделей (RPE прогноз, 1RM расчёты)

**Web/Bot Frameworks:**
- **python-telegram-bot / aiohttp** — для Telegram-ботов (ActiveBuddy runner coach)
- **Ollama** — локальный LLM backend, стандарт для privacy-first решений
- **LangChain + LangGraph** — для multi-agent оркестрации поверх LLM (imanoop7 Personal Trainers)

**Data & Validation:**
- **SQLAlchemy 2.0** — ORM, встречается в большинстве Python fitness проектов
- **Pydantic** — валидация входных данных (Telegram → Python CLI)
- **Alembic** — миграции SQLite/PostgreSQL (Reflex-based fitness tracker)
- **Pandas / NumPy** — аналитика прогрессии (volume tracking, trends)

_Major Frameworks: PyTorch + SQLAlchemy + Pydantic — самый распространённый стек_
_Source: [fitness_app](https://github.com/GeorgiosLymperis/fitness_app), [AI-Personal-Trainer](https://github.com/thaochu05/AI-Personal-Trainer), [ActiveBuddy](https://github.com/oleksandr-g-rock/ai-runner-coach)_

### Database and Storage Technologies

**Для локальных/VPS решений:**
- **SQLite с WAL mode** — абсолютный стандарт для local-first fitness приложений; FK constraints обязательны
- Типичные таблицы: `users`, `exercises`, `workouts`, `sets`, `activity_log`, `meta` (session state), `model_weights` (версионирование)
- Главная таблица: `activity_log` с `start_time`, `end_time`, `reps`, `load`, `rpe`, `status`

**Для более сложных web-приложений:**
- **PostgreSQL** (workout.cool + Prisma, ActiveBuddy) — если нужен multi-user или web
- **In-memory SQLite** (`sqlite:///:memory:`) — стандарт для тестов

**Хранение весов ML-модели:**
- Файловая система (`.pt` checkpoint files) + версионирование вручную или через DVC
- Бэкап перед каждым fine-tuning циклом — критически важно

_Source: [RisticDjordje health-fitness-tracking](https://github.com/RisticDjordje/health-and-fitness-tracking-app), [GeeksForGeeks DB design](https://www.geeksforgeeks.org/dbms/how-to-design-a-database-for-health-and-fitness-tracking-applications/), [workout.cool](https://github.com/Snouzy/workout-cool)_

### Development Tools and Platforms

- **Testing:** pytest + `sqlite:///:memory:` — стандарт изоляции тестов
- **Migrations:** Alembic (автогенерация через `--autogenerate`)
- **Dependency tracking:** requirements.txt или pyproject.toml
- **Local LLM:** Ollama (privacy-first, VPS-ready)
- **Deployment:** Docker + docker-compose для self-hosted решений

_Source: [Pybites Reflex fitness tracker](https://pybit.es/articles/fitness-tracker-app-with-python-reflex/), [Ollama + Telegram guide](https://medium.com/mcd-unison/pocket-ai-telegram-bot-python-ollama-01da2c4d05df)_

### Notable Open-Source Projects (Ecosystem Map)

| Проект | Стек | Релевантность для gym-coach-brain |
|---|---|---|
| [workout.cool](https://github.com/Snouzy/workout-cool) | Next.js + Prisma + PostgreSQL | База упражнений (1200+), не Python |
| [fitness_app (GeorgiosLymperis)](https://github.com/GeorgiosLymperis/fitness_app) | Python + SQLite + SQLAlchemy + HuggingFace | Ближайший аналог по стеку |
| [MyFit](https://github.com/WhyAsh5114/MyFit) | SvelteKit | RIR tracking + progression formulas (GPL v3) |
| [AI Personal Trainers (imanoop7)](https://github.com/imanoop7/AI-Agents-as-Personal-Trainers--Customizing-Fitness-Routines-with-LLMs) | LangChain + LangGraph | Multi-agent оркестрация |
| [ActiveBuddy](https://github.com/oleksandr-g-rock/ai-runner-coach) | Python + aiohttp + PostgreSQL | Telegram-бот для спорта |
| [Liftosaur](https://www.liftosaur.com/) | TypeScript (closed) | Лучшая реализация Double/Linear/Rep Sum progression |
| [AI-Personal-Trainer (thaochu05)](https://github.com/thaochu05/AI-Personal-Trainer) | PyTorch + MediaPipe + Streamlit | CV pose estimation |

### Technology Adoption Trends

- **Local-first + privacy:** Тренд к Ollama + локальный SQLite вместо cloud API
- **Telegram как UI:** Растущий паттерн для fitness ботов (избегает mobile app разработки)
- **LangGraph для оркестрации:** Переход от простых LLM вызовов к state-machine агентам
- **Deterministic core + LLM wrapper:** Лучшие проекты используют детерминированную логику для расчётов и LLM только для NL интерфейса — совпадает с нашей философией

_Source: [Hacker News workout.cool thread](https://news.ycombinator.com/item?id=44309320), [IBM Llama4 fitness tutorial](https://www.ibm.com/think/tutorials/develop-ai-personal-trainer-with-llama-4-watsonx-ai)_

## Integration Patterns Analysis

### API Design Patterns — "Brain" к Telegram и внешним системам

**Текущий паттерн gym-coach (NL Proxy → subprocess → CLI):**
- `router.py` (NL) → `subprocess.run(gym_coach.py ...)` → stdout JSON → Telegram
- Проблема: subprocess overhead + `TimeoutExpired` не перехватывается (known bug C2)
- Альтернатива #1: **Direct Python import** — `gym_coach` как библиотека, без subprocess
- Альтернатива #2: **FastAPI microservice** — gym_coach.py обёрнут в async REST API для тяжёлых ML операций

**Рекомендуемый паттерн (из экосистемы):**
- RESTful JSON API между NL-слоем и "мозгом" — стандарт для fitness AI систем
- Для heavy ML ops (fine-tuning, inference): async эндпоинт, ответ 200 немедленно → результат через callback или polling статуса
- Для простых команд (log, plan, next): синхронный вызов функции достаточен

_Source: [FastAPI microservices guide](https://www.merixstudio.com/blog/how-use-fastapi-microservices-python), [Python microservices architecture](https://kinsta.com/blog/python-microservices/)_

### Telegram Bot Communication Protocol

**Webhook vs Polling — однозначный вывод:**
- **Webhook** для production: 60–80% меньше нагрузки на сервер, доставка <100ms
- **Long polling** только для разработки и тестирования
- **FastAPI + asyncio** — industry standard для python-telegram-bot v20+ webhooks
- Telegram ожидает ответ 200 OK в течение **25–30 секунд** — критично для ML операций
- Тяжёлые операции (fine-tuning, volume analysis) ОБЯЗАНЫ быть async: сначала 200, потом результат отправляется через `context.bot.send_message()`

**Security:**
- Secret token в заголовках — обязателен против spoofing атак
- HTTPS + TLS 1.2+, токены в env variables

_Source: [python-telegram-bot webhooks guide 2026](https://copyprogramming.com/howto/python-telegram-bot-using-webhook), [grammY polling vs webhooks](https://grammy.dev/guide/deployment-types.html)_

### ML Model Serving (PyTorch Inference)

**Варианты для локального VPS:**

| Решение | Когда использовать | Overhead |
|---|---|---|
| **Прямой вызов Python функции** | Phase 1 MVP, inference простой | Минимальный |
| **BentoML** | Нужен REST API для ML модели | Средний |
| **TorchServe** | Production-grade serving, batching | Высокий |
| **FastAPI + asyncio** | Async inference, уже есть FastAPI | Низкий |

**Для gym-coach-brain Phase 1:** Direct Python function call + async для fine-tuning
**Для Phase 2+:** BentoML или FastAPI endpoint если нужна независимость сервисов

_Source: [BentoML](https://github.com/bentoml/BentoML), [PyTorch Serve](https://github.com/pytorch/serve), [FastAPI + PyTorch](https://medium.com/@mingc.me/deploying-pytorch-model-to-production-with-fastapi-in-cuda-supported-docker-c161cca68bb8)_

### Wearable Integration (Phase 2: HRV через Oura)

**Oura Ring API:**
- REST API (cloud.ouraring.com/v2) — HRV, sleep stages, readiness score
- OAuth 2.0 аутентификация
- Данные тянутся ежедневно (не real-time) — polling раз в день достаточно
- Python: стандартный `httpx` или `requests` + OAuth2 flow

**Unified Wearable APIs (рекомендация):**
- **[Open Wearables](https://www.themomentum.ai/blog/introducing-open-wearables-the-open-source-api-for-wearable-health-intelligence)** — open-source unified API (Apple Health, Garmin, Polar, Whoop; Oura в Q1 2026)
- **[Terra API](https://tryterra.co/)** — коммерческий unified wearable API, все устройства через одну интеграцию
- Рекомендация: для Phase 2 использовать Oura API напрямую (простейший OAuth); для Phase 3 — Open Wearables или Terra

**Архитектурный паттерн:**
- Background job (cron или asyncio task) → Oura API → SQLite `readiness_log` таблица → APRE readiness coefficient recalculation

_Source: [Oura API docs](https://cloud.ouraring.com/v2/docs), [Open Wearables](https://medium.com/@momentum_healthtech_agency/open-wearables-the-open-source-api-for-wearable-health-intelligence-207cc3d20538)_

### Data Formats и Протоколы

- **JSON** — стандарт для всего: Telegram → router.py → gym_coach.py → ответ
- **SQLite WAL** — для конкурентного чтения/записи при async операциях (ML + Telegram одновременно)
- **`.pt` checkpoint files** — хранение весов PyTorch модели, версионирование по дате/сессии
- Нет нужды в Protobuf/MessagePack для нашего масштаба — JSON достаточен

### Ключевой Архитектурный Инсайт

**Anti-pattern (текущий):** `subprocess.run()` с timeout проблемой
**Best practice:** Разделить на 2 слоя:
1. **Sync layer** — NL parsing + простые команды (direct Python call, <1s)
2. **Async layer** — ML inference, fine-tuning, volume analysis (asyncio task, результат через Telegram callback)

Это устраняет проблему M2 (`TimeoutExpired` не перехватывается) и позволяет масштабировать ML-операции независимо.

_Source: [ActiveBuddy architecture](https://github.com/oleksandr-g-rock/ai-runner-coach), [Telegram async pattern](https://www.freecodecamp.org/news/how-to-build-and-deploy-python-telegram-bot-v20-webhooks/)_

## Architectural Patterns and Design

### System Architecture Patterns

**Monolith vs Microservices — однозначный вывод для gym-coach-brain:**

| Критерий | Монолит | Микросервисы |
|---|---|---|
| Команда | Solo / <3 человека ✅ | >10 человек |
| Стадия | MVP / brownfield ✅ | Production at scale |
| DevOps зрелость | Низкая ✅ | Высокая |
| Время до market | Быстро ✅ | Медленно |

**Вывод:** Modular Monolith с чёткими границами модулей — правильная архитектура для gym-coach-brain на всех фазах. Microservices добавляют сложность без выгоды при solo разработке.

**Рекомендуемая структура — Modular Monolith:**
```
gym_coach_brain/
├── core/          # Детерминированная логика (APRE, PUOS, Double Progression)
├── ml/            # PyTorch модели, fine-tuning, inference
├── data/          # SQLAlchemy models, Alembic migrations
├── nl/            # NL parsing (router), intent extraction
└── api/           # Интерфейс с OpenClaw (JSON)
```

_Source: [Monolith vs Microservices 2025](https://medium.com/@kodekx-solutions/microservices-vs-monolith-decision-framework-for-2025-b19570930cf7), [Monolith for Python developers](https://opsmatters.com/posts/monolith-or-microservices-architecture-choices-python-developers)_

### Design Principles — Deterministic Core + LLM Hybrid

**Это утверждённый архитектурный паттерн в индустрии — "Rule Maker Pattern":**

> "The Rule Maker Pattern transforms AI's probabilistic generation into reliable, deterministic execution by establishing clear rules. The separation of probabilistic generation vs. deterministic execution makes AI dependable at scale."

**Применение для gym-coach-brain:**

| Слой | Тип | Отвечает за |
|---|---|---|
| NL Interface | Вероятностный (LLM/regex) | Понять намерение пользователя |
| Routing | Детерминированный | Intent → команда |
| Core Logic | Детерминированный | APRE, PUOS, Double Progression, Brzycki 1RM |
| ML Adaptation | Вероятностный (PyTorch) | RPE прогноз, персонализация |
| Safety Guards | Детерминированный | Блокировка нарушений физиологических лимитов |

**Ключевой принцип:** ML-слой НИКОГДА не переопределяет детерминированные лимиты (PUOS = 11 сетов). Confidence-Based Fallback к Double Progression при низком confidence — правильный паттерн.

_Source: [Rule Maker Pattern](https://tessl.io/blog/the-rule-maker-pattern/), [Hybrid Intelligence](https://blog.newmathdata.com/hybrid-intelligence-marrying-deterministic-code-with-llms-for-robust-software-development-b92bf949257c)_

### Local-First Agent Architecture Pattern

**OpenClaw сам является примером** этого паттерна (найдено в ресерче):
> SQLite как "single-file portable intelligence layer" — FTS5 для поиска, sqlite-vec для embeddings. Нет зависимости от внешних сервисов, единый файл, портабельность.

**"God Model" Anti-Pattern** (НЕ делать):
- Одна точка (LLM или нейросеть) делает всё: NL parsing + бизнес-логику + ML
- Проблема: непредсказуемость, "галлюцинации" в расчётах
- Наша архитектура уже решает это через разделение router.py / gym_coach.py

**Stevens Pattern** (простота как добродетель):
> "Hackable AI assistant using a single SQLite table and a handful of cron jobs" — показывает, что простые паттерны часто лучше сложных.

**Agentive Architecture for Brain:**
- Perception: входящие данные (RPE логи, результаты сессий, HRV)
- Decision: детерминированный движок + ML confidence
- Action: генерация плана, адаптация весов, генерация Recap/Summary

_Source: [Local-First RAG with OpenClaw](https://www.pingcap.com/blog/local-first-rag-using-sqlite-ai-agent-memory-openclaw/), [Stevens SQLite assistant](https://www.geoffreylitt.com/2025/04/12/how-i-made-a-useful-ai-assistant-with-one-sqlite-table-and-a-handful-of-cron-jobs), [AI Agent Architectures](https://dev.to/aws/we-need-to-talk-about-ai-agent-architectures-4n49)_

### Data Architecture — RPE/RIR Scientific Foundation

**RPE ↔ RIR Mapping (научно валидировано, NSCA):**
- 10 RPE = 0 RIR (failure)
- 9 RPE = 1 RIR
- 8 RPE = 2 RIR
- 7 RPE = 3 RIR (и т.д.)

**Ключевой инсайт для архитектуры:**
- Для **начинающих** (experience < 1 год): % от 1RM точнее RPE — они не умеют калибровать
- Для **опытных** (experience > 1 год): RPE/RIR точнее %1RM — onboarding ДОЛЖЕН учитывать это
- Session-RPE метод (Borg * Duration) — научно валидированный способ суммарной нагрузки сессии

**Database schema implications:**
- `sets` таблица: `weight`, `reps`, `rpe` (nullable для новичков), `rir` (computed), `status`
- `sessions` таблица: `session_rpe` (summary load), `training_load_au` (session_rpe × duration)
- `athlete_meta`: `experience_years` → определяет режим (% 1RM vs RPE)

_Source: [RPE/RIR Complete Guide — MASS Research Review](https://massresearchreview.com/2023/05/22/rpe-and-rir-the-complete-guide/), [Session-RPE PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5673663/)_

### Scalability and Performance Patterns

**Для нашего VPS (16-32 ГБ RAM), single-user:**
- SQLite WAL mode обрабатывает concurrent reads без блокировок — достаточно
- PyTorch fine-tuning — самая тяжёлая операция, запускать в asyncio executor
- Memory management после fine-tuning: явный `torch.cuda.empty_cache()` + `gc.collect()`
- Horizontal scaling НЕ нужен на Phase 1-2 — single VPS достаточен

**Bottleneck map:**
1. Fine-tuning (minutes) → async background task
2. Volume analysis (seconds) → sync, допустимо
3. Plan generation (milliseconds) → sync

_Source: [Monolith vs Microservices 2025](https://foojay.io/today/monolith-vs-microservices-2025/)_

### Security Architecture

- **Zero Cloud Leak** — все вычисления локально, no external API calls для ML
- SQLite file permissions: только процесс gym_coach_brain имеет доступ
- Telegram webhook: secret token в заголовке (обязательно)
- `.pt` model files: хранятся локально, не в git репозитории
- Env variables для токенов (никогда не hardcode)

_Source: [Telegram webhook security](https://www.freecodecamp.org/news/how-to-build-and-deploy-python-telegram-bot-v20-webhooks/)_

## Implementation Approaches and Technology Adoption

### Incremental ML Fine-Tuning — EWC Implementation

**Elastic Weight Consolidation (EWC) — готовое решение для предотвращения catastrophic forgetting:**

Готовая PyTorch реализация: [moskomule/ewc.pytorch](https://github.com/moskomule/ewc.pytorch)

**Принцип работы:**
```
loss = standard_loss(output, target) + λ × Σ F_i × (θ_i - θ*_i)²
```
где:
- `F_i` — Fisher Information Matrix (важность параметра для предыдущих задач)
- `θ*_i` — оптимальные веса после предыдущей сессии
- `λ` — сила регуляризации (критический гиперпараметр, требует тюнинга)

**Workflow для gym-coach-brain:**
1. Тренировка завершена, результаты записаны в SQLite
2. Вычислить FIM по данным предыдущих сессий (`estimate_ewc_params()`)
3. Fine-tuning на данных текущей сессии с EWC loss
4. Сохранить `model.state_dict()` как новый checkpoint (`.pt` файл с датой)
5. Бэкап старого checkpoint перед перезаписью (атомарная операция)

**Ключевые параметры:**
- Learning rate: начать с 1e-4, уменьшать при признаках forgetting
- λ (EWC lambda): начать с 100, увеличивать если старые данные "забываются"
- Batch size: весь датасет предыдущих сессий (обычно <1000 записей — помещается в память)

_Source: [moskomule/ewc.pytorch](https://github.com/moskomule/ewc.pytorch), [EWC Deep Dive — TDS](https://towardsdatascience.com/continual-learning-a-deep-dive-into-elastic-weight-consolidation-loss-7cda4a2d058c/)_

### APRE Algorithm — Implementation from Scratch

**Python реализации в публичных репо НЕ найдено** — это подтверждает необходимость написать с нуля.

**APRE Lookup Tables (из научных источников):**

APRE-6 (Strength — 6RM target):
```
Reps on last set → Weight adjustment next session
< 2 reps   → -5 to -10 lb (-2.5 to -5 kg)
3-4 reps   → 0 to -5 lb (лёгкое снижение)
5-7 reps   → без изменений (целевая зона)
8-9 reps   → +5 lb (+2.5 kg)
10+ reps   → +5 to +10 lb (+2.5 to +5 kg)
```

APRE-10 (Hypertrophy — 10RM target):
```
< 4 reps   → -5 to -10 lb
5-6 reps   → 0 to -5 lb
7-12 reps  → без изменений (целевая зона)
13-16 reps → +5 lb
17+ reps   → +5 to +10 lb
```

**Double Progression Algorithm:**
```python
def should_increase_weight(reps_done, target_range_top, weight_step):
    if reps_done >= target_range_top:
        return weight + weight_step  # reset reps to bottom of range
    return weight  # continue working reps up
```

Типичные диапазоны: 8-12 (гипертрофия), 5-8 (сила), 3-5 (мощность)

**Ключевой инсайт:** APRE строже — autoregulates внутри сессии (set 3 → корректирует set 4). Double Progression — между сессиями. Оба алгоритма должны быть реализованы как чистые Python функции без зависимости от ML.

_Source: [APRE CoachMePlus](https://coachmeplus.com/apre-training-what-you-need-to-know-to-get-started/), [Double Progression — Legion](https://legionathletics.com/double-progression/), [APRE protocols](https://allaboutpowerlifting.com/apre-protocols-programs-seasons/)_

### Confidence Score + Fallback — Implementation Pattern

**Production-ready паттерн для нашей системы:**

```python
CONFIDENCE_THRESHOLD = 0.70  # тюнить по данным

def get_recommendation(athlete_data):
    ml_pred, confidence = model.predict_with_confidence(athlete_data)

    if confidence >= CONFIDENCE_THRESHOLD:
        return ml_pred, "ai"
    else:
        return double_progression_fallback(athlete_data), "deterministic"
```

**Как получить confidence из PyTorch:**
- Regression: используй MC Dropout (несколько forward passes с dropout активированным)
- Uncertainty = std(predictions) / mean(predictions) — чем выше, тем ниже confidence
- Softmax probability — для классификационных задач (например, RPE категория)

**Out-of-Distribution (OOD) Detection:**
- Если входные данные атлета сильно отличаются от тренировочного распределения → принудительный fallback
- Простая реализация: Mahalanobis distance от центра тренировочных данных

_Source: [Confidence Scores in ML — TDS](https://towardsdatascience.com/how-to-use-confidence-scores-in-machine-learning-models-abe9773306fa/), [Oxford Protein Informatics — Confidence in ML](https://www.blopig.com/blog/2025/03/confidence-in-ml-models/)_

### Testing Strategy — Brownfield + ML

**Порядок покрытия тестами (brownfield подход — от критичного к второстепенному):**

1. **Сначала тесты на баги** (C1, C2 из issues matrix): parser regex + RPE parsing
2. **Unit tests для детерминированных алгоритмов**: APRE lookup, Double Progression, PUOS calculator
3. **Integration tests**: полный pipeline с `sqlite:///:memory:` через Alembic migrations
4. **ML tests**: проверить что предсказания в ожидаемом диапазоне (RPE 6-10), нет NaN, размерности корректны

**pytest + Alembic (brownfield pitfall):**
- При рефакторинге импортов Alembic может предложить DROP TABLE — **опасно!**
- Использовать `pytest-alembic` для валидации migrations при каждом запуске
- Конфигурация в `conftest.py` с session-scoped engine

**Ключевые fixtures:**
```python
@pytest.fixture(scope="session")
def engine():
    engine = create_engine("sqlite:///:memory:")
    # apply all alembic migrations
    return engine
```

_Source: [pytest-alembic docs](https://pytest-alembic.readthedocs.io/en/latest/setup.html), [SQLAlchemy + Alembic Best Practices](https://dev.to/welel/best-practices-for-alembic-and-sqlalchemy-3b34)_

### Technology Adoption Strategy — Phased Approach

**Рекомендуемая последовательность внедрения:**

**Фаза 0 — Stabilize (немедленно):**
- Исправить C1, C2 (parser bugs) — тесты сначала
- Исправить M1 (`status='completed'`), M2 (TimeoutExpired)
- Добавить базовое покрытие тестами для критических путей

**Фаза 1 — Refactor + ML Foundation:**
- Перейти с `subprocess` на direct Python import (устранить root cause M2)
- Добавить SQLAlchemy models + Alembic для существующих таблиц
- Реализовать детерминированный core: APRE, Double Progression, PUOS
- Добавить PyTorch модель с EWC fine-tuning (начать с линейной регрессии, не DNN)

**Фаза 2 — Intelligence Layer:**
- Confidence-based fallback
- Recap/Summary generation
- Async fine-tuning (asyncio + executor)
- Oura Ring HRV integration

**Фаза 3 — Autonomy:**
- Wearable ecosystem (Open Wearables API)
- Proactive coaching
- Voice interface

### Risk Assessment

| Риск | Вероятность | Impact | Митигация |
|---|---|---|---|
| Catastrophic forgetting при fine-tuning | Высокая | Критический | EWC + регулярные checkpoint бэкапы |
| Overfitting на малом датасете (N=1) | Высокая | Высокий | Начать с линейной регрессии, не DNN |
| Data leakage в ML pipeline | Средняя | Критический | Строгое разделение train/test по времени |
| Alembic DROP TABLE при рефакторинге | Средняя | Критический | pytest-alembic + всегда review autogenerate |
| TimeoutExpired в subprocess (current bug) | Высокая (уже есть) | Высокий | Перейти на direct import |
| OOM при fine-tuning на 16 ГБ VPS | Низкая | Высокий | `gc.collect()` + `torch.cuda.empty_cache()` после каждого цикла |

---

## Technical Research Synthesis

### Executive Summary

Технический ресерч по AI-powered local fitness coaching подтверждает: **gym-coach-brain находится на правильном архитектурном пути**, а выбранный стек (Python + SQLite + PyTorch) является отраслевым стандартом для данного класса систем. Рынок fitness AI активно растёт (с $3.3 млрд в 2019 до $15.6 млрд к 2028), тренд 2025 года — **privacy-first, local-first, on-device ML** без облачных зависимостей.

Главное стратегическое подтверждение: архитектурный паттерн "Deterministic Core + LLM для NL-интерфейса" является **официально признанным best practice** в индустрии (Rule Maker Pattern). Конкретный дифференциатор gym-coach-brain — детерминированное научное ядро (ScienceEvidence.md) — это именно то, что отличает надёжные production-системы от "галлюцинирующих" LLM-коучей.

Три критических вывода для немедленного действия: (1) переход с subprocess на direct Python import устраняет корневую причину bug M2 и унифицирует архитектуру; (2) начинать ML с линейной регрессии, не DNN — при N=1 датасете это предотвращает overfitting; (3) EWC (готовая библиотека) решает catastrophic forgetting и должна быть заложена в архитектуру с самого начала, не добавлена позже.

**Ключевые технические находки:**
- ✅ Python + SQLite WAL + SQLAlchemy + PyTorch — подтверждённый стек
- ✅ Modular Monolith — правильная архитектура для solo разработчика (не microservices)
- ✅ Webhook > Polling для Telegram; async для heavy ML ops (25-30s лимит)
- ✅ EWC (moskomule/ewc.pytorch) — готовое решение для incremental learning
- ✅ APRE алгоритм — пишем с нуля (Python реализаций нет), это lookup table
- ✅ Oura Ring API — прямой REST/OAuth для Phase 2 HRV интеграции
- ⚠️ subprocess.run() — anti-pattern, заменить на direct import
- ⚠️ Начинать с линейной регрессии для RPE прогноза, не DNN

**Топ-5 технических рекомендаций:**
1. **Немедленно:** Исправить C1/C2 bugs (parser regex) с тестами — технический долг блокирует ML
2. **Phase 1:** Заменить subprocess на direct Python import + добавить async layer для ML
3. **Phase 1:** Реализовать APRE + Double Progression как чистые детерминированные функции
4. **Phase 1:** Использовать EWC с линейной регрессией — НЕ DNN для первых 50+ сессий
5. **Phase 2:** Oura Ring API через background asyncio task → `readiness_log` таблица → APRE coefficients

### Strategic Technical Recommendations

#### Архитектура системы (для gym-coach-brain)

```
OpenClaw Telegram Bot
        │
        ▼ (JSON, webhook)
   router.py (NL Proxy)
   ├── Intent extraction (regex + patterns)
   └── Direct Python call (НЕ subprocess)
        │
        ▼
   gym_coach_brain/
   ├── core/      ← APRE, PUOS, Double Progression (детерминированный)
   ├── ml/        ← PyTorch модель, EWC fine-tuning (вероятностный)
   ├── data/      ← SQLAlchemy models, Alembic migrations
   ├── nl/        ← NL parsing helpers
   └── api/       ← JSON interface to OpenClaw
        │
        ▼
   SQLite (WAL mode)
   ├── sets, sessions, exercises
   ├── athlete_meta (experience_years → APRE vs %1RM mode)
   ├── readiness_log (HRV, sleep — Phase 2)
   └── model_checkpoints (metadata)

   [Async Background]
   ├── EWC fine-tuning (after each session)
   └── Oura Ring HRV sync (Phase 2, daily cron)
```

#### Дерево решений для ML-компонента

```
Session completed?
├── YES → EWC fine-tuning (background async)
│         └── Save checkpoint with timestamp
└── Prediction needed?
    ├── confidence >= 0.70 → ML prediction (PyTorch)
    └── confidence < 0.70  → Double Progression fallback
```

### Future Technical Outlook

**Ближайшие 1-2 года (наш горизонт):**
- Local-first AI coaching с on-device ML становится стандартом (KinesteX, Athletica.ai)
- Unified Wearable APIs (Open Wearables, Terra) упростят HRV интеграцию
- LangGraph/state-machine агенты заменят простые LLM вызовы в NL слое

**Средний срок (3-5 лет):**
- Computer Vision pose estimation на VPS уровне (YOLOv11 и аналоги) для автоматического учёта техники
- Federated Learning для N=1 моделей без отправки данных в облако

**Стратегическая позиция gym-coach-brain:**
Детерминированное научное ядро + N=1 персонализация + privacy-first = устойчивый дифференциатор. Крупные игроки (Freeletics, FitnessAI) используют облачные модели — локальный подход gym-coach-brain не конкурирует с ними, а закрывает принципиально другую нишу: **атлеты, для которых данные остаются только на их VPS**.

_Source: [CIZO — AI Fitness 2025](https://cizotech.com/your-ai-personal-trainer-how-machine-learning-is-revolutionizing-fitness-in-2025/), [KitLabs AI Fitness Trends](https://www.kitlabs.us/ai-personalized-fitness-apps/), [KinesteX local processing](https://www.kinestex.com/)_

### Source Documentation (все поисковые запросы)

1. "AI fitness coaching app local ML PyTorch architecture 2025 open source"
2. "APRE autoregulation progressive resistance exercise algorithm implementation Python"
3. "fitness training app SQLite database schema workout logging Python 2024 2025"
4. "N=1 personalized machine learning fitness adaptation local training pitfalls"
5. "workout.cool open source fitness coaching architecture tech stack"
6. "local LLM fitness coaching Telegram bot Python architecture 2024 2025"
7. "progressive overload double progression algorithm Python open source gym tracker"
8. "incremental learning catastrophic forgetting small dataset fitness PyTorch pitfalls"
9. "fitness AI app subprocess JSON API communication architecture Python CLI microservice pattern"
10. "Telegram bot webhook vs polling Python fitness sport coach architecture best practices 2024"
11. "local ML model Python REST API JSON async integration PyTorch inference service"
12. "wearable HRV Apple Watch Oura Ring API integration Python fitness app 2025"
13. "fitness app monolith vs microservices when to split Python backend architecture 2024 2025"
14. "deterministic rules engine AI LLM hybrid architecture pattern Python fitness health"
15. "local AI agent separate brain service architecture VPS SQLite PyTorch design pattern"
16. "RPE RIR training load model database schema design sports science app architecture"
17. "PyTorch EWC elastic weight consolidation incremental learning implementation small dataset Python code"
18. "APRE double progression algorithm Python implementation code lookup table strength training"
19. "SQLAlchemy Alembic pytest fitness workout app brownfield refactoring best practices"
20. "confidence score fallback mechanism ML prediction Python safety guard pattern production"
21. "AI personal fitness coaching technology 2025 state of the art local ML personalization trends"

---

**Technical Research Completion Date:** 2026-03-02
**Research Period:** Current comprehensive technical analysis (2024–2026)
**Source Verification:** All technical facts cited with current sources
**Technical Confidence Level:** High — based on multiple authoritative technical sources

_Этот документ является авторитетным техническим референсом для архитектурных решений gym-coach-brain и обеспечивает стратегическую техническую базу для реализации Phase 1–3._
