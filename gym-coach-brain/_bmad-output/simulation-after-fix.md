# OpenGym Simulation Report

**Parameters:** 8 months, 3×/week, seed=42
**Scenario:** ppl_hypertrophy_gym
**Total sessions simulated:** 96
**Total exercise decisions:** 306

## Source Label Distribution

| Category | Decisions | Percentage |
|---|---|---|
| AI (ML correction applied) | 285 | 93.1% |
| Anomaly (ML blocked) | 6 | 2.0% |
| Core (deterministic fallback) | 15 | 4.9% |

## RPE Model MAE Trend

| Window | MAE |
|---|---|
| Sessions 1–10 | 0.946 |
| Sessions 11–20 | 0.757 |
| Sessions 21–30 | 1.933 |
| Sessions 31–40 | 0.808 |
| Sessions 41–50 | 0.777 |
| Sessions 51–60 | 0.656 |
| Sessions 61–70 | 0.661 |
| Sessions 71–80 | 0.607 |
| Sessions 81–90 | 0.716 |
| Sessions 91–96 | 0.803 |

**MAE sessions 1–10:** 0.946
**MAE sessions 51+:** 0.679

## Split Rotation Coverage

| Split | Sessions |
|---|---|
| legs | 32 |
| pull | 32 |
| push | 32 |

## Intensity Wave Coverage

| Target RPE | Sessions |
|---|---|
| 6.0 | 5 |
| 6.5 | 24 |
| 7.0 | 21 |
| 7.5 | 24 |
| 8.0 | 22 |

## Exercise Coverage

| Exercise | Sessions Present |
|---|---|
| Bulgarian Split Squat | 32 |
| Cable Pull-Through | 32 |
| Calf Raise (standing) | 32 |
| Farmer's Walk | 32 |
| Romanian Deadlift | 32 |
| Dumbbell Curl | 23 |
| Tricep Pushdown | 14 |
| Dumbbell Shoulder Press | 10 |
| Incline Dumbbell Press | 10 |
| Lateral Raise | 10 |
| Dumbbell Fly | 9 |
| Cable Row | 8 |
| Lat Pulldown | 8 |
| Bodyweight Chin-up | 7 |
| Overhead Press | 7 |
| Bench Press | 6 |
| Dumbbell Row | 6 |
| Pike Push-up | 5 |
| Push-up | 5 |
| Barbell Row | 4 |
| Diamond Push-up | 4 |
| Inverted Row | 4 |
| Chin-up | 2 |
| Dip | 2 |
| Pull-up | 2 |

## Simulation Health

| Metric | Value |
|---|---|
| Weighted exercises tracked | 19 |
| Increase transitions | 109 |
| Hold transitions | 14 |
| Decrease transitions | 107 |
| Decrease ratio | 46.5% |
| Exercises flagged for degradation | 2 |

## Degradation Flags

| Severity | Exercise | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |
|---|---|---|---|---|---|---|---|---|---|
| high | Dumbbell Fly | 9 | 3 | 0 | 5 | 45.0 | 32.0 | 47.0 | 32% |
| medium | Dumbbell Row | 6 | 2 | 0 | 3 | 25.0 | 22.0 | 32.0 | 31% |

## Movement Pattern Health

| Metric | Value |
|---|---|
| Tracked movement pattern groups | 7 |
| Increase transitions | 109 |
| Hold transitions | 14 |
| Decrease transitions | 107 |
| Decrease ratio | 46.5% |
| Flagged movement pattern groups | 0 |

## Movement Pattern Health Flags

No movement pattern flags detected.

## Primary Muscle Health

| Metric | Value |
|---|---|
| Tracked primary muscle groups | 9 |
| Increase transitions | 109 |
| Hold transitions | 14 |
| Decrease transitions | 107 |
| Decrease ratio | 46.5% |
| Flagged primary muscle groups | 0 |

## Primary Muscle Health Flags

No primary muscle flags detected.

## Equipment Type Health

| Metric | Value |
|---|---|
| Tracked equipment type groups | 5 |
| Increase transitions | 109 |
| Hold transitions | 14 |
| Decrease transitions | 107 |
| Decrease ratio | 46.5% |
| Flagged equipment type groups | 0 |

## Equipment Type Health Flags

No equipment type flags detected.

## Exercise Cluster Health

| Metric | Value |
|---|---|
| Tracked exercise cluster groups | 5 |
| Increase transitions | 109 |
| Hold transitions | 14 |
| Decrease transitions | 107 |
| Decrease ratio | 46.5% |
| Flagged exercise cluster groups | 0 |

## Exercise Cluster Health Flags

No exercise cluster flags detected.

## Exercise Family Health

| Metric | Value |
|---|---|
| Tracked exercise family groups | 18 |
| Increase transitions | 109 |
| Hold transitions | 14 |
| Decrease transitions | 107 |
| Decrease ratio | 46.5% |
| Flagged exercise family groups | 0 |

## Exercise Family Health Flags

No exercise family flags detected.

## Weight Progression (Sample Exercises)

### Incline Dumbbell Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 37.0 |
| 16 | 2025-10-01 | 33.0 |
| 25 | 2025-10-19 | 32.0 |
| 34 | 2025-11-06 | 31.0 |
| 43 | 2025-11-24 | 44.0 |
| 55 | 2025-12-18 | 24.0 |
| 64 | 2026-01-05 | 34.0 |
| 76 | 2026-01-29 | 43.0 |
| 85 | 2026-02-16 | 31.0 |
| 94 | 2026-03-06 | 34.0 |

### Dumbbell Shoulder Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 24.0 |
| 13 | 2025-09-25 | 19.0 |
| 22 | 2025-10-13 | 16.0 |
| 31 | 2025-10-31 | 25.0 |
| 40 | 2025-11-18 | 28.0 |
| 52 | 2025-12-12 | 24.0 |
| 58 | 2025-12-24 | 21.0 |
| 70 | 2026-01-17 | 26.0 |
| 79 | 2026-02-04 | 17.0 |
| 88 | 2026-02-22 | 19.0 |

### Lat Pulldown

| Session | Date | Weight (kg) |
|---|---|---|
| 2 | 2025-09-03 | 32.5 |
| 20 | 2025-10-09 | 37.5 |
| 29 | 2025-10-27 | 35.0 |
| 38 | 2025-11-14 | 37.5 |
| 50 | 2025-12-08 | 35.0 |
| 62 | 2026-01-01 | 17.5 |
| 74 | 2026-01-25 | 25.0 |
| 86 | 2026-02-18 | 17.5 |

### Dumbbell Curl

| Session | Date | Weight (kg) |
|---|---|---|
| 2 | 2025-09-03 | 35.0 |
| 11 | 2025-09-21 | 35.0 |
| 14 | 2025-09-27 | 40.0 |
| 17 | 2025-10-03 | 34.0 |
| 23 | 2025-10-15 | 34.0 |
| 26 | 2025-10-21 | 38.0 |
| 29 | 2025-10-27 | 38.0 |
| 32 | 2025-11-02 | 39.0 |
| 38 | 2025-11-14 | 43.0 |
| 41 | 2025-11-20 | 40.0 |
| 44 | 2025-11-26 | 36.0 |
| 47 | 2025-12-02 | 44.0 |
| 53 | 2025-12-14 | 39.0 |
| 59 | 2025-12-26 | 34.0 |
| 62 | 2026-01-01 | 26.0 |
| 68 | 2026-01-13 | 38.0 |
| 71 | 2026-01-19 | 46.0 |
| 74 | 2026-01-25 | 36.0 |
| 77 | 2026-01-31 | 52.0 |
| 83 | 2026-02-12 | 49.0 |
| 86 | 2026-02-18 | 29.0 |
| 89 | 2026-02-24 | 56.0 |
| 92 | 2026-03-02 | 51.0 |

### Farmer's Walk

| Session | Date | Weight (kg) |
|---|---|---|
| 2 | 2025-09-03 | 25.0 |
| 5 | 2025-09-09 | 28.0 |
| 8 | 2025-09-15 | 23.0 |
| 11 | 2025-09-21 | 27.0 |
| 14 | 2025-09-27 | 31.0 |
| 17 | 2025-10-03 | 26.0 |
| 20 | 2025-10-09 | 31.0 |
| 23 | 2025-10-15 | 26.0 |
| 26 | 2025-10-21 | 29.0 |
| 29 | 2025-10-27 | 29.0 |
| 32 | 2025-11-02 | 29.0 |
| 35 | 2025-11-08 | 28.0 |
| 38 | 2025-11-14 | 31.0 |
| 41 | 2025-11-20 | 27.0 |
| 44 | 2025-11-26 | 24.0 |
| 47 | 2025-12-02 | 29.0 |
| 50 | 2025-12-08 | 30.0 |
| 53 | 2025-12-14 | 25.0 |
| 56 | 2025-12-20 | 22.0 |
| 59 | 2025-12-26 | 21.0 |
| 62 | 2026-01-01 | 16.0 |
| 65 | 2026-01-07 | 27.0 |
| 68 | 2026-01-13 | 22.0 |
| 71 | 2026-01-19 | 27.0 |
| 74 | 2026-01-25 | 21.0 |
| 77 | 2026-01-31 | 29.0 |
| 80 | 2026-02-06 | 28.0 |
| 83 | 2026-02-12 | 26.0 |
| 86 | 2026-02-18 | 15.0 |
| 89 | 2026-02-24 | 29.0 |
| 92 | 2026-03-02 | 26.0 |
| 95 | 2026-03-08 | 20.0 |

### Bulgarian Split Squat

| Session | Date | Weight (kg) |
|---|---|---|
| 3 | 2025-09-05 | 66.0 |
| 6 | 2025-09-11 | 37.0 |
| 9 | 2025-09-17 | 52.0 |
| 12 | 2025-09-23 | 66.0 |
| 15 | 2025-09-29 | 53.0 |
| 18 | 2025-10-05 | 62.0 |
| 21 | 2025-10-11 | 66.0 |
| 24 | 2025-10-17 | 64.0 |
| 27 | 2025-10-23 | 38.0 |
| 30 | 2025-10-29 | 67.0 |
| 33 | 2025-11-04 | 51.0 |
| 36 | 2025-11-10 | 49.0 |
| 39 | 2025-11-16 | 51.0 |
| 42 | 2025-11-22 | 55.0 |
| 45 | 2025-11-28 | 70.0 |
| 48 | 2025-12-04 | 64.0 |
| 51 | 2025-12-10 | 62.0 |
| 54 | 2025-12-16 | 66.0 |
| 57 | 2025-12-22 | 83.0 |
| 60 | 2025-12-28 | 90.0 |
| 63 | 2026-01-03 | 52.0 |
| 66 | 2026-01-09 | 88.0 |
| 69 | 2026-01-15 | 99.0 |
| 72 | 2026-01-21 | 55.0 |
| 75 | 2026-01-27 | 93.0 |
| 78 | 2026-02-02 | 68.0 |
| 81 | 2026-02-08 | 104.0 |
| 84 | 2026-02-14 | 108.0 |
| 87 | 2026-02-20 | 101.0 |
| 90 | 2026-02-26 | 71.0 |
| 93 | 2026-03-04 | 108.0 |
| 96 | 2026-03-10 | 103.0 |

## Anomaly and Rollback Events

| Session | Date | Type | Details |
|---|---|---|---|
| 26 | 2025-10-21 | fault_injection | session_idx=25: anomaly model injected (RPE=1.0) |
| 26 | 2025-10-21 | anomaly_prediction | exercise_id=12 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
| 26 | 2025-10-21 | anomaly_prediction | exercise_id=32 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
| 26 | 2025-10-21 | anomaly_prediction | exercise_id=27 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
| 27 | 2025-10-23 | fault_injection | session_idx=26: anomaly model injected (RPE=1.0) |
| 27 | 2025-10-23 | anomaly_prediction | exercise_id=20 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
| 27 | 2025-10-23 | anomaly_prediction | exercise_id=22 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
| 27 | 2025-10-23 | anomaly_prediction | exercise_id=36 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
