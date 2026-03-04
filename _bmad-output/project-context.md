---
project_name: '.openclaw'
user_name: 'Max'
date: '2026-03-01'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns', 'database_architecture']
status: 'complete'
rule_count: 15
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Python 3.14**: Core language for all skill logic.
- **SQLite 3.x**: Primary database, strictly using **WAL mode** and **Foreign Keys**.
- **SQLAlchemy 2.0+**: Mandatory ORM for all database interactions.
- **Alembic**: Required for all schema migrations; manual SQL changes are forbidden.
- **Pydantic 2.0+**: Mandatory for data validation and schema definition.
- **Pytest**: Standard testing framework for all new features.
- **Node.js (LTS)**: Platform infrastructure (Telegraf, Express).

## Critical Implementation Rules

### Language & Framework Rules (Python)
- **Modern Dependencies Mandatory**: Use `pydantic` for validation and `sqlalchemy` for DB. Avoid raw dictionaries for complex data.
- **SQLAlchemy Declarative**: All tables MUST be defined as SQLAlchemy models using the Declarative Base.
- **Pydantic-SQLAlchemy Integration**: Use Pydantic models for NL Proxy (`router.py`) validation before data reaches DB models (`from_attributes=True`).
- **Type Hinting**: Mandatory use of `typing` module for all function signatures and complex variables.

### Regex & Parsing Rules
- **Regex Alignment**: Parsing patterns (e.g., `RE_RPE`, `RE_WXRX`) MUST be identical in `router.py` and `gym_coach.py`.
- **Cyrillic Support**: Always include support for Cyrillic 'х' in weight/reps patterns and 'rpe N' format.

### Database & Migration Rules (ADR #001)
- **Alembic Only**: All schema updates MUST be done via `alembic revision --autogenerate`.
- **Deterministic Formulas**: Use scientific formulas (e.g., Brzycki 1RM) over LLM reasoning for training calculations.

### Testing & Quality Rules
- **Test-Driven Development**: Every new feature or bug fix MUST include `pytest` tests.
- **DB Isolation**: Use `sqlite:///:memory:` for unit and integration tests to ensure speed and isolation.
- **Zero-Test Coverage Alert**: Be proactive in adding tests to legacy code when modifying it.

### Workflow & Structure
- **Dependency Tracking**: Update `requirements.txt` immediately when adding any external library.
- **Naming Conventions**: `snake_case` for files/functions/variables; `PascalCase` for classes/models.
- **Subprocess Protocol**: Maintain strict separation between `router.py` (stateless proxy) and `gym_coach.py` (CLI engine).

## Critical Don't-Miss Rules (Anti-Patterns)
- **NO Raw SQL**: Do not write manual `INSERT/UPDATE` queries; use SQLAlchemy sessions.
- **NO Missing RPE**: Ensure 'rpe N' format is correctly parsed and not silently dropped.
- **NO Global State**: Keep command handlers stateless; rely on the SQLite `meta` table for session persistence.

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code.
- Follow ALL rules exactly as documented.
- When in doubt, prefer the more restrictive option.
- Update this file if new architectural patterns are established.

**For Humans:**
- Keep this file lean and focused on agent needs.
- Update when the technology stack changes.
- Review quarterly for outdated rules.
- Remove rules that become obvious to the team over time.

Last Updated: 2026-03-01
