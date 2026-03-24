# OpenGym Simulation Report

**Parameters:** 3 months, 3×/week, seed=42
**Total sessions simulated:** 36
**Total exercise decisions:** 120

## Source Label Distribution

| Category | Decisions | Percentage |
|---|---|---|
| AI (ML correction applied) | 87 | 72.5% |
| Anomaly (ML blocked) | 3 | 2.5% |
| Core (deterministic fallback) | 30 | 25.0% |

## RPE Model MAE Trend

| Window | MAE |
|---|---|
| Sessions 1–10 | 6.547 |
| Sessions 11–20 | 2.409 |
| Sessions 21–30 | 3.282 |
| Sessions 31–36 | 2.345 |

**MAE sessions 1–10:** 6.547
**MAE sessions 51+:** N/A

## Weight Progression (Sample Exercises)

### Bench Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 37.5 |
| 16 | 2025-10-01 | 30.0 |
| 31 | 2025-10-31 | 22.5 |

### Overhead Press

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 25.0 |
| 13 | 2025-09-25 | 17.5 |
| 25 | 2025-10-19 | 7.5 |

### Diamond Push-up

| Session | Date | Weight (kg) |
|---|---|---|
| 1 | 2025-09-01 | 0.0 |
| 7 | 2025-09-13 | 0.0 |
| 13 | 2025-09-25 | 0.0 |
| 19 | 2025-10-07 | 0.0 |
| 25 | 2025-10-19 | 0.0 |
| 31 | 2025-10-31 | 0.0 |

## Anomaly and Rollback Events

| Session | Date | Type | Details |
|---|---|---|---|
| 26 | 2025-10-21 | fault_injection | session_idx=25: anomaly model injected (RPE=1.0) |
| 26 | 2025-10-21 | anomaly_prediction | exercise_id=27 delta=0.00kg source=[AI заблокирован: дельта 17% > 15% лимит] |
| 27 | 2025-10-23 | fault_injection | session_idx=26: anomaly model injected (RPE=1.0) |
| 27 | 2025-10-23 | anomaly_prediction | exercise_id=20 delta=0.00kg source=[AI заблокирован: дельта 17% > 15% лимит] |
| 27 | 2025-10-23 | anomaly_prediction | exercise_id=35 delta=0.00kg source=[AI заблокирован: дельта 17% > 15% лимит] |
