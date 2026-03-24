# Slot-Based Planner Tech Spec

## Purpose

This document defines the target architecture and implementation requirements for the next iteration of `WorkoutPlanner`.

The goal is to move from the current muscle-group-first heuristic planner to a slot-based planner that:

- adapts to changing athlete parameters
- adapts to changing equipment inventory
- preserves program balance and progression continuity
- supports ML-assisted personalization without giving up deterministic safety constraints

This document is written as implementation-facing technical guidance for a programmer working inside the current `gym-coach-brain` codebase.

## Problem Statement

The current planner has improved substantially, but it still has structural limitations:

- it starts from muscle groups instead of training slots
- it treats exercise selection and program structure as the same problem
- anchor stability and variation are handled through heuristics instead of explicit rules
- support muscles are added through coverage heuristics, but their role in the day is not first-class
- exercise prescription still depends too much on generic exercise metadata instead of program role
- ML personalization is currently better suited for adaptation/progression than for initial plan construction

As a result, the planner is still too brittle when:

- equipment changes
- split changes
- athlete goal changes
- training frequency changes
- exercise tolerance differs per athlete
- progression continuity must be maintained across weeks

## Target Outcome

Replace the core planning model with a slot-based planning system.

Instead of:

- choose muscle groups for the day
- choose one exercise per group
- add support coverage heuristically

The planner should do:

1. Determine the day template.
2. Build required and optional slots for that day.
3. Enumerate candidate exercises for each slot, constrained by equipment and safety rules.
4. Score candidates using deterministic and ML-assisted signals.
5. Select exercises per slot.
6. Assign prescription based on slot role.
7. Validate final plan against PUOS, balance, rest, and recovery constraints.

## Non-Goals

This phase does not require:

- replacing deterministic safety logic with ML
- LLM-generated programming (LLM is conversation layer only; planner remains rule-based)
- free-form natural-language planning inside the core planner
- mesocycle generation across multiple weeks
- auto-writing full periodized blocks
- direct modification of slot selection via conversation layer

This phase is about building a strong single-session planner architecture that can evolve safely.

**Note:** Free-form conversation is handled by the conversation layer (`bot/agent.py`). The conversation layer translates human language into planner events, NOT directly into slot selections. This separation ensures deterministic, auditable planning decisions.

## Design Principles

### 1. Deterministic Safety Boundary

The following must remain rule-based and hard-constrained:

- exercise availability from concrete inventory
- equipment legality
- split-day structure
- rest-day constraints
- PUOS/session volume limits
- antagonist balance checks
- fallback when ML confidence is low

### 2. Slot-First Planning

Each training day must be represented as a set of slots, not a flat list of muscle groups.

Examples:

- `upper_primary_push`
- `upper_primary_pull`
- `upper_secondary_push_pull`
- `upper_arm_or_trap_accessory`
- `lower_primary_knee`
- `lower_primary_hinge`
- `lower_secondary_lower`
- `core_slot`
- `calves_slot`

### 3. Role-Based Prescription

Sets, rep ranges, and progression behavior should be assigned by slot role, not only by `Exercise.is_compound` or movement pattern.

### 4. Separation Of Concerns

The planner should separate:

- day structure generation
- candidate enumeration
- scoring/ranking
- exercise selection
- prescription
- validation

### 5. ML As Scoring Layer, Not Safety Layer

ML should rank and tune choices inside an allowed corridor, not bypass hard constraints.

## Adaptation Boundary

Clarifies when the Adaptation Engine interacts with the Planner.

### Two-Phase Adaptation Pattern

**Phase 1: Pre-Planning Adaptation (Readiness-Aware Slot Selection)**

Before session planning begins, the system evaluates athlete readiness:

```
athlete_readiness_signal → slot_modification → modified_day_template
```

Examples:
- `readiness_signal.coefficient < 0.7` → suppress optional slots, reduce prescription intensity
- `athlete.skipped_last_session` → apply detraining coefficient, shift to maintenance load
- `athlete.reported_pain(muscle)` → exclude slot targeting that muscle, find safe alternative

**Phase 2: Post-Planning Adaptation (Weight/Rep Adaptation)**

After plan is generated, Adaptation Engine adjusts weights/reps:

```
planned_session → adaptation_engine → adapted_session
```

This is the existing flow in `adaptation/engine.py`.

### Pre-Planning Signals

The Planner must accept these pre-planning inputs:

| Signal | Source | Effect on Planner |
|--------|--------|-------------------|
| `recovery_signal` | readiness_log + HRV | Slot suppression, prescription reduction |
| `skipped_sessions` | session_history | Detraining coefficient, shift to maintenance |
| `pain_report` | conversation layer | Exclude affected muscle slots |
| `equipment_change` | profile update | Fallback ladder activation |

**Implementation note:** Pre-planning adaptation outputs a `PlanningContext` object that modifies slot selection but does NOT alter hard safety constraints (rest days, PUOS limits).

## Proposed Architecture

## Core Planner Pipeline

Target `WorkoutPlanner.generate(...)` flow:

1. Resolve active split day.
2. Resolve day template.
3. Build slots for this day.
4. For each slot:
   - enumerate candidate exercises
   - compute deterministic features
   - optionally compute ML score
   - choose best candidate
5. Assign slot prescription.
6. Build `PlannedExercise[]`.
7. Run validation/reduction passes.
8. Return `WorkoutPlan`.

## New Planner Concepts

### Day Template

Defines which slots exist for a session under a given split and frequency.

Examples:

#### `upper_lower` upper day

- `upper_primary_push`
- `upper_primary_pull`
- `upper_secondary_upper`
- `upper_optional_support_1`
- `upper_optional_support_2`

#### `upper_lower` lower day

- `lower_primary_knee`
- `lower_primary_hinge`
- `lower_secondary_lower`
- `core_slot`
- `calves_slot`

#### `ppl` push day

- `push_primary_horizontal`
- `push_primary_vertical`
- `push_secondary_push`
- `push_optional_triceps`

#### `ppl` pull day

- `pull_primary_vertical`
- `pull_primary_row`
- `pull_secondary_pull`
- `pull_optional_biceps_or_traps`

#### `ppl` legs day

- `legs_primary_knee`
- `legs_primary_hinge`
- `legs_secondary_lower`
- `core_slot`
- `calves_slot`

### Slot

A slot is a role in a training day.

Each slot should define:

- `slot_id`
- `required: bool`
- `priority`
- `target_regions`
- `target_muscles`
- `movement_preferences`
- `exercise_family_preferences`
- `fallback_policy`
- `anchor_policy`
- `prescription_policy`
- `max_exercises_for_role` (usually 1)

### Exercise Family

Introduce a higher-level classification above raw movement pattern.

Examples:

- `chest_press`
- `incline_press`
- `vertical_press`
- `vertical_pull`
- `horizontal_row`
- `knee_dominant_machine`
- `knee_dominant_free`
- `hip_hinge_barbell`
- `hip_extension_bridge`
- `arm_flexion`
- `arm_extension`
- `carry`
- `trunk_bracing`
- `spinal_extension`

This is needed because:

- movement pattern alone is too coarse
- primary muscle alone is not enough to represent exercise role

## Candidate Enumeration

For each slot, candidate exercises should be built from the exercise library using:

- concrete inventory availability
- broad equipment availability
- slot movement preferences
- slot family preferences
- split-day compatibility
- rest-day compatibility
- recent usage history
- previous anchor state

Candidate enumeration must support fallbacks.

Example:

`lower_primary_knee` fallback order:

1. `Smith Squat`
2. `Barbell Squat`
3. `Leg Press`
4. `Bulgarian Split Squat`
5. `Bodyweight Squat`

This must be driven by slot rules plus available candidates, not hardcoded for one athlete.

## Equipment Coverage Model

### Concrete vs Broad Inventory

The planner distinguishes:

- **Concrete inventory**: Specific equipment items athlete owns (e.g., `smith_machine`, `leg_curl_machine`)
- **Broad availability**: Equipment type available at training location (e.g., `machine`, `barbell`)

```python
# Example: athlete profile
available_equipment: ["barbell", "dumbbell", "pullup_bar", "dips_bar"]
available_equipment_inventory: ["smith_machine", "leg_curl_machine"]
```

### Fallback Ladder Structure

Fallback chains are **declarative**, not procedural:

```yaml
# In slot definition
lower_primary_knee:
  fallback_chain:
    - equipment_constraint: smith_machine  # requires concrete inventory item
      exercise_family: knee_dominant_machine
    - equipment_constraint: barbell
      exercise_family: knee_dominant_free
    - equipment_constraint: bodyweight
      exercise_family: knee_dominant_machine
  allow_partial_coverage: false  # if true, accept lower fractional stimulus
```

### Biomechanical Profile Matching

When selecting fallback, the system should consider **biomechanical similarity**:

| Primary Choice | Fallback 1 | Fallback 2 | Fallback 3 |
|---------------|------------|------------|------------|
| Barbell Squat | Smith Squat (same bar path, guided) | Leg Press (different angle) | Bulgarian Split Squat (unilateral, different load) |

**Principle:** Later fallbacks may have lower fractional contribution → triggers Coverage Gap Detection.

### Equipment-Aware Coverage Calculation

When computing weekly fractional sets:

```python
def fractional_contribution(exercise, slot_role, available_inventory):
    base = FRACTIONAL_MAP[slot_role][exercise.primary_muscle_role]
    
    if exercise.requires_concrete_inventory:
        if exercise.concrete_item not in available_inventory:
            return 0.0  # Cannot use this exercise
    
    if exercise.equipment_type not in available_equipment_types:
        return 0.0  # Cannot use this equipment category
    
    return base * EQUIPMENT_QUALITY_MULTIPLIER[exercise.equipment_type]
```

### Equipment Quality Multiplier

Different equipment types have different effectiveness multipliers (evidence-informed):

| Equipment Type | Quality Multiplier | Rationale |
|---------------|-------------------|-----------|
| Barbell | 1.0 | Gold standard |
| Dumbbell | 0.95 | Slightly less stable |
| Machine | 0.90 | Guided path, less stabilizer demand |
| Cable | 0.95 | Constant tension |
| Bodyweight | 0.85 | Often limited by skill/load |
| Resistance Band | 0.80 | Variable tension curve |

**Note:** These multipliers affect fractional volume calculation, not selection priority.

### Home vs Gym Environment

The planner must adapt for training environment:

```python
@dataclass
class TrainingEnvironment:
    is_home: bool
    available_equipment: list[EquipmentType]
    available_inventory: list[str]  # concrete items
    
# Environment-aware planning
def filter_candidates(candidates, environment):
    if environment.is_home:
        # Reject gym-only equipment
        return [c for c in candidates if c.equipment_type.available_home]
    else:
        # Gym environment - use full inventory
        return candidates
```

### Implementation Requirements

1. Add `requires_concrete_inventory: bool` field to Exercise metadata
2. Add `concrete_item_id: str | None` to exercises that need specific equipment
3. Update `CoverageAnalyzer` to compute equipment-aware fractional contribution
4. Planner must receive `TrainingEnvironment` in planning context

## Coverage Gap Detection

### Problem

When equipment is missing, the fallback ladder provides a substitution, but does NOT guarantee the muscle group receives adequate weekly volume.

**Example:**
- Athlete has no cable machine
- `push_secondary_push` slot gets bodyweight Diamond Push-up instead of Cable Fly
- Diamond Push-up loads chest @ 0.5 fractional (synergist) not 1.0 (primary)
- Chest weekly volume is now deficient despite "having" the slot filled

### Coverage Gap Model

Introduce a `CoverageAnalyzer` that runs after planning:

```
weekly_plan → coverage_analysis → gap_report → planner_adjustment
```

### Gap Detection Algorithm

For each muscle group in the weekly plan:

1. **Sum fractional sets** across all sessions using `ScienceEvidence.weekly_volume_landmarks`:
   ```
   total_fractional_sets[muscle] = Σ(session.slots.exercises.fractional_contribution)
   ```

2. **Compare against MEV** (Minimum Effective Volume):
   ```
   if total_fractional_sets[muscle] < mev:
       gap_detected = True
       gap_severity = mev - total_fractional_sets[muscle]
   ```

3. **Gap Classification**:
   - `minor_gap` (MEV > total >= MV): maintenance volume not reached, warn only
   - `significant_gap` (total < MEV): effective volume not reached, trigger adjustment
   - `critical_gap` (total < MV): below minimum, require intervention

### Gap Resolution Strategies

| Gap Severity | Resolution Action |
|--------------|------------------|
| `minor_gap` | Log warning, no action |
| `significant_gap` | Activate suppressed optional slot OR increase prescription intensity |
| `critical_gap` | Force equipment-free alternative OR suggest equipment acquisition |

### Coverage Gap Resolution Examples

**Scenario: Athlete has no cable machine, chest coverage gap detected**

1. System detects: weekly chest fractional sets = 8.0, MEV = 10.0
2. Resolution: activate `upper_optional_support_3` slot with isolation movement (e.g., Dumbbell Fly)
3. Result: chest coverage restored to MEV range

**Scenario: Athlete has no leg extension machine, quad coverage gap**

1. System detects: weekly quad fractional sets = 10.0, MEV = 8.0 → NO GAP
2. Bodyweight squat provides sufficient quad stimulus as primary (1.0 fractional)
3. No intervention needed

**Scenario: Athlete lacks equipment for all hinge slots**

1. System detects: no exercise with `hinge` movement available
2. Hip Thrust (bodyweight) available → fallback
3. Glutes/hamstrings still get stimulus from squat variants (glutes are secondary in squat)
4. If coverage still insufficient → critical_gap → surface to athlete: "Consider adding glute-focused equipment"

### Implementation Notes

- `CoverageAnalyzer` runs after weekly plan is generated, before session execution
- Results stored in `CoverageGapReport` with muscle/gap_severity/resolution_action
- Gaps surfaced to athlete via conversation layer (friendly language, not technical)
- Resolution actions may trigger re-planning for affected sessions

## Anchor And Variation Policy

Exercise continuity should be explicit.

Each slot needs an anchor policy:

- `stable`: prefer repeating same exercise for 4-6 exposures
- `semi_stable`: repeat unless recovery/tolerance/coverage suggests change
- `free_rotation`: rotate among top candidates

Recommended defaults:

- primary lower slots: `stable`
- primary upper slots: `semi_stable`
- secondary lower/upper slots: `semi_stable`
- accessory slots: `free_rotation`
- core/carry slots: `free_rotation`

Anchor selection must be slot-aware, not only “recently used”.

## Prescription Policy

Prescription should be attached to slot role.

Suggested first-pass defaults:

- primary upper slot: `3-4 x 6-12`
- primary lower slot: `3-4 x 6-10`
- secondary compound slot: `3-4 x 8-12`
- isolation accessory slot: `2-4 x 8-15`
- arms slot: `2-4 x 8-15`
- calves slot: `2-4 x 10-20`
- core slot: `2-4 x 10-20` or time-based policy
- carry slot: `2-4` work bouts, ideally distance/time rather than reps

Important:

- `carry` and `timed core` should not be represented forever as classic rep-range lifts
- this phase may still store them as rep ranges for compatibility, but the architecture should leave room for a later `prescription_mode` field:
  - `reps`
  - `seconds`
  - `distance`

## Deterministic Scoring

Before ML is added to planner decisions, deterministic scoring should be explicit.

Suggested score components:

- `availability_score`
- `slot_fit_score`
- `anchor_score`
- `fatigue_cost_score`
- `novelty_score`
- `equipment_preference_score`
- `secondary_coverage_score`
- `progression_continuity_score`

Candidate score can be modeled as:

`total_score = weighted_sum(...)`

This scoring function should be implemented in a separable helper module so that ML can later augment or replace only part of the ranking.

## ML Integration Plan

## ML Role

ML should score candidates and tune prescription inside deterministic boundaries.

It should not:

- select unavailable exercises
- violate rest constraints
- violate PUOS limits
- create unsupported slot structures

## Planner ML Hook

Add a planner-facing scoring hook, conceptually:

```python
score = planner_scorer.score_candidate(
    athlete_profile=...,
    slot=...,
    exercise=...,
    history=...,
    recovery_signal=...,
)
```

Return shape:

```python
{
  "score": 0.0,
  "confidence": 0.0,
  "stimulus_score": 0.0,
  "fatigue_score": 0.0,
  "adherence_score": 0.0,
  "novelty_score": 0.0,
  "explanation_tags": [...]
}
```

If confidence is below threshold, planner must fall back to deterministic ranking.

## ML Prescription Hook

Separate from candidate selection:

```python
prescription = planner_scorer.score_prescription(
    athlete_profile=...,
    slot=...,
    chosen_exercise=...,
    recovery_signal=...,
    history=...,
)
```

Boundaries must still be deterministic:

- sets must stay within slot min/max
- rep ranges must stay within allowed ranges for the slot
- progression deltas must still respect existing safety caps

## Required Features For ML Candidate Scoring

At minimum, planner-scoring features should include:

- athlete age
- bodyweight
- goal
- experience level
- training frequency
- split type
- current day slot
- exercise family
- movement pattern
- primary muscle
- equipment type
- concrete inventory match quality
- days since last use of exercise
- days since last use of exercise family
- days since last exposure of primary muscle
- recent performance trend on exercise
- recent performance trend on family
- recent recovery score
- current session volume state
- historical tolerance / anomaly flags
- adherence / skipped-session behavior

## Data Model Changes

## New Fields Or Tables

At minimum, implementation should introduce some combination of:

### Exercise metadata expansion

Add fields or derived metadata for:

- `exercise_family`
- `slot_tags`
- `prescription_mode`

### Session planning trace

Persist slot-level planning context in planned session payload:

- `slot_id`
- `selection_reason`
- `anchor_state`
- `candidate_score`
- `selection_source` (`deterministic` or `ml`)

### Optional planner state table

If needed, add planner continuity state:

- current anchor exercise per slot
- anchor age
- last anchor switch reason

This can also initially be reconstructed from session history if preferred.

## Compatibility Requirements

The refactor must preserve:

- current `WorkoutPlan` public contract unless explicitly migrated
- current adaptation pipeline compatibility
- current workout session persistence contract
- ability to run existing ML worker without planner-side ML scoring enabled

If any schema changes are required, add migrations and keep default behavior backward compatible.

## Conversation Layer Integration

### Purpose

The slot-based planner is a backend module. The conversation layer (LLM agent) is the frontend. This section defines integration points for "free-form language without commands."

### User Message → Planner Event Mapping

When athlete speaks freely, the conversation layer must extract structured events:

| Athlete Message (examples) | Conversation Layer Action | Planner Event |
|---------------------------|-------------------------|--------------|
| "вчера на deadlift спина странно ощущалась" | Extract: `pain_report(muscle=lower_back)` | `pre_planning_modification` → exclude hinge slots |
| "сегодня не выспался, устал" | Extract: `readiness_signal(recovery_coeff=0.6)` | `pre_planning_modification` → suppress optional slots |
| "пропустил тренировку в среду" | Extract: `skipped_session(date=2026-03-22)` | `detraining_check` → apply 0.85 coefficient |
| "сделал больше повторов чем написано" | Extract: `performance_report(exercise=deadlift, reps=10 vs planned=8)` | `adaptation_feedback` → tune future prescription |
| "хочу попробовать новое упражнение на плечи" | Extract: `preference_request(slot=upper_primary_push, family=vertical_press)` | `slot_candidate_preference` |

### Conversation Layer Responsibilities

The LLM agent (see `bot/agent.py` and `bot/prompts/system.md`) must:

1. **Parse intent** from free-form Russian text
2. **Call tools** to persist structured events to backend
3. **Surface feedback** in human-friendly language

**Do NOT** expect the conversation layer to know:
- Slot IDs
- Exercise internal names
- Technical planning parameters

### Planner Event Types

```python
@dataclass
class PlannerEvent:
    event_type: str  # pain_report | readiness_override | skipped_session | performance_feedback | preference_request
    timestamp: datetime
    data: dict  # event-specific payload
    athlete_id: int
```

### Event Processing Pipeline

```
conversation_layer (LLM) 
    → tool_executor.execute(event=PlannerEvent)
    → state_store.update(event)
    → on next workout_start:
        → planner.generate(context=state.get_planning_context())
        → state.get_recent_events() influences pre-planning adaptation
```

### Feedback Loop Example

**Athlete:** "вчерашний жим лёжа показался лёгким, сделал все 12 повторений а не 10"

**Conversation layer actions:**
1. Extract: `performance_feedback(exercise=bench_press, achieved_reps=12, planned_reps=10)`
2. Call `workout_log_set` with actual data
3. Planner stores in session history

**Next session planning:**
1. Adaptation engine sees: bench_press last session RPE was easy (12 reps @ same weight = low RPE)
2. On next bench_press slot: increase target weight slightly OR increase target reps
3. Explanation surfaced: "Жим лёжа вчера дался легко — сегодня возьмём вес чуть больше"

### Skipped Session Handling

When athlete skips a session:

1. Conversation layer logs: `skipped_session(date, split_day_label, reason_if_given)`
2. Planner applies detraining logic at next planning:
   ```
   if days_since_last_session[muscle] > detraining_threshold_days:
       apply_deload_coefficient(0.85)
       flag_for_recovery_loading
   ```
3. Progression may reset to lower weight OR continue depending on gap duration

### Conversation-to-Planner Data Flow

```
Athlete Message
    │
    ▼
┌─────────────────────────┐
│  Conversation Layer     │
│  (LLM + Tool Executor)  │
└────────┬────────────────┘
         │ tool calls (workout_log_set, readiness_log, etc.)
         ▼
┌─────────────────────────┐
│  State Store            │
│  (UserState in bot/)    │
└────────┬────────────────┘
         │ on workout_start
         ▼
┌─────────────────────────┐
│  Planner                │
│  (reads planning context│
│   + recent events)      │
└────────┬────────────────┘
         │ generates session
         ▼
┌─────────────────────────┐
│  Adaptation Engine      │
│  (weight/rep tuning)    │
└────────┬────────────────┘
         │ adapted plan
         ▼
┌─────────────────────────┐
│  Conversation Layer      │
│  (presents to athlete)   │
└─────────────────────────┘
```

### Non-Goals for Conversation Layer

- The conversation layer does NOT directly select exercises or modify prescriptions
- It translates human intent into planner events
- All planning decisions remain backend responsibility

## Acceptance Criteria

## Functional

1. Planner builds sessions from explicit slots, not only muscle groups.
2. Lower and upper days maintain stable primaries while allowing controlled variation.
3. Support groups are added based on slot logic and coverage, not naive one-group-one-exercise rules.
4. Equipment changes alter candidate availability without changing planner architecture.
5. Athlete profile changes alter slot/prescription selection appropriately.
6. Bodyweight fallback remains supported when equipment does not fully cover required roles.
7. Core/carry slots are handled distinctly from standard compound/isolation lifts.
8. **Coverage gaps detected when equipment missing causes weekly volume below MEV.**
9. **Pre-planning adaptation modifies slot selection based on readiness/skipped sessions/pain reports.**
10. **Equipment changes trigger fallback within 2 sessions and restoration within 2 sessions.**

## Quality

1. Deterministic fallback exists for all ML-assisted decisions.
2. Planner behavior remains reproducible given the same inputs.
3. Full test suite remains green.
4. Simulation health gates remain green.
5. The algorithm improves continuity of lower-body progression compared to the current heuristic-only rotation.

## Simulation Health Gates

### Purpose

Simulation validates the planner algorithm WITHOUT waiting 3 months of real athlete data. Health gates define pass/fail criteria for simulation runs.

### Simulation Health Metrics

Each simulation run (typically 12-week synthetic athlete) must pass ALL gates:

#### Gate 1: Volume Integrity

```
PASS: For each muscle group, weekly fractional sets stay within [MV, MRV] for ≥80% of simulation weeks
FAIL: Any muscle group stays below MV for >2 consecutive weeks
```

Rationale: Prolonged under-training indicates coverage gaps or recovery violations.

#### Gate 2: Progression Continuity

```
PASS: Lower body primary exercises show weight increase in ≥70% of simulation weeks
FAIL: Weight stagnation (no increase) for >4 consecutive weeks without deload explanation
```

Rationale: Algorithm should drive progressive overload unless blocked by fatigue management.

#### Gate 3: Recovery Compliance

```
PASS: Rest day constraints (min_rest_days_per_muscle_group) violated ≤5% of simulation sessions
FAIL: Rest constraint violations >5% of sessions
```

Rationale: Hard constraints must be respected; violations indicate slot builder or day template errors.

#### Gate 4: Equipment Adaptation

```
PASS: When equipment is removed from inventory, fallback to bodyweight within 2 sessions
PASS: When equipment is restored, returns to equipment-based exercise within 2 sessions
FAIL: Athlete continues without valid exercise for slot for >2 sessions
```

Rationale: Fallback ladder must activate quickly and restore continuity.

#### Gate 5: Adaptation Quality

```
PASS: RPE predictions stay within [rpe_easy_threshold, rpe_hard_threshold] for ≥60% of working sets
FAIL: >40% of sets outside target RPE range consistently
```

Rationale: APRE/double progression should keep athlete in target RPE zone.

#### Gate 6: Coverage Gap Recovery

```
PASS: Any significant_gap detected is resolved within 3 sessions
FAIL: Coverage gap persists for >3 sessions without resolution
```

Rationale: CoverageAnalyzer must trigger effective corrections.

### Simulation Output Schema

Each simulation run produces:

```yaml
health_gate_results:
  volume_integrity: {status: "PASS"|"FAIL", details: {...}}
  progression_continuity: {status: "PASS"|"FAIL", details: {...}}
  recovery_compliance: {status: "PASS"|"FAIL", details: {...}}
  equipment_adaptation: {status: "PASS"|"FAIL", details: {...}}
  adaptation_quality: {status: "PASS"|"FAIL", details: {...}}
  coverage_gap_recovery: {status: "PASS"|"FAIL", details: {...}}

overall_status: "PASS" (all gates PASS) | "CONDITIONAL_PASS" (non-critical failures) | "FAIL"

summary:
  total_sessions: int
  total_muscle_groups_tracked: int
  weeks_at_target_volume_pct: float
  avg_rpe: float
  progression_events: int
  coverage_gaps_detected: int
  coverage_gaps_resolved: int
```

### Gate Severity Classification

| Gate | Severity | Block Merge If |
|------|----------|----------------|
| Volume Integrity | CRITICAL | FAIL |
| Recovery Compliance | CRITICAL | FAIL |
| Equipment Adaptation | HIGH | FAIL |
| Progression Continuity | MEDIUM | CONDITIONAL_PASS |
| Adaptation Quality | MEDIUM | CONDITIONAL_PASS |
| Coverage Gap Recovery | HIGH | FAIL |

### Running Simulations

```bash
# Full health gate validation
cd gym-coach-brain
uv run python -m gym_coach_brain.simulation.run --health-gates

# Specific split testing
uv run python -m gym_coach_brain.simulation.run --split=upper_lower --weeks=12 --health-gates

# Compare slot-based vs heuristic (before/after)
uv run python -m gym_coach_brain.simulation.run --compare=slot_based,heuristic --metric=progression_continuity
```

## Testing Requirements

Add or update tests for:

- slot construction per split/day
- candidate enumeration per slot
- fallback ladder behavior with changing equipment
- anchor stability for primary slots
- free rotation for accessory slots
- support-slot suppression when secondary coverage is sufficient
- support-slot activation when secondary coverage is insufficient
- slot-based prescription assignment
- core/carry prescription behavior
- ML fallback behavior on low confidence
- simulation health-gate compatibility
- **equipment continuity**: athlete has partial inventory → gets bodyweight exercise → full inventory restored → returns to equipment-based exercise within 2 sessions
- **coverage gap detection**: missing equipment causes weekly volume below MEV → gap detected → resolved within 3 sessions
- **pre-planning adaptation**: low readiness signal → optional slots suppressed → prescription intensity reduced

## Implementation Plan

Recommended implementation order:

1. Introduce slot definitions and planner slot builder.
2. Add exercise-family metadata + equipment coverage fields.
3. Refactor planner selection to slot-first deterministic scoring.
4. Move current heuristics into slot-aware deterministic scoring functions.
5. Add anchor policy handling.
6. Add slot-based prescription logic.
7. Add planning trace metadata.
8. Add CoverageAnalyzer + coverage gap detection.
9. Add pre-planning adaptation signals (readiness-aware slot modification).
10. Add optional ML candidate scoring hook behind a feature flag or optional dependency.
11. Update simulations with health gate validation.
12. Update tests including new equipment continuity and coverage gap scenarios.

## Suggested File-Level Changes

Expected touch points:

- `src/gym_coach_brain/core/planner.py`
- new module: `src/gym_coach_brain/core/planner_slots.py`
- new module: `src/gym_coach_brain/core/planner_scoring.py`
- new module: `src/gym_coach_brain/core/planner_prescription.py`
- new module: `src/gym_coach_brain/core/planner_coverage.py` (CoverageAnalyzer + gap detection)
- new module: `src/gym_coach_brain/core/planner_adaptation.py` (pre-planning adaptation signals)
- possibly new module: `src/gym_coach_brain/core/planner_ml.py`
- `src/gym_coach_brain/data/models.py` (add coverage fields, concrete_inventory, equipment quality)
- `src/gym_coach_brain/data/seed.py` (update exercise metadata)
- `src/gym_coach_brain/bot/state.py` (PlannerEvent storage + retrieval)
- simulation tests and planner tests

## Definition Of Done

The work is done when:

- the planner is slot-based
- the design is inventory-agnostic and athlete-agnostic
- deterministic safety constraints remain enforced
- the algorithm supports future ML scoring cleanly
- tests and simulation health gates pass

