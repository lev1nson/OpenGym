# Протокол брейншторм-сессии: Epic 5 — AI-персонализация

**Дата:** 2026-03-09
**Формат:** BMAD Party Mode (мультиагентная сессия)
**Участники:** John (PM), Winston (Architect), Mary (Analyst), Amelia (Dev), Sally (UX), Quinn (QA), Bob (SM)
**Цель:** Пройти по каждой story Epic 5 и выявить критические пробелы до начала имплементации

---

## Контекст продукта (уточнён в ходе сессии)

- OpenGym — **single-user** приложение на личном VPS
- Интерфейс: **Telegram-бот**
- Один атлет, одна модель на установку — multi-tenancy не предполагается в MVP
- `athlete_id` в схеме **не нужен**

---

## Выявленные пробелы и принятые решения

### 🔴 Критические

#### #1 — Момент вызова `enqueue_predict` (eager vs lazy)

**Пробел:** AC 5.1 не определял когда именно создаётся PREDICT job. Lazy (при запросе плана) → UX-катастрофа при polling 60s.

**Решение:** `enqueue_predict` вызывается сразу после того, как атлет завершил pre-workout check-in (заполнены `sleep_hours` и `pre_readiness`). Это критично: prediction строится на актуальных данных текущего дня — сон и состояние меняются ежедневно. При запросе плана: prediction активной сессии → ML; нет/сессия брошена → ядро без ожидания.

---

#### #2 — `athlete_id` в MLJob ~~(закрыт)~~

**Пробел:** Изначально поднят вопрос об изоляции данных по атлетам.
**Закрыт:** Продукт single-user. Не актуально.

---

#### #3 — Как атлет вносит сон и readiness

**Пробел:** Feature vector включал "readiness signal", но не было определено откуда он берётся, какой endpoint, что происходит при пропуске.

**Решение:**

**Pre-workout (обязательный, кнопки Telegram):**
- `sleep_hours`: `[< 6ч]` `[6–7ч]` `[7–8ч]` `[8+ ч]` → 5.0 / 6.5 / 7.5 / 9.0
- `pre_readiness`: `[😴 Разбит]` `[😐 Норм]` `[💪 Огонь]` → 2 / 5 / 9
- Кнопки **обязательные** — бот не идёт дальше без ответа
- После обоих ответов → свободный чат с LLM + план

**Post-workout (обязательный):**
- `post_feeling`: `[😓 Тяжело]` `[👌 В самый раз]` `[😤 Слишком легко]` → 2 / 5 / 9
- После ответа → свободный чат / завершение

**Дополнение в ходе сессии:** добавлен `workout_hour` — время тренировки автоматически из `session.started_at`, циклически закодированный (`sin/cos`). Хронобиологический сигнал: циркадный ритм влияет на силовые показатели.

---

#### #4 — `MODEL_DIR` без `athlete_id` ~~(закрыт)~~

**Пробел:** Изначально поднят вопрос о per-athlete директории моделей.
**Закрыт:** Продукт single-user. `MODEL_DIR` плоский, одна модель.

---

### 🟡 Средние

#### #3 — Idempotency при повторном enqueue

**Пробел:** Retry на фронте или нестабильный коннект → дублирующие PREDICT jobs.

**Решение:** `UniqueConstraint('session_id', 'job_type')` на `MLJob`. `enqueue_predict` идемпотентен — повторный вызов возвращает существующий job.

---

#### #4 — TTL / Staleness prediction

**Пробел:** Prediction могла быть "вчерашней" (другой сон, другое состояние).

**Решение:** Prediction валидна только в рамках активной сессии. Если сессия брошена — prediction игнорируется. Новый `/workout` → новая сессия → новый check-in → новый enqueue_predict.

---

#### #7 — `rpe_to_weight()` не определена

**Пробел:** Story 5.2 вызывала функцию которой нет в Epic 4.

**Решение:** Функция определяется в Story 5.2 как часть `AdaptationEngine`:

```
ml_weight_kg = core_weight_kg * (1 - rpe_sensitivity * (predicted_rpe - target_rpe))
```

`rpe_weight_sensitivity` из `ScienceConfig.ml` (default: 0.025 — ~2.5% веса за единицу RPE). `target_rpe` из плана упражнения.

---

#### #8 — Fine-tuning threshold: суммарно или per-exercise?

**Пробел:** "≥5 завершённых сессий" — не было ясно считать ли по упражнениям.

**Решение:** 5 завершённых сессий **суммарно** где `post_feeling IS NOT NULL`. Per-exercise нереалистично (8 упражнений = 40 сессий до первого fine-tuning).

---

#### #9 — Deload weeks в обучающих данных

**Пробел:** Deload сессии (нагрузка -40-50%) зашумляют модель нетипично низкими весами.

**Решение:** `is_deload: bool` в `sessions`, пробрасывается из APRE-логики Epic 4. `enqueue_fine_tune` фильтрует `is_deload=True` сессии — они не попадают в обучающую выборку.

---

#### #10 — Версионный счётчик после rollback

**Пробел:** После rename `model_v3.pt` → `model_v3.anomaly.pt` непонятно как нумеровать следующую версию.

**Решение:** `next_version = max(n for model_v{n}.pt in MODEL_DIR, excluding .anomaly.pt, .backup.pt) + 1`. После rollback счётчик органично откатывается вместе с файлами.

---

#### #11 — Восстановление при прерванном fine-tuning

**Пробел:** Сервер упал во время fine-tuning → `model_v{n+1}.pt` corrupt или отсутствует.

**Решение:** При старте ML Worker — валидация последнего файла через `torch.load()` в try/except. Если corrupt: удалить, попробовать `.backup.pt` или `model_v{n-1}.pt`, залогировать `WARNING`.

---

#### #12 — Модуль `simulation/` не создаётся до 5.5

**Пробел:** Story 5.5 предполагала существование `gym_coach_brain/simulation/` но ни одна предыдущая story его не создавала.

**Решение:** Scaffolding (`simulation/run.py`, `simulation/synthetic_athlete.py`) — **первый шаг** Story 5.5 AC.

---

#### #13 — Нет абсолютного порога MAE

**Пробел:** "MAE после 10 > MAE после 50" — нет численного критерия успеха.

**Решение:** MAE после 50 сессий **< 1.0** RPE единицы AND минимум на **15% лучше** MAE после 10 сессий.

---

#### #14 — Генерация readiness в симуляции

**Пробел:** Случайный readiness → нулевая корреляция с performance → модель не учится использовать этот признак.

**Решение:** Реалистичная генерация:
- `sleep_hours` ~ N(7, 1), clamp [4, 10]
- `pre_readiness` коррелирует со сном: при sleep < 6 → P(readiness=2) = 0.6
- `workout_hour` — детерминированный паттерн (19:00 ± 30 мин)
- `post_feeling` — случайный со смещением к 5

---

## Итоговые изменения в эпике

Все решения зафиксированы в **Contract Snapshot v3** и AC соответствующих stories:

| Story | Изменения |
|---|---|
| 5.1 | Trigger: enqueue после check-in; уникальный constraint; sessions поля (sleep_hours, pre_readiness, post_feeling, is_deload); фильтрация deload в fine_tune |
| 5.2 | workout_hour_sin/cos в feature vector; rpe_to_weight() с формулой |
| 5.3 | Fine-tuning threshold уточнён: 5 сессий с post_feeling, суммарно |
| 5.4 | next_version через glob; startup validation; rpe_weight_sensitivity в ScienceConfig |
| 5.5 | Simulation scaffolding как первый шаг; MAE пороги; реалистичный synthetic data |

---

## Feature Vector (финальный состав, Epic 5)

| Фича | Тип | Источник | Примечание |
|---|---|---|---|
| `exercise_id` | categorical | план упражнения | per-exercise персонализация |
| `sleep_hours` | float | pre-workout кнопки | сильный предиктор производительности |
| `pre_readiness` | int (2/5/9) | pre-workout кнопки | субъективное состояние |
| `post_feeling` | int (2/5/9) | post-workout кнопки | только в FINE_TUNE данных |
| `workout_hour_sin` | float | session.started_at | хронобиология, циклическое кодирование |
| `workout_hour_cos` | float | session.started_at | хронобиология, циклическое кодирование |
| completed history | float[] | БД | история нагрузок и RPE |
| same-muscle fatigue | float | БД | усталость мышечной группы |
| readiness signal (legacy) | — | → заменён sleep_hours + pre_readiness | |
