# OpenGym GitHub Positioning Plan

## Goal

Transform [`README.md`](../README.md) from a generic template pitch into a repository-level product narrative that reflects the real strengths of the current codebase and roadmap.

## What I analyzed

- Current public positioning in [`README.md`](../README.md)
- Actual implemented capabilities and architecture in [`docs/project-overview.md`](../docs/project-overview.md)
- Technical strengths and known limitations in [`docs/architecture.md`](../docs/architecture.md)
- Stack and design decisions in [`docs/technology-stack.md`](../docs/technology-stack.md)
- Documentation entrypoint and issue matrix in [`docs/index.md`](../docs/index.md)

## Observed mismatch

Current README presents OpenGym mostly as a generic LLM template, while repository artifacts show a stronger and more specific value:

- local-first fitness intelligence direction
- deterministic training logic with science grounding
- practical AI workflow culture and documentation discipline
- clear migration path from working MVP toward modular gym-coach-brain

## Proposed narrative direction

### Positioning statement

OpenGym is a local-first AI fitness engineering repo that combines deterministic sports-science logic with an LLM-friendly development workflow.

### Core differentiators

1. Deterministic core over hallucination-prone recommendations
2. Science-config driven methodology as explicit artifact
3. NL proxy plus CLI engine architecture with transparent contracts
4. Zero-dependency operational baseline for reliability and deployability
5. Open architecture documentation with explicit debt and roadmap

## Planned README sections

1. Hero section with concise product pitch and trust badges
2. Why this project exists
3. What is implemented today
4. Architecture snapshot
5. Why this is unique
6. Quality and transparency
7. Quick start
8. Roadmap and current stage
9. Contributing and license

## Draft content strategy

- Avoid overclaiming
- Keep all claims traceable to docs/code artifacts
- Use short, high-signal sections optimized for GitHub skimming
- Emphasize culture plus engineering rigor

## GitHub page metadata recommendations

- About: Local-first AI fitness system with deterministic training logic and LLM-native workflow
- Topics: ai, fitness, llm, python, sqlite, sports-science, openclaw, cli
- Social preview: use [`logo.png`](../logo.png) or a dedicated OpenGraph image in [`assets/`](../assets)

## Next execution steps

1. Rewrite [`README.md`](../README.md) using the proposed structure
2. Keep existing stars/forks badges and improve signal badges
3. Add architecture mini-diagram in Mermaid for rapid understanding
4. Final polish for canonical open-source tone and consistency
