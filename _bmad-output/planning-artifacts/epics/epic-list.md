# Epic List

## Epic 1: Научная методология
Разработать production-ready ScienceEvidence.md — полноценную методологическую базу данных с научно обоснованными формулами, коэффициентами и прогрессивной системой методик для всех уровней атлетов.
**Блокирует:** Epic 2, Epic 3, Epic 4
**FRs covered:** Пререквизит для FR1-FR8, FR12-FR14 (все FR зависящие от ScienceConfig)

## Epic 2: База знаний и мастер-данные
Создать полную базу знаний: таксономию мышц и паттернов движения, библиотеку ~35 базовых упражнений с полными метаданными, каталог оборудования и спецификацию ML-фичей. Фундамент для корректной работы PUOS и нейросети.
**Requires:** Epic 1 (завершён), Stories 3.1–3.2 из Epic 3 (завершены — нужен Alembic)
**Блокирует:** Epic 4, Epic 5
**FRs covered:** Пререквизит для FR5, FR6, FR12 (фракционный объём, PUOS, ML features)

## Epic 3: Основа проекта и профиль атлета
Атлет может пройти интерактивный онбординг через OpenClaw чат, его ответы конвертируются в числовые коэффициенты, создаётся профиль с параметрами и оборудованием в SQLite. Проект инициализирован с нуля (greenfield).
**⚠️ Порядок выполнения (критично):** Stories 3.1–3.2 выполняются ДО Epic 2 — они создают project skeleton и Alembic, которые Epic 2 требует для seed-миграций. Stories 3.3–3.5 выполняются ПОСЛЕ Epic 2.
**Requires (Stories 3.1–3.2):** Epic 1 (завершён)
**Requires (Stories 3.3–3.5):** Epic 1 (завершён), Epic 2 (завершён)
**FRs covered:** FR9, FR10, FR13, FR14

## Epic 4: Детерминированное тренировочное ядро
Атлет получает научно-обоснованный план тренировки с автоматическим Recap/Summary, PUOS-защитой, lifestyle-коэффициентами и pluggable методологиями. Все алгоритмы реализованы исключительно на основе ScienceEvidence.md.
**Requires:** Epic 1 (завершён), Epic 2 (завершён), Epic 3 (завершён)
**FRs covered:** FR5, FR6, FR8, FR15, FR16, FR17

## Epic 5: AI-персонализация нагрузок
Нагрузки точно подстраиваются под физиологию конкретного атлета — система обучается на его данных, предсказывает RPE с автоматическим fallback, ML-статистика участвует в разблокировке продвинутых методик.
**Requires:** Epic 4 (завершён)
**FRs covered:** FR1, FR2, FR3, FR4, FR7

## Epic 6: Финальная интеграция и деплой
gym-coach-brain полностью интегрирован как OpenClaw скилл: api/ handlers дописаны для всех интентов, router.py обновлён, SKILL.md обновлён (новый entry point, убран system_prompt coach-prompt.md), fractional volume analytics готова. Система задеплоена как два systemd сервиса, CI/CD настроен.

Архитектурное решение: gym-coach-brain остаётся ephemeral subprocess (не daemon) — state между вызовами хранится в SQLite. Наш код (adaptation/recap.py, adaptation/summary.py, adaptation/explanation.py) формирует финальный текст пользователю — главный агент OpenClaw передаёт stdout в Telegram as-is.
**Requires:** Epic 5 (завершён)
**FRs covered:** FR11, FR12

---

## Порядок выполнения (фактический)

```
Epic 1              → ScienceEvidence.md (независим)
Epic 3 [3.1, 3.2]  → uv init + SQLAlchemy models + Alembic (до Epic 2!)
Epic 2              → Seed данные: мышцы, упражнения, оборудование, ML-фичи
Epic 3 [3.3–3.5]   → ScienceConfig loader, Onboarding, API handlers
Epic 4              → Детерминированное ядро (APRE, PUOS, Readiness, Adaptation)
Epic 5              → ML Worker, RPEModel, EWC, версионирование
Epic 6              → Финальная интеграция, деплой, CI/CD
```
