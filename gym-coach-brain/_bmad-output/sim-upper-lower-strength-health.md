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
| Sessions 11–20 | 1.345 |
| Sessions 21–30 | 2.229 |
| Sessions 31–40 | 0.618 |
| Sessions 41–48 | 1.204 |

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
| Increase transitions | 2 |
| Hold transitions | 35 |
| Decrease transitions | 100 |
| Decrease ratio | 73.0% |
| Exercises flagged for degradation | 21 |

## Degradation Flags

| Severity | Exercise | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |
|---|---|---|---|---|---|---|---|---|---|
| high | Dumbbell Fly | 5 | 0 | 0 | 4 | 21.0 | 2.0 | 21.0 | 90% |
| high | Romanian Deadlift | 8 | 0 | 0 | 7 | 47.5 | 5.0 | 47.5 | 89% |
| high | Lateral Raise | 6 | 0 | 0 | 5 | 13.0 | 2.0 | 13.0 | 85% |
| high | Chin-up | 8 | 0 | 2 | 5 | 4.2 | 0.7 | 4.2 | 84% |
| high | Dumbbell Shoulder Press | 6 | 0 | 0 | 5 | 25.0 | 5.0 | 25.0 | 80% |
| high | Overhead Press | 6 | 0 | 2 | 3 | 32.5 | 7.5 | 32.5 | 77% |
| high | Barbell Row | 4 | 0 | 1 | 2 | 47.5 | 12.5 | 47.5 | 74% |
| high | Bench Press | 5 | 0 | 0 | 4 | 52.5 | 15.0 | 52.5 | 71% |
| high | Cable Row | 4 | 0 | 0 | 3 | 35.0 | 10.0 | 35.0 | 71% |
| high | Cable Pull-Through | 6 | 0 | 1 | 4 | 67.5 | 20.0 | 67.5 | 70% |
| high | Bulgarian Split Squat | 6 | 0 | 1 | 4 | 62.0 | 19.0 | 62.0 | 69% |
| high | Hip Thrust | 6 | 0 | 0 | 5 | 47.5 | 15.0 | 47.5 | 68% |
| high | Pull-up | 4 | 0 | 1 | 2 | 2.4 | 0.8 | 2.4 | 68% |
| high | Barbell Squat | 6 | 0 | 0 | 5 | 45.0 | 15.0 | 45.0 | 67% |
| high | Good Morning | 8 | 0 | 1 | 6 | 67.5 | 25.0 | 67.5 | 63% |
| high | Incline Dumbbell Press | 5 | 0 | 0 | 4 | 39.0 | 15.0 | 39.0 | 62% |
| high | Leg Press | 6 | 0 | 0 | 5 | 90.0 | 35.0 | 90.0 | 61% |
| high | Deadlift | 6 | 0 | 0 | 5 | 95.0 | 37.5 | 95.0 | 61% |
| high | Dumbbell Row | 4 | 0 | 0 | 3 | 46.0 | 21.0 | 46.0 | 54% |
| high | Dip | 4 | 0 | 0 | 3 | 80.5 | 38.7 | 80.5 | 52% |
| high | Lat Pulldown | 4 | 0 | 1 | 2 | 10.0 | 5.0 | 10.0 | 50% |

## Weight Progression (Sample Exercises)

### Bench Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 52.5 |
| 11 | 2025-09-11 | 40.0 |
| 21 | 2025-09-21 | 27.5 |
| 31 | 2025-10-01 | 17.5 |
| 41 | 2025-10-11 | 15.0 |

### Barbell Row

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 47.5 |
| 13 | 2025-09-13 | 20.0 |
| 25 | 2025-09-25 | 12.5 |
| 37 | 2025-10-07 | 12.5 |

### Overhead Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 32.5 |
| 9 | 2025-09-09 | 32.5 |
| 17 | 2025-09-17 | 27.5 |
| 25 | 2025-09-25 | 15.0 |
| 33 | 2025-10-03 | 7.5 |
| 41 | 2025-10-11 | 7.5 |

### Farmer's Walk

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 16.0 |
| 3 | 2025-09-03 | 8.0 |
| 5 | 2025-09-05 | 5.0 |
| 7 | 2025-09-07 | 5.0 |
| 9 | 2025-09-09 | 7.0 |
| 11 | 2025-09-11 | 5.0 |
| 13 | 2025-09-13 | 2.0 |
| 15 | 2025-09-15 | 1.0 |
| 17 | 2025-09-17 | 1.0 |
| 19 | 2025-09-19 | 1.0 |
| 21 | 2025-09-21 | 1.0 |
| 23 | 2025-09-23 | 1.0 |
| 25 | 2025-09-25 | 1.0 |
| 27 | 2025-09-27 | 1.0 |
| 29 | 2025-09-29 | 1.0 |
| 31 | 2025-10-01 | 1.0 |
| 33 | 2025-10-03 | 1.0 |
| 35 | 2025-10-05 | 1.0 |
| 37 | 2025-10-07 | 1.0 |
| 39 | 2025-10-09 | 1.0 |
| 41 | 2025-10-11 | 1.0 |
| 43 | 2025-10-13 | 1.0 |
| 45 | 2025-10-15 | 1.0 |
| 47 | 2025-10-17 | 1.0 |

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
