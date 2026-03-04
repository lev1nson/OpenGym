---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
classification:
  projectType: CLI Tool / Agent
  domain: Scientific (Sports Science / Physiology)
  complexity: Medium
  projectContext: brownfield
inputDocuments:
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture.md
  - docs/development-guide.md
  - docs/source-tree-analysis.md
  - docs/api-contracts.md
  - docs/data-models.md
  - docs/technology-stack.md
  - _bmad-output/implementation-artifacts/tech-spec-gym-coach-bug-fixes.md
  - workspace/skills/gym-coach/ScienceEvidence.md
project_name: gym-coach-brain
status: finalized
---

# Product Requirements Document (PRD) - gym-coach-brain

## 1. Executive Summary

gym-coach-brain — это интеллектуальное вычислительное ядро для управления тренировочным процессом на базе платформы openclaw. Система разворачивается локально на VPS (16-32 ГБ RAM) и выступает в роли «цифрового физиологического двойника» атлета.

**Цель:** Полное снятие когнитивной нагрузки с пользователя за счет автоматизации планирования, адаптации весов и ротации упражнений.
**Ключевой дифференциатор:** Детерминированное ядро на базе научного свода правил (ScienceEvidence.md), работающее в связке с интерактивным онбордингом. Система исключает «галлюцинации» ИИ в расчетах, так как вся логика адаптации (APRE, Double Progression) жестко привязана к коэффициентам в БД.

## 2. Success Criteria

### User & Business Success
*   **Zero Planning:** Пользователь не тратит время на расчет весов и подходов; 100% решений принимает система на основе методологии.
*   **Scientific Accountability:** Каждое изменение веса или объема сопровождается кратким пояснением со ссылкой на принципы из ScienceEvidence.md.
*   **Continuous Progress:** Стабильное выполнение плана без системного недовосстановления (подтверждается HRV и RPE трендами).
*   **N=1 Validation:** Среднеквадратичная ошибка (MSE) прогноза нейросети для RPE/RIR на 15-20% ниже, чем у стандартных формул после 8 недель обучения.

### Technical Success
*   **Scientific Safeguard:** 100% блокировка команд, нарушающих физиологические лимиты PUOS (11 фракционных сетов на группу).
*   **Integration:** Бесшовный асинхронный обмен JSON-данными с агентом OpenClaw.
*   **Privacy:** Гарантированная изоляция данных и весов модели в контуре VPS.

## 3. Product Scope & Roadmap

### Phase 1: MVP (The Brain)
*   **Core Logic:** Расчет PUOS, фракционных сетов и Double Progression.
*   **Adaptive Engine:** Локальная нейросеть PyTorch для персонализации нагрузок.
*   **Safety Interlocks:** Валидатор лимитов и Confidence-Based Fallback.
*   **Interface:** Асинхронное JSON API для интеграции с OpenClaw.

### Phase 2: Growth (The Optimization)
*   **Context Awareness:** Профили оборудования (Home/Gym) и интеграция HRV (APRE).
*   **Analytics Suite:** Генерация Diff-отчетов и визуализация прогрессии.
*   **NL Support:** Полноценный голосовой интерфейс через основной агент.

### Phase 3: Vision (The Autonomy)
*   **Proactive Coaching:** Агент инициирует взаимодействие и контролирует техника через Computer Vision.
*   **Wearable Ecosystem:** Прямая синхронизация с Apple Watch/Oura.

## 4. User Journeys

### Journey 1: Алекс (Опытный атлет)
*   **Opening:** Алекс начинает тренировку. Система выдает **Recap** прошлой сессии: «В прошлый раз ты прибавил 2.5кг в жиме. Сегодня идем по плану, веса без изменений».
*   **Climax:** После тяжелого подхода с RPE 9, система мгновенно снижает вес на 2.5кг для следующего сета, ссылаясь на риск переутомления по PUOS.
*   **Resolution:** В конце тренировки система подводит **Summary**: «Тренировка прошла успешно, объем выполнен на 95%. Твой прогресс в силе +2% за неделю. Данные ушли на дообучение».

### Journey 2: Макс (Админ/Разработчик)
*   **Opening:** Макс запрашивает аудит состояния нейросети.
*   **Action:** Система выдает Diff-отчет: сравнение точности прогнозов текущей модели и базовых формул на исторических данных.
*   **Resolution:** Макс видит сходимость модели и подтверждает успешность обучения N=1.

## 5. Domain-Specific Requirements

*   **Science-over-AI:** Детерминированные лимиты ScienceEvidence.md всегда приоритетнее выводов нейросети.
*   **Fractional Volume:** Учет нагрузки по модели 1.0 (агонист) / 0.5 (синергист).
*   **SMH Prioritization:** Метаданные упражнений должны содержать флаг stretch_mediated для корректной ротации в гипертрофийных фазах.
*   **Training Cadence:** Инкрементальное дообучение (Incremental Learning) строго после каждой подтвержденной сессии.

## 6. Functional Requirements (Capability Contract)

### Capability Area: Intelligence & ML
*   **FR1:** Система выполняет инкрементальный Fine-tuning локальной модели после каждой тренировки.
*   **FR2:** Система прогнозирует индивидуальный RPE с расчетом Confidence Score.
*   **FR3:** Система выполняет автоматическую оптимизацию памяти VPS (Memory Management) после циклов обучения.
*   **FR4:** Система версионирует веса нейросети и выполняет Diff-анализ точности.

### Capability Area: Planning & Safety
*   **FR5:** Система рассчитывает план тренировки на основе SMH-метаданных и истории атлета.
*   **FR6:** Система блокирует превышение лимита PUOS (11 сетов на группу).
*   **FR7:** Система автоматически откатывается к Double Progression при низком Confidence Score ИИ.
*   **FR8:** Система предоставляет обоснование изменений веса со ссылками на ScienceEvidence.md (автоматический Recap в начале и Summary в конце).

### Capability Area: Data & Operations
*   **FR9:** Атлет проходит интерактивный онбординг (Closed-loop questions).
*   **FR10:** Система поддерживает профили оборудования (Gym Environment JSON).
*   **FR11:** Система выполняет асинхронный JSON-обмен данными с OpenClaw.
*   **FR12:** Система генерирует историческую аналитику фракционного объема нагрузки.

### Capability Area: Onboarding & Mapping
*   **FR13:** Каждый ответ онбординга мапится на конкретные числовые коэффициенты в БД (например, возраст -> коэффициент объема, опыт -> шаг прогрессии).
*   **FR14:** Логика адаптации (APRE, Double Progression) строится на программных алгоритмах, исключающих свободную интерпретацию параметров со стороны LLM.

### Capability Area: Communication Protocol
*   **FR15:** Перед началом тренировки система обязана выдать Recap: сравнение с прошлой сессией и план на сегодня.
*   **FR16:** В конце тренировки система обязана выдать Summary: оценку выполнения плана и прогноз восстановления.
*   **FR17:** Система учитывает образ жизни (lifestyle) пользователя через коэффициенты восстановления (сна, стресса), вносимые через readiness-лог.

## 7. Non-Functional Requirements

*   **Performance:** Отсутствие жесткого лимита времени на ответ; приоритет точности расчетов. Асинхронное выполнение тяжелых ML-операций.
*   **Scalability:** Базовая работа на 16 ГБ RAM с архитектурной поддержкой масштабирования до 32 ГБ.
*   **Reliability:** Атомарность записей в SQLite (транзакции). Обязательный бэкап весов модели перед дообучением.
*   **Privacy:** Zero Cloud Leak. Все вычисления и хранение данных строго локально на VPS атлета.

## 8. Innovation Analysis

*   **N=1 Neural Architecture:** Переход от общих моделей к локальному Fine-tuning под конкретную физиологию.
*   **Parallel Piloting:** Постоянное сравнение точности ИИ и классических формул в реальном времени.
*   **Invisible UI:** Полное отсутствие интерфейса за пределами естественного диалога с агентом OpenClaw.
