# OpenGym Simulation Report

**Parameters:** 3 months, 3×/week, seed=42
**Scenario:** ppl_hypertrophy_gym
**Total sessions simulated:** 36
**Total exercise decisions:** 120

## Source Label Distribution

| Category | Decisions | Percentage |
|---|---|---|
| AI (ML correction applied) | 101 | 84.2% |
| Anomaly (ML blocked) | 3 | 2.5% |
| Core (deterministic fallback) | 16 | 13.3% |

## RPE Model MAE Trend

| Window | MAE |
|---|---|
| Sessions 1–10 | 0.867 |
| Sessions 11–20 | 0.783 |
| Sessions 21–30 | 1.896 |
| Sessions 31–36 | 0.953 |

**MAE sessions 1–10:** 0.867
**MAE sessions 51+:** N/A

## Split Rotation Coverage

| Split | Sessions |
|---|---|
| legs | 12 |
| pull | 12 |
| push | 12 |

## Intensity Wave Coverage

| Target RPE | Sessions |
|---|---|
| 6.0 | 2 |
| 6.5 | 9 |
| 7.0 | 7 |
| 7.5 | 10 |
| 8.0 | 8 |

## Exercise Coverage

| Exercise | Sessions Present |
|---|---|
| Calf Raise (standing) | 12 |
| Farmer's Walk | 12 |
| Diamond Push-up | 6 |
| Tricep Pushdown | 6 |
| Barbell Squat | 4 |
| Bodyweight Chin-up | 4 |
| Bodyweight Squat | 4 |
| Bulgarian Split Squat | 4 |
| Chin-up | 4 |
| Dumbbell Curl | 4 |
| Good Morning | 4 |
| Nordic Curl | 4 |
| Romanian Deadlift | 4 |
| Bench Press | 3 |
| Cable Pull-Through | 3 |
| Deadlift | 3 |
| Dumbbell Shoulder Press | 3 |
| Glute Bridge | 3 |
| Hip Thrust | 3 |
| Incline Dumbbell Press | 3 |
| Lateral Raise | 3 |
| Overhead Press | 3 |
| Pike Push-up | 3 |
| Barbell Row | 2 |
| Cable Row | 2 |
| Dip | 2 |
| Dumbbell Fly | 2 |
| Dumbbell Row | 2 |
| Inverted Row | 2 |
| Lat Pulldown | 2 |
| Pull-up | 2 |
| Push-up | 2 |

## Simulation Health

| Metric | Value |
|---|---|
| Weighted exercises tracked | 23 |
| Increase transitions | 24 |
| Hold transitions | 3 |
| Decrease transitions | 30 |
| Decrease ratio | 52.6% |
| Exercises flagged for degradation | 5 |

## Degradation Flags

| Severity | Exercise | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |
|---|---|---|---|---|---|---|---|---|---|
| high | Bulgarian Split Squat | 4 | 1 | 0 | 2 | 73.0 | 39.0 | 73.0 | 47% |
| high | Good Morning | 4 | 1 | 0 | 2 | 65.0 | 35.0 | 65.0 | 46% |
| high | Cable Pull-Through | 3 | 0 | 0 | 2 | 65.0 | 37.5 | 65.0 | 42% |
| high | Overhead Press | 3 | 0 | 0 | 2 | 25.0 | 15.0 | 25.0 | 40% |
| high | Dumbbell Curl | 4 | 1 | 0 | 2 | 46.0 | 32.0 | 46.0 | 30% |

## Movement Pattern Health

| Metric | Value |
|---|---|
| Tracked movement pattern groups | 7 |
| Increase transitions | 36 |
| Hold transitions | 1 |
| Decrease transitions | 36 |
| Decrease ratio | 49.3% |
| Flagged movement pattern groups | 1 |

## Movement Pattern Health Flags

| Severity | Movement Pattern | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |
|---|---|---|---|---|---|---|---|---|---|
| high | vertical_pull | 10 | 3 | 0 | 6 | 40.0 | 9.6 | 40.0 | 76% |

## Primary Muscle Health

| Metric | Value |
|---|---|
| Tracked primary muscle groups | 9 |
| Increase transitions | 53 |
| Hold transitions | 0 |
| Decrease transitions | 46 |
| Decrease ratio | 46.5% |
| Flagged primary muscle groups | 1 |

## Primary Muscle Health Flags

| Severity | Primary Muscle | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |
|---|---|---|---|---|---|---|---|---|---|
| high | biceps | 12 | 4 | 0 | 7 | 46.0 | 0.0 | 46.0 | 100% |

## Equipment Type Health

| Metric | Value |
|---|---|
| Tracked equipment type groups | 5 |
| Increase transitions | 25 |
| Hold transitions | 1 |
| Decrease transitions | 32 |
| Decrease ratio | 55.2% |
| Flagged equipment type groups | 1 |

## Equipment Type Health Flags

| Severity | Equipment Type | Obs | Inc | Hold | Dec | First kg | Last kg | Peak kg | Drop vs peak |
|---|---|---|---|---|---|---|---|---|---|
| medium | dumbbell | 25 | 9 | 0 | 15 | 39.0 | 39.0 | 73.0 | 47% |

## Weight Progression (Sample Exercises)

### Bench Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 37.5 |
| 16 | 2025-10-01 | 40.0 |
| 31 | 2025-10-31 | 40.0 |

### Overhead Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 25.0 |
| 13 | 2025-09-25 | 22.5 |
| 25 | 2025-10-19 | 15.0 |

### Diamond Push-up

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 0.0 |
| 7 | 2025-09-13 | 0.0 |
| 13 | 2025-09-25 | 0.0 |
| 19 | 2025-10-07 | 0.0 |
| 25 | 2025-10-19 | 0.0 |
| 31 | 2025-10-31 | 0.0 |

### Lat Pulldown

| Session | Date | Weight (kg) |
|---|---|---|
| 2 | 2025-09-03 | 40.0 |
| 20 | 2025-10-09 | 30.0 |

### Farmer's Walk

| Session | Date | Weight (kg) |
|---|---|---|
| 2 | 2025-09-03 | 32.0 |
| 5 | 2025-09-09 | 26.0 |
| 8 | 2025-09-15 | 32.0 |
| 11 | 2025-09-21 | 18.0 |
| 14 | 2025-09-27 | 29.0 |
| 17 | 2025-10-03 | 32.0 |
| 20 | 2025-10-09 | 25.0 |
| 23 | 2025-10-15 | 19.0 |
| 26 | 2025-10-21 | 33.0 |
| 29 | 2025-10-27 | 25.0 |
| 32 | 2025-11-02 | 35.0 |
| 35 | 2025-11-08 | 19.0 |

### Dumbbell Curl

| Session | Date | Weight (kg) |
|---|---|---|
| 2 | 2025-09-03 | 46.0 |
| 11 | 2025-09-21 | 26.0 |
| 20 | 2025-10-09 | 35.0 |
| 29 | 2025-10-27 | 32.0 |

## Anomaly and Rollback Events

| Session | Date | Type | Details |
|---|---|---|---|
| 26 | 2025-10-21 | fault_injection | session_idx=25: anomaly model injected (RPE=1.0) |
| 26 | 2025-10-21 | anomaly_prediction | exercise_id=27 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
| 27 | 2025-10-23 | fault_injection | session_idx=26: anomaly model injected (RPE=1.0) |
| 27 | 2025-10-23 | anomaly_prediction | exercise_id=20 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
| 27 | 2025-10-23 | anomaly_prediction | exercise_id=35 delta=0.00kg source=[AI заблокирован: дельта 15% > 15% лимит] |
