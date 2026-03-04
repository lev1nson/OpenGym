# Quick Spec: Workout Simulator

**Status:** Draft
**Date:** 2026-03-04
**Author:** Party Mode (Barry, Winston, Murat, Mary, Carson)

---

## What & Why

Симулятор генерирует 6 месяцев тренировок виртуального атлета и прогоняет их через реальное ядро `gym-coach-brain`. Цель — находить баги в детерминированном ядре и ML-слое **до** появления реальных данных.

**Критический принцип:** симулятор взаимодействует с ядром через тот же JSON-контракт `{intent, argv, stdout, exit_code}` что и реальный OpenClaw. Никаких моков ядра — только мок ввода пользователя.

---

## Scope (в рамках этого спека)

**IN:**
- 5 архетипов атлетов с поведенческими параметрами
- Engine: прогон N недель для одного архетипа
- Event log: каждое значимое решение ядра/AI
- CLI: `python -m gym_coach_brain.simulator run --archetype steady --weeks 26`
- Markdown-отчёт по итогам прогона

**OUT (следующий спек):**
- CI/CD интеграция (ночные прогоны)
- Популяция (1000 атлетов параллельно)
- HTML-отчёт с графиками
- Adversarial / "Лжец" архетип

---

## Archetypes

| ID | Имя | Compliance | Пропуски | Особенность |
|----|-----|-----------|---------|-------------|
| `enthusiast` | Новичок-энтузиаст | 100%→40% (после нед. 4) | Нет до нед.4, потом хаотичные | Может перетренироваться |
| `steady` | Стабильный черепах | 85% всегда | ~1 в 6 недель | Базовый happy path |
| `chaotic` | Хаотичный | 50–90% random | 1–3 подряд каждые 2–3 нед | Стресс-тест адаптивности |
| `perfectionist` | Перфекционист | 95%, но игнорирует "слабые" рекоменд. | Нет | Берёт больше если AI предложил меньше |
| `injured` | Травма на нед. 8 | 90% → пауза 3 нед → 70% | Нед. 8–11 | Тест recovery logic |

**Параметры архетипа (BaseArchetype interface):**
```python
class BaseArchetype(ABC):
    name: str
    initial_strength: dict[str, float]  # exercise_name → starting_weight_kg

    def plan_week(self, week: int) -> list[PlannedSession]
    def generate_session(self, planned: PlannedSession, ai_recommendation: dict) -> SessionInput
    def compliance_rate(self, week: int) -> float  # вероятность выполнить сессию
    def will_skip(self, week: int) -> bool
```

---

## File Structure

Размещается внутри `gym-coach-brain` как отдельный модуль:

```
src/gym_coach_brain/
└── simulator/
    ├── __init__.py
    ├── __main__.py          # CLI entry: python -m gym_coach_brain.simulator
    ├── engine.py            # SimulatorEngine: прогоняет недели, собирает events
    ├── events.py            # EventLog: dataclass + append + to_markdown()
    ├── archetypes/
    │   ├── __init__.py
    │   ├── base.py          # BaseArchetype ABC
    │   ├── enthusiast.py
    │   ├── steady.py
    │   ├── chaotic.py
    │   ├── perfectionist.py
    │   └── injured.py
    └── report/
        ├── __init__.py
        └── generator.py     # ReportGenerator: events + stats → markdown

tests/
└── test_simulator/
    ├── test_engine.py       # Мок ядра через mock JSON contract
    ├── test_archetypes.py   # compliance_rate, will_skip, generate_session
    └── test_report.py       # Markdown output format
```

---

## Core Interface

### SimulatorEngine

```python
# engine.py
class SimulatorEngine:
    def __init__(self, archetype: BaseArchetype, db_url: str, weeks: int = 26):
        ...

    def run(self) -> EventLog:
        """Прогоняет weeks недель. Возвращает полный EventLog."""
        for week in range(self.weeks):
            sessions = self.archetype.plan_week(week)
            for planned in sessions:
                if self.archetype.will_skip(week):
                    self.events.log_skip(week, planned)
                    continue

                # Получить рекомендацию ядра через реальный JSON контракт
                rec = self._call_core("adapt_recommend", planned.exercise)

                # Атлет реагирует на рекомендацию
                session_input = self.archetype.generate_session(planned, rec)

                # Выполнить сессию через реальное ядро
                result = self._call_core("workout_log", session_input)

                self.events.log_session(week, planned, rec, session_input, result)

        return self.events

    def _call_core(self, intent: str, data: dict) -> dict:
        """Вызывает реальное ядро через JSON контракт. Никаких моков."""
        # subprocess → api/main.py → возвращает {intent, stdout, exit_code}
        ...
```

### EventLog

```python
# events.py — что логируем
@dataclass
class SimEvent:
    week: int
    session: int
    event_type: str       # SESSION | SKIP | ANOMALY | FALLBACK | PLATEAU | RECOVERY
    archetype: str
    exercise: str
    recommended_weight: float | None
    actual_weight: float | None
    compliance: bool
    ai_confidence: float | None   # из rpe_predictions если доступно
    exit_code: int
    notes: str
```

**Типы событий:**
- `SESSION` — обычная сессия выполнена
- `SKIP` — атлет пропустил
- `ANOMALY` — exit_code != 0 или невалидные данные в stdout
- `FALLBACK` — AI confidence < 0.6, сработал Double Progression
- `PLATEAU` — вес не изменился 3+ сессии подряд
- `RECOVERY` — первая сессия после пропуска/травмы

---

## Report Format

Генерируется в `_bmad-output/simulator-reports/YYYY-MM-DD-{archetype}.md`

```markdown
# Simulator Report: steady — 26 недель

**Дата:** 2026-03-04
**Архетип:** Стабильный черепах (steady)
**Период:** 26 недель

## Executive Summary

| Метрика | Значение | Статус |
|---------|----------|--------|
| Сессий выполнено | 74/78 | ✅ |
| Аномалий (exit_code != 0) | 2 | ⚠️ |
| AI Fallback срабатываний | 8 | ✅ |
| Плато обнаружено | 3 | ✅ |
| Средний прогресс Bench Press | +22.5 kg | ✅ |

## Progression Charts

[Bench Press прогрессия по неделям]
Нед 1: 60kg → Нед 13: 75kg → Нед 26: 82.5kg

## Incident Log

| Нед | Упражнение | Событие | Детали |
|-----|-----------|---------|--------|
| 4 | Squat | ANOMALY | exit_code=1: PUOS limit exceeded |
| 12 | Bench | PLATEAU | 3 сессии подряд: 75kg |
| 14 | Bench | FALLBACK | AI confidence=0.41, Double Progression applied |
```

---

## CLI

```bash
# Прогон одного архетипа
python -m gym_coach_brain.simulator run --archetype steady --weeks 26

# Прогон всех архетипов последовательно
python -m gym_coach_brain.simulator run --all --weeks 26

# Указать путь к БД (изолированная тест-БД)
python -m gym_coach_brain.simulator run --archetype injured --db sqlite:///sim_test.db

# Вывод отчёта в stdout вместо файла
python -m gym_coach_brain.simulator run --archetype chaotic --stdout
```

Симулятор создаёт **свою изолированную SQLite БД** (не трогает production `gym_coach.sqlite`).

---

## Implementation Order

1. `events.py` — dataclass + EventLog (нет зависимостей)
2. `archetypes/base.py` — ABC (нет зависимостей)
3. `archetypes/steady.py` — первый архетип, happy path
4. `engine.py` — SimulatorEngine с `_call_core` через subprocess
5. `report/generator.py` — markdown из EventLog
6. `__main__.py` — CLI
7. Остальные 4 архетипа
8. Тесты

---

## Acceptance Criteria

- [ ] `python -m gym_coach_brain.simulator run --archetype steady --weeks 26` завершается без ошибок
- [ ] Отчёт содержит Executive Summary, Progression section, Incident Log
- [ ] Архетип `injured` генерирует событие `RECOVERY` на нед. 11–12
- [ ] Симулятор использует изолированную БД — production БД не затронута
- [ ] `ANOMALY` события логируются при любом exit_code != 0 из ядра
- [ ] Тесты: engine мокирует `_call_core`, тестирует логику без реального ядра

---

## Open Questions

1. **Начальные веса** — брать из реального профиля пользователя или хардкодить в архетипе? → Рекомендация: хардкод в архетипе для reproducibility
2. **Программа тренировок** — использовать реальную `program.example.json` или симулированную? → Рекомендация: реальную, импортировать через `program import`
3. **Время разработки** — 1 спринт (Barry estimate: ~2-3 дня реальной работы)
