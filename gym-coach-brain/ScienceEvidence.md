---
version: "1.0.0"

puos:
  max_sets_per_group: 10       # int — PUOS limit: max fractional sets per muscle group per session (Israetel 2018)
  smh_volume_multiplier: 1.2   # float — SMH multiplier; evidence-informed heuristic (Israetel 1.2–1.3)

progression:
  compound_increment_kg: 2.5   # float — weight increment for compound/barbell exercises
  isolation_increment_kg: 1.25 # float — weight increment for isolation exercises
  apre_6_step_min_kg: 2.5      # float — APRE-6 base adjustment step (Knight 1979); 5 lbs = 2.5 kg
  apre_6_step_max_kg: 5.0      # float — APRE-6 maximum adjustment step (Knight 1979); 10 lbs = 5 kg
  hypertrophy_rep_min: 6       # int — double progression bottom of hypertrophy rep range (Schoenfeld & Grgic 2021, PMC7927075)
  hypertrophy_rep_max: 12      # int — double progression top of hypertrophy rep range (Schoenfeld & Grgic 2021, PMC7927075)

recovery:
  # Readiness weights for formula: score = sum(weight * component). TOTAL SUM MUST BE 1.0
  hrv_weight: 0.5              # float — HRV weight (Kiviniemi 2007; most objective metric)
  sleep_weight: 0.3            # float — sleep weight (moderate objectivity)
  stress_weight: 0.2           # float — stress weight (most subjective; lowest weight)

exercises: {}                  # dict — exercise overrides. Example: {"deadlift": {"smh_eligible": false}}

methodologies:
  strength:
    rep_min: 1                 # int — minimum reps (Schoenfeld & Grgic 2021, PMC7927075)
    rep_max: 5                 # int — maximum reps
    frequency_per_week_min: 2  # int — min training sessions per muscle group per week
    frequency_per_week_max: 4  # int — max training sessions per muscle group per week
  hypertrophy:
    rep_min: 6                 # int — minimum reps (Schoenfeld & Grgic 2021, PMC7927075)
    rep_max: 12                # int — maximum reps
    frequency_per_week_min: 2  # int — min training sessions per muscle group per week
    frequency_per_week_max: 4  # int — max training sessions per muscle group per week
  endurance:
    rep_min: 15                # int — minimum reps (Schoenfeld & Grgic 2021, PMC7927075)
    rep_max: 30                # int — maximum reps
    frequency_per_week_min: 3  # int — min training sessions per muscle group per week
    frequency_per_week_max: 5  # int — max training sessions per muscle group per week

planning:
  min_rest_days_per_muscle_group: 2  # int — min rest days (isolation; Monteiro 2018, PMC6015912; 48h = 2 days)
  min_rest_days_compound: 3          # int — min rest days (multi-joint; De Salles 2010, PMC6719818; 72h = 3 days)
---

# ScienceEvidence

Scientific methodology rulebook for gym-coach-brain.
YAML frontmatter: structured data (limits, coefficients, version) parsed at startup into ScienceConfig.
Markdown body: human-readable scientific justifications for each parameter.

<!-- Verification (run from within gym-coach-brain/ dir): uv run python -c "from gym_coach_brain.core.science import load_science_config; print(load_science_config())" -->
<!-- Standalone YAML check (run from within gym-coach-brain/ dir): uv run python -c "import yaml, re; raw=open('ScienceEvidence.md').read(); m=re.match(r'^---\s*\n(.*?)\n---\s*\n', raw, re.DOTALL); print(yaml.safe_load(m.group(1)))" -->

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 1.0.0 | 2026-03-04 | Initial production coefficients; all fields populated from domain-sports-science-research-2026-03-04.md |
| 0.0.0 | 2026-03-02 | Skeleton with placeholder values (Story 1.2) |

## PUOS — Per-Unique-Output-per-Session

Parameters controlling Per-Unique-Output-per-Session volume limits.

### max_sets_per_group

**Value: 10 fractional sets per muscle group per session**

PUOS (Point of Undetectable Outcome Superiority) defines the threshold beyond which additional sets in a single session produce no measurable additional hypertrophic benefit and increase injury/recovery risk.

Research indicates a threshold of approximately **10–11 fractional sets** per muscle group per session (Israetel, M. — RP Strength, Renaissance Periodization series). The value of **10** is the conservative lower bound of this range.

**Fractional volume system:**
- 1.0 — primary (agonist) muscle directly targeted
- 0.5 — synergist receiving secondary stimulus
- 0 — stabilizer (isometric, not counted)

Source: Israetel, M. (2019). *Scientific Principles of Strength Training.* Renaissance Periodization.

### smh_volume_multiplier

**Value: 1.2 (evidence-informed heuristic)**

SMH (Stretch-Mediated Hypertrophy) refers to exercises where peak mechanical tension occurs at maximal muscle length (e.g., Romanian Deadlift for hamstrings, cable flyes for chest, incline curls for biceps). Research demonstrates that training muscles in the lengthened/stretched position produces **equal or greater hypertrophy** vs. full ROM.

The multiplier of **1.2** represents the conservative lower bound of Israetel's stated range (1.2–1.3).

**Evidence classification:**
- Direction of effect (SMH >= non-SMH): **PEER-REVIEWED** — 5 published RCTs (Oranchuk 2019; Werkhausen 2021; PMC10587333)
- Specific multiplier 1.2: **EVIDENCE-INFORMED HEURISTIC** — Israetel coaching estimate; not derived from a single RCT

Sources: Israetel, M. (2023). RP Strength. PMC10587333 — Physiology of Stretch-Mediated Hypertrophy.

## Progression Protocols

Parameters for linear and auto-regulated (APRE) progression schemes.

### APRE-6 Adjustment Steps

**Values: apre_6_step_min_kg = 2.5, apre_6_step_max_kg = 5.0**

APRE-6 (Auto-Regulatory Progressive Resistance Exercise, 6-rep target) uses a 4-set structure where Set 3 and Set 4 are performed to failure (AMRAP). Weight adjustments follow Knight's (1979) original table, originally specified in pounds.

**Metric conversion:** 5 lbs = 2.5 kg; 10 lbs = 5.0 kg (standard barbell plate rounding).

APRE-6 Next-Session Adjustment (based on Set 4 reps):
- 4 reps or fewer: -apre_6_step_max_kg (decrease)
- 5-7 reps: no change (this is the 6RM target)
- 8-10 reps: +apre_6_step_min_kg
- 11 reps or more: +apre_6_step_max_kg

Sources: Knight, K.L. (1979). AJSM, 7(6), 336-337. Mann, J.B. et al. (2010). JSCR, 24(7), 1718-1723 (PubMed 20543732).

### Double Progression Rep Ranges

**Hypertrophy values: rep_min = 6, rep_max = 12**

Double Progression = progressive overload on two variables: reps (within a target range) then weight (when top of range is achieved for all sets).

The 6-12 rep range for hypertrophy reflects the traditional hypertrophy zone, while Schoenfeld & Grgic (2021) demonstrate that equivalent hypertrophy occurs across a wide spectrum (6-30+) when training to near-failure. The 6-12 range is used as the practical default for double progression as it provides sufficient mechanical tension while allowing consistent rep performance.

Source: Schoenfeld, B.J. & Grgic, J. (2021). "Loading Recommendations for Muscle Strength, Hypertrophy, and Local Endurance: A Re-Examination of the Repetition Continuum." *Sports*, 9(2), 32. DOI: 10.3390/sports9020032. PMC7927075.

### Weight Increments

**Values: compound = 2.5 kg, isolation = 1.25 kg**

Standard barbell plate increments for progressive overload:
- **Compound (barbell exercises):** 2.5 kg — smallest standard barbell plate; minimum meaningful load increment
- **Isolation (small muscle groups):** 1.25 kg — micro-plates; prevents stalling due to large percentage jumps (e.g., lateral raises where 2.5 kg = 25% increase)

Sources: Rippetoe, M. & Kilgore, L. (2011). *Starting Strength* (3rd ed.). Schoenfeld & Grgic (2021) — increment guidance.

## Recovery Coefficients

Weights for composite readiness score: `readiness = hrv_component*hrv_weight + sleep_component*sleep_weight + stress_component*stress_weight`. Formula requires normalized weights (sum = 1.0).

### Composite Readiness Formula

**Values: hrv_weight = 0.5, sleep_weight = 0.3, stress_weight = 0.2**

`readiness_score = (hrv_component x 0.5) + (sleep_component x 0.3) + (stress_component x 0.2)`

Where each component is normalized 0.0-1.0 (1.0 = optimal). Volume multiplier: `planned_volume x readiness_score`.

**Weight rationale:**
- **HRV (0.5):** Highest weight due to strongest evidence base; most objective physiological readiness metric. 7-day rolling average of morning resting lnRMSSD.
- **Sleep (0.3):** Moderate weight; sleep quality directly impacts performance and recovery. Self-report bias possible.
- **Stress (0.2):** Lowest weight; most subjective; included as lifestyle modifier.

**Evidence classification:**
- HRV as readiness marker: **PEER-REVIEWED** (Kiviniemi 2007; Plews 2013; Buchheit 2014; PMC11204851)
- Specific weights (0.5/0.3/0.2): **EVIDENCE-INFORMED HEURISTIC** — proportions reflect relative objectivity; not derived from a single study

Sources: Kiviniemi, A.M. et al. (2007). *European Journal of Applied Physiology*, 101, 743-751. Plews, D.J. et al. (2013). *Sports Medicine*, 43, 773-781. Buchheit, M. (2014). *Frontiers in Physiology*, 5, 112. PMC11204851.

## Training Methodologies

Rep range and frequency targets per training goal (strength / hypertrophy / endurance).

### Strength

**Values: rep_min=1, rep_max=5, frequency_per_week_min=2, frequency_per_week_max=4**

Strength-focused training targets 1-5 rep range at 80-100% 1RM. Near-maximal loading maximizes neural adaptations and 1RM gains. Frequency of 2-4x/week per muscle group allows adequate recovery between high-intensity sessions.

Source: Schoenfeld, B.J. & Grgic, J. (2021). PMC7927075.

### Hypertrophy

**Values: rep_min=6, rep_max=12, frequency_per_week_min=2, frequency_per_week_max=4**

Hypertrophy-focused training targets 6-12 rep range at 60-80% 1RM. Schoenfeld (2021) demonstrates equivalent hypertrophy across 6-30+ reps when training to near-failure — the 6-12 range is the practical default for double progression. Frequency of 2-4x/week is optimal; 2x minimum is the evidence-based floor.

Source: Schoenfeld, B.J. & Grgic, J. (2021). PMC7927075. Schoenfeld, Ogborn & Krieger (2016). *Sports Medicine*, 46(11). PubMed 27102172.

### Endurance

**Values: rep_min=15, rep_max=30, frequency_per_week_min=3, frequency_per_week_max=5**

Muscular endurance training targets 15-30+ rep range at less than 60% 1RM. High rep counts develop metabolic endurance and slow-twitch fiber adaptations. Higher frequency (3-5x/week) is feasible due to lower per-session intensity.

Source: Schoenfeld, B.J. & Grgic, J. (2021). PMC7927075.

## Planning Constraints

Inter-session rest day minimums to avoid overtraining and preserve hypertrophic stimulus.

### min_rest_days_per_muscle_group

**Value: 2 days (= 48 hours minimum)**

Research demonstrates that:
- 24-36 hours: significant strength decrease in same-muscle testing (insufficient recovery)
- **48 hours**: threshold at which performance is no longer impaired, selected as minimum

Source: Monteiro, A.G. et al. (2018). "Effects of Consecutive Versus Non-consecutive Days of Resistance Training." PMC6015912. De Salles, B.F. et al. (2010). "Rest interval between sets in strength training." PubMed 19691365.

### min_rest_days_compound

**Value: 3 days (= 72 hours recommended for multi-joint movements)**

Multi-joint compound exercises (squat, deadlift, bench press, overhead press) involve greater systemic fatigue, larger muscle mass, and higher CNS demand. 72 hours provides adequate recovery for these movements.

Source: De Salles, B.F. et al. (2010). PubMed 19691365. Schoenfeld, Ogborn & Krieger (2016). PubMed 27102172.
