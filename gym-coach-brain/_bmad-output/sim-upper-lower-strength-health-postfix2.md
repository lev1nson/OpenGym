# OpenGym Simulation Report

**Parameters:** 3 months, 4×/week, seed=42
**Scenario:** upper_lower_strength_gym
**Total sessions simulated:** 48
**Total exercise decisions:** 240

## Source Label Distribution

| Category | Decisions | Percentage |
|---|---|---|
| AI (ML correction applied) | 205 | 85.4% |
| Anomaly (ML blocked) | 9 | 3.8% |
| Core (deterministic fallback) | 26 | 10.8% |

## RPE Model MAE Trend

| Window | MAE |
|---|---|
| Sessions 1–10 | 1.266 |
| Sessions 11–20 | 1.329 |
| Sessions 21–30 | 2.234 |
| Sessions 31–40 | 0.613 |
| Sessions 41–48 | 1.193 |

**MAE sessions 1–10:** 1.266
**MAE sessions 51+:** N/A

## Split Rotation Coverage

| Split | Sessions |
|---|---|
| lower | 24 |
| upper | 24 |

## Intensity Wave Coverage

| Target RPE | Sessions |
|---|---|
| 6.0 | 2 |
| 6.5 | 12 |
| 7.5 | 12 |
| 8.0 | 11 |
| 8.5 | 11 |

## Exercise Coverage

| Exercise | Sessions Present |
|---|---|
| Calf Raise (standing) | 24 |
| Farmer's Walk | 24 |
| Diamond Push-up | 12 |
| Tricep Pushdown | 12 |
| Bodyweight Chin-up | 8 |
| Chin-up | 8 |
| Dumbbell Curl | 8 |
| Good Morning | 8 |
| Nordic Curl | 8 |
| Romanian Deadlift | 8 |
| Barbell Squat | 6 |
| Bodyweight Squat | 6 |
| Bulgarian Split Squat | 6 |
| Cable Pull-Through | 6 |
| Deadlift | 6 |
| Dumbbell Shoulder Press | 6 |
| Glute Bridge | 6 |
| Hip Thrust | 6 |
| Lateral Raise | 6 |
| Leg Press | 6 |
| Overhead Press | 6 |
| Pike Push-up | 6 |
| Bench Press | 5 |
| Dumbbell Fly | 5 |
| Incline Dumbbell Press | 5 |
| Push-up | 5 |
| Barbell Row | 4 |
| Cable Row | 4 |
| Dip | 4 |
| Dumbbell Row | 4 |
| Inverted Row | 4 |
| Lat Pulldown | 4 |
| Pull-up | 4 |

## Simulation Health

| Metric | Value |
|---|---|
| Weighted exercises tracked | 24 |
| Increase transitions | 68 |
| Hold transitions | 2 |
| Decrease transitions | 67 |
| Decrease ratio | 48.9% |
| Exercises flagged for degradation | 6 |

## Degradation Flags

| Severity | Exercise | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |
|---|---|---|---|---|---|---|---|---|---|
| high | Cable Row | 4 | 1 | 0 | 2 | 35.0 | 25.0 | 47.5 | 47% |
| medium | Hip Thrust | 6 | 2 | 0 | 3 | 47.5 | 50.0 | 72.5 | 31% |
| medium | Barbell Squat | 6 | 2 | 0 | 3 | 45.0 | 50.0 | 67.5 | 26% |
| medium | Lat Pulldown | 4 | 1 | 0 | 2 | 10.0 | 7.5 | 10.0 | 25% |
| medium | Dip | 4 | 1 | 0 | 2 | 80.5 | 62.6 | 80.5 | 22% |
| medium | Overhead Press | 6 | 2 | 0 | 3 | 32.5 | 32.5 | 40.0 | 19% |

## Weight Progression (Sample Exercises)

### Bench Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 52.5 |
| 11 | 2025-09-11 | 52.5 |
| 21 | 2025-09-21 | 47.5 |
| 31 | 2025-10-01 | 42.5 |
| 41 | 2025-10-11 | 52.5 |

### Barbell Row

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 47.5 |
| 13 | 2025-09-13 | 25.0 |
| 25 | 2025-09-25 | 32.5 |
| 37 | 2025-10-07 | 52.5 |

### Overhead Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 32.5 |
| 9 | 2025-09-09 | 40.0 |
| 17 | 2025-09-17 | 35.0 |
| 25 | 2025-09-25 | 22.5 |
| 33 | 2025-10-03 | 20.0 |
| 41 | 2025-10-11 | 32.5 |

### Farmer's Walk

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 16.0 |
| 3 | 2025-09-03 | 10.0 |
| 5 | 2025-09-05 | 13.0 |
| 7 | 2025-09-07 | 15.0 |
| 9 | 2025-09-09 | 25.0 |
| 11 | 2025-09-11 | 21.0 |
| 13 | 2025-09-13 | 11.0 |
| 15 | 2025-09-15 | 17.0 |
| 17 | 2025-09-17 | 20.0 |
| 19 | 2025-09-19 | 21.0 |
| 21 | 2025-09-21 | 16.0 |
| 23 | 2025-09-23 | 17.0 |
| 25 | 2025-09-25 | 13.0 |
| 27 | 2025-09-27 | 14.0 |
| 29 | 2025-09-29 | 16.0 |
| 31 | 2025-10-01 | 15.0 |
| 33 | 2025-10-03 | 11.0 |
| 35 | 2025-10-05 | 16.0 |
| 37 | 2025-10-07 | 21.0 |
| 39 | 2025-10-09 | 18.0 |
| 41 | 2025-10-11 | 19.0 |
| 43 | 2025-10-13 | 11.0 |
| 45 | 2025-10-15 | 18.0 |
| 47 | 2025-10-17 | 17.0 |

### Bodyweight Chin-up

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 0.0 |
| 7 | 2025-09-07 | 0.0 |
| 13 | 2025-09-13 | 0.0 |
| 19 | 2025-09-19 | 0.0 |
| 25 | 2025-09-25 | 0.0 |
| 31 | 2025-10-01 | 0.0 |
| 37 | 2025-10-07 | 0.0 |
| 43 | 2025-10-13 | 0.0 |

### Diamond Push-up

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 0.0 |
| 5 | 2025-09-05 | 0.0 |
| 9 | 2025-09-09 | 0.0 |
| 13 | 2025-09-13 | 0.0 |
| 17 | 2025-09-17 | 0.0 |
| 21 | 2025-09-21 | 0.0 |
| 25 | 2025-09-25 | 0.0 |
| 29 | 2025-09-29 | 0.0 |
| 33 | 2025-10-03 | 0.0 |
| 37 | 2025-10-07 | 0.0 |
| 41 | 2025-10-11 | 0.0 |
| 45 | 2025-10-15 | 0.0 |

## Anomaly and Rollback Events

| Session | Date | Type | Details |
|---|---|---|---|
| 26 | 2025-09-26 | fault_injection | session_idx=25: anomaly model injected (RPE=1.0) |
| 26 | 2025-09-26 | anomaly_prediction | exercise_id=20 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 26 | 2025-09-26 | anomaly_prediction | exercise_id=35 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 26 | 2025-09-26 | anomaly_prediction | exercise_id=36 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 27 | 2025-09-27 | fault_injection | session_idx=26: anomaly model injected (RPE=1.0) |
| 27 | 2025-09-27 | anomaly_prediction | exercise_id=3 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 27 | 2025-09-27 | anomaly_prediction | exercise_id=13 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 27 | 2025-09-27 | anomaly_prediction | exercise_id=8 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 27 | 2025-09-27 | anomaly_prediction | exercise_id=27 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 27 | 2025-09-27 | anomaly_prediction | exercise_id=32 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
| 27 | 2025-09-27 | anomaly_prediction | exercise_id=30 delta=0.00kg source=[AI заблокирован: дельта 19% > 15% лимит] |
