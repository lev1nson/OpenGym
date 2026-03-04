# Story 1.1: Ресёрч спортивной науки

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a dev agent,
I want to run the domain-research workflow on sports science topics,
So that I have verified numerical coefficients and principles for ScienceEvidence.md.

## Acceptance Criteria

**Given** domain-research workflow доступен и web search работает

**When** агент вызывает `Skill("bmad-domain-research")` с темой:
> "APRE, Double Progression, PUOS, фракционный объём (1.0/0.5), SMH stretch_mediated, коэффициенты восстановления (сон, стресс, HRV), тренировочные методологии (гипертрофия, сила, выносливость), минимальный отдых между тренировками одной группы мышц (min_rest_days)"

**Then** research report сохранён в `_bmad-output/planning-artifacts/research/` (имя файла генерируется workflow автоматически; фактический файл: `domain-sports-science-research-2026-03-04.md`)

**And** документ содержит числовые значения для каждой темы с источниками/обоснованиями

**And** все 7 тематических областей покрыты:
1. APRE (Auto-Regulatory Progressive Resistance Exercise)
2. Double Progression
3. PUOS (Per-Unique per session volume)
4. Fractional volume (1.0/0.5 multipliers)
5. SMH stretch_mediated hypertrophy
6. Recovery coefficients (sleep, stress, HRV)
7. Training methodologies (hypertrophy, strength, endurance)

**And** для каждой методологии определены:
- Диапазон повторений
- Тип прогрессии
- Рекомендуемая частота тренировок

**And** все источники являются peer-reviewed публикациями или работами признанных S&C исследователей (Schoenfeld, Helms, Israetel, Baraki, Zourdos) — общие сайты, форумы и YouTube-контент не принимаются

**And** для каждого числового коэффициента указана ссылка на конкретный источник (автор, год, или DOI)

## Tasks / Subtasks

- [x] Check if research file already exists (AC: all)
  - [x] Look for `_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md`
  - [x] If exists → verify it satisfies ALL acceptance criteria below; skip to verification step
- [x] Run domain-research workflow if file does not yet exist (AC: all)
  - [x] Invoke `Skill("bmad-domain-research")` with the sports science topic string above
  - [x] Ensure workflow completes and saves file to correct path
- [x] Verify coverage of all 7 thematic areas (AC: 7-area coverage)
  - [x] Section 1: APRE protocol, adjustment tables, reps → weight change mapping
  - [x] Section 2: Double Progression — rep range brackets (e.g., 3×8–12), progression trigger
  - [x] Section 3: PUOS limits — max sets per muscle group per session
  - [x] Section 4: Fractional volume — 1.0 (primary) vs 0.5 (secondary) multipliers
  - [x] Section 5: SMH (Stretch-Mediated Hypertrophy) — smh_volume_multiplier range (1.2–1.3 per Israetel)
  - [x] Section 6: Recovery coefficients — sleep quality, HRV, stress score modifiers
  - [x] Section 7: Methodologies — hypertrophy, strength, endurance with rep ranges + frequency
- [x] Verify peer-reviewed sources only (AC: source quality)
  - [x] No forum links, no YouTube, no general fitness websites
  - [x] Schoenfeld/Helms/Israetel/Baraki/Zourdos citations present for key claims
- [x] Verify each numerical coefficient has a citation (AC: coefficient sourcing)
  - [x] Author + year OR DOI for every numerical value
- [x] Verify min_rest_days defined (AC: planning constraint)
  - [x] `min_rest_days_per_muscle_group` value with scientific justification (expected: 2–3 days / 48–72h)
- [x] Confirm file is saved at correct path (AC: output location)

### Review Follow-ups (AI)
- [x] [AI-Review][CRITICAL] Fix citation error: "Muscle and Strength Pyramids" is by Eric Helms, not Mike Israetel (Section 3). [_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md:158]
- [x] [AI-Review][MEDIUM] Replace Bodybuilding.com source with a peer-reviewed publication (Section 7). [_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md:435]
- [x] [AI-Review][MEDIUM] Correct broken/duplicate PubMed link (26049792) for Helms (2016) citation (Section 10). [_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md:586]
- [x] [AI-Review][MEDIUM] Explicitly flag and justify "evidence-informed heuristics" vs. peer-reviewed coefficients for smh_multiplier and recovery weights. [_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md:323, 404]
- [x] [AI-Review][MEDIUM] Add specific citation for APRE-10 table origin (Bryan Mann) (Section 1). [_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md:120]
- [x] [AI-Review][LOW] Add biomechanical note explaining Deadlift (0.5) vs RDL (1.0) hamstring fractional volume difference (Section 8). [_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md:522, 563]
- [x] [AI-Review][LOW] Explicitly document 5 lbs to 2.5 kg rounding for APRE metric increments (Section 1). [_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md:104]

## Dev Notes

### Critical Pre-Implementation Check: Research File Already Exists

**⚠️ IMPORTANT:** The domain research file ALREADY EXISTS at:
```
_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md
```

**Strategy:**
1. First READ the existing file and verify it satisfies ALL 7 acceptance criteria
2. If fully satisfied → mark story done (the work is already done)
3. If missing areas → supplement using `Skill("bmad-domain-research")` to fill gaps or update the file manually

### What This Story Produces

This story produces a **Research Report** (a markdown document), NOT code. It is a prerequisite for:
- **Story 1.2**: YAML schema design for `ScienceEvidence.md`
- **Story 1.2.5**: Implementing `core/science.py` Pydantic models
- **Story 1.3**: Filling `ScienceEvidence.md` with real coefficient values

The key output data extracted from this research will directly feed into the `ScienceEvidence.md` YAML frontmatter fields:
- `puos.max_sets_per_group` — from PUOS research
- `puos.smh_volume_multiplier` — from SMH research (Israetel, 1.2–1.3)
- `progression.*` — from APRE + Double Progression research
- `recovery.*` — from recovery coefficients research
- `planning.min_rest_days_per_muscle_group` — from recovery research (48–72h → 2–3 days)
- `methodologies.*` — from training methodologies research

### How to Invoke Domain Research Skill

```python
# If research needs to be re-run or supplemented:
Skill("bmad-domain-research")
# Topic: "APRE, Double Progression, PUOS, фракционный объём (1.0/0.5), SMH stretch_mediated,
#          коэффициенты восстановления (сон, стресс, HRV), тренировочные методологии
#          (гипертрофия, сила, выносливость), минимальный отдых между тренировками
#          одной группы мышц (min_rest_days)"
```

### Key Numerical Values to Verify Are Present

Based on Architecture.md ADR-002 and Epic 1 story requirements, the following MUST be in the research report:

| Parameter | Expected Range | Source |
|-----------|---------------|--------|
| `smh_volume_multiplier` | 1.2–1.3 | Israetel |
| `max_sets_per_group` (PUOS) | ~10–20 per week / ~5–11 per session | Israetel/Schoenfeld |
| `min_rest_days_per_muscle_group` | 2–3 days (48–72h) | Recovery science |
| APRE-6 adjustment step | ±2.5–5 kg | Knight (1979) |
| Confidence threshold fallback | N/A (architecture, not science) | Architecture.md |
| Hypertrophy rep range | 6–12 | Schoenfeld (2010) |
| Strength rep range | 1–5 | Helms et al. |
| Endurance rep range | 15+ | Various |

### Source Quality Requirements

The research **MUST** cite only:
- Peer-reviewed journals: JSCR, European Journal of Sport Science, Medicine & Science in Sports & Exercise
- Recognized S&C researchers: Schoenfeld, Helms, Israetel, Baraki, Zourdos, Mann, Knight
- Systematic reviews / meta-analyses preferred

**NOT acceptable:** Reddit, YouTube, bodybuilding.com, T-Nation (unless citing a researcher's own peer-reviewed paper linked there)

### Architecture Constraints for This Story

This is a **research story** with no code output. Key notes:
- Output path: `_bmad-output/planning-artifacts/research/` (fixed, per Epic 1 spec)
- File naming: generated by workflow (e.g., `domain-sports-science-research-2026-03-04.md`)
- No Python code, no SQLAlchemy, no Pydantic — pure research document
- No DB changes required

### Project Structure Notes

This story does NOT touch the `gym-coach-brain` source code at all. Relevant paths:
- **Input:** none (web research)
- **Output:** `_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md`
- **Consumed by Story 1.2:** the research file is read to design YAML schema
- **Consumed by Story 1.3:** the research file is read to populate `ScienceEvidence.md` values

### References

- Epic 1 story requirements: [Source: _bmad-output/planning-artifacts/epics/epic-1.md#Story 1.1]
- Architecture ADR-002 (ScienceConfig loading): [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002]
- Architecture SMH multiplier note: [Source: _bmad-output/planning-artifacts/architecture.md#ScienceEvidence.md]
- Project context: [Source: _bmad-output/project-context.md]
- Existing research file: [Source: _bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Story 1.1 implementation note: Check the existing research file first at `_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md` — it was created 2026-03-04 and may already satisfy all ACs.
- ✅ Research file verified on 2026-03-04 — ALL 7 acceptance criteria satisfied. File exists at correct path with comprehensive peer-reviewed coverage of APRE (Knight 1979, Mann 2010), Double Progression (Schoenfeld & Grgic 2021), PUOS/fractional volume (Israetel RP Strength), SMH multiplier 1.2–1.3 (Israetel), recovery coefficients (Kiviniemi 2007, Plews 2013, Buchheit 2014), training methodologies (Schoenfeld & Grgic 2021), and min_rest_days=2 (PMC6015912, PMC6719818). Summary table provides all ScienceEvidence.md coefficients with confidence levels.
- ✅ Resolved review finding [CRITICAL]: Fixed "Muscle and Strength Pyramids" attribution — added ⚠️ note clarifying this is Eric Helms's work (2015), not Israetel's. Israetel's primary text is "Scientific Principles of Strength Training" (2019).
- ✅ Resolved review finding [MEDIUM]: Replaced Bodybuilding.com source (Section 7) with Schoenfeld, Ogborn & Krieger (2016) peer-reviewed meta-analysis on RT frequency (PubMed 27102172).
- ✅ Resolved review finding [MEDIUM]: Fixed Helms (2016) duplicate PubMed link — Helms now links to DOI (SCJ not PubMed-indexed); Zourdos retains PMID 26049792. Both links corrected in Sources section.
- ✅ Resolved review finding [MEDIUM]: Added explicit peer-reviewed vs evidence-informed heuristic tables for both SMH multiplier (Section 4) and recovery composite weights (Section 5), with implementation code annotations.
- ✅ Resolved review finding [MEDIUM]: Added Mann et al. (2010) citation above APRE-10 table with PubMed link.
- ✅ Resolved review finding [LOW]: Added biomechanical note under Section 8.3 explaining why Deadlift hamstrings = 0.5 (shortened/mid-length at lockout) vs RDL hamstrings = 1.0 (peak tension at maximum stretch, SMH-qualifying).
- ✅ Resolved review finding [LOW]: Added Metric Conversion Note section in Section 1 documenting 5 lbs ≈ 2.5 kg rounding with conversion table and rationale.
- ✅ Research report final review: Addressed remaining inconsistencies in summary tables, APRE steps, and RPE ranges. Verified Abs/Core and Lower Back landmarks added. (2026-03-04)

### File List

- `_bmad-output/planning-artifacts/research/domain-sports-science-research-2026-03-04.md` (created/verified/updated with review fixes)

## Change Log

- 2026-03-04: Initial research file created and verified against all 7 ACs.
- 2026-03-04: Addressed code review findings — 7 items resolved (1 CRITICAL, 4 MEDIUM, 2 LOW). Key fixes: citation attribution correction (Helms vs Israetel), Bodybuilding.com → peer-reviewed replacement, duplicate PubMed link fix, explicit heuristic vs peer-reviewed classification tables, APRE-10 citation, biomechanical deadlift/RDL note, lbs→kg rounding documentation.
