# Epic 7: Simulation & Validation Engine

Создание полноценного симулятора тренировочного процесса для предиктивной валидации алгоритмов. Система должна позволять «прокручивать» недели тренировок для синтетических профилей атлетов, выявляя логические ошибки, перетренированность или неэффективность методик до их выхода в продакшн. Результатом каждой симуляции является структурированный отчет о «дельтах» (отклонениях от научной базы).

**Requires:** Epic 1 (завершён), Epic 2 (в процессе - Story 2.1), Epic 3 (частично)
**FRs covered:** FR5, FR6, FR8 (валидация логики), Quality Assurance

## Story 7.1: Генератор хаоса и отчет о дельтах (ex-2.2)

As a dev agent,
I want to implement a CLI-based Simulation Engine that runs synthetic athlete profiles through our Pydantic models and training logic,
So that I can identify logical flaws and scientific inconsistencies through a structured feedback loop of "deltas".

**Acceptance Criteria:**

**Given** `ScienceConfig` и Pydantic модели из `gym-coach-brain` доступны
**When** `python -m simulation.engine --profile synthetic_newbie --weeks 4` вызывается
**Then** система генерирует последовательность тренировок, имитируя ответы атлета (RPE, reps)
**And** для каждого шага симуляции рассчитывается "Delta": разница между предсказанным прогрессом и фактическим результатом симуляции
**And** симулятор использует те же алгоритмы (APRE, PUOS, Readiness), что и основное ядро
**And** по завершении генерируется `simulation_report_[timestamp].json`, содержащий:
    - Метрики накопленной усталости
    - График прогрессии рабочих весов
    - Список нарушений PUOS или ScienceEvidence лимитов
    - Сводную таблицу аномалий (где логика повела себя непредсказуемо)
**And** движок поддерживает "Chaos Injection": случайные пропуски тренировок, аномально высокий стресс или ошибки ввода данных для проверки устойчивости системы
**And** `pytest tests/test_simulation/test_engine.py` проходит:
    - Симуляция 1 недели завершается без ошибок
    - Отчет содержит валидный JSON
    - Дельты рассчитываются детерминированно при фиксированном seed
