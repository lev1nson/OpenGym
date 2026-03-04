<div align="center">
  <img src="logo.png" alt="OpenGym logo" width="100%" />

  # OpenGym
  **A production-minded open template for LLM-native product development**

  [![Status](https://img.shields.io/badge/status-active%20template-22c55e)](#)
  [![GitHub stars](https://img.shields.io/github/stars/lev1nson/OpenGym?style=flat)](https://github.com/lev1nson/OpenGym/stargazers)
  [![GitHub forks](https://img.shields.io/github/forks/lev1nson/OpenGym?style=flat)](https://github.com/lev1nson/OpenGym/network/members)
  [![Contributions](https://img.shields.io/badge/contributions-welcome-3b82f6)](CONTRIBUTING.md)
  [![License](https://img.shields.io/badge/license-MIT-black)](LICENSE)
</div>

OpenGym is a repository template for teams building AI-first products with clear engineering standards.

It gives you a practical baseline for documentation, prompting discipline, contribution culture, and iterative delivery — so your project starts structured from day one.

---

## Why OpenGym

Most LLM projects fail not because of model quality, but because of process chaos.

OpenGym is designed to solve exactly that:

- **Documentation-first workflow** for faster onboarding and lower team ambiguity.
- **Prompt governance** with reusable system/task prompt structure.
- **Contributor-friendly setup** with explicit contribution rules and change tracking.
- **GitHub-native hygiene** with CI checks and repository conventions.
- **Scalable project skeleton** suitable for prototypes and production evolution.

---

## Core Features

- **Clear project scaffolding** across [`docs/`](docs), [`prompts/`](prompts), and [`assets/`](assets).
- **Canonical repository docs**: [`README.md`](README.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CHANGELOG.md`](CHANGELOG.md), [`LICENSE`](LICENSE).
- **LLM operating guide** in [`docs/LLM_GUIDE.md`](docs/LLM_GUIDE.md).
- **Roadmap baseline** in [`docs/ROADMAP.md`](docs/ROADMAP.md).
- **Prompt templates** in [`prompts/system.md`](prompts/system.md) and [`prompts/task-template.md`](prompts/task-template.md).
- **Basic CI guardrails** for documentation quality in [`.github/workflows/`](.github/workflows).

---

## What Makes It Better Than a Typical Starter Repo

1. **It encodes culture, not just files**
   - Convention over chaos: clear expectations for docs, prompts, and collaboration.

2. **It is AI-workflow aware**
   - Structure is optimized for human + LLM co-development.

3. **It is transparent by design**
   - Change history and roadmap are first-class citizens, not afterthoughts.

4. **It is implementation-agnostic**
   - Works for Python, JS/TS, backend APIs, agent systems, and mixed stacks.

---

## Quick Start

```bash
# 1) Clone the repository
git clone <your-repo-url>
cd OpenGym

# 2) Create your working branch
git checkout -b chore/bootstrap-project

# 3) Customize the project baseline
# - README.md: project positioning and value proposition
# - docs/LLM_GUIDE.md: model usage rules and constraints
# - prompts/system.md: core system behavior
```

---

## Recommended Structure

```text
OpenGym/
├─ assets/                # logos, banners, visual assets
├─ docs/
│  ├─ LLM_GUIDE.md        # operating rules for LLM usage
│  └─ ROADMAP.md          # milestones and release direction
├─ prompts/
│  ├─ system.md           # canonical system prompt
│  └─ task-template.md    # reusable task prompt template
├─ .github/workflows/
│  └─ docs-check.yml      # minimal CI checks for docs quality
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ LICENSE
└─ README.md
```

---

## Best Practices for Teams

- Keep [`README.md`](README.md) focused on **problem → solution → value**.
- Treat [`docs/LLM_GUIDE.md`](docs/LLM_GUIDE.md) as the source of truth for model behavior and safety boundaries.
- Version prompt changes like code changes.
- Update [`CHANGELOG.md`](CHANGELOG.md) on every meaningful iteration.
- Use pull requests to preserve decision history and review quality.

---

## Project Maturity Checklist

- [ ] Add domain-specific references and datasets to [`docs/LLM_GUIDE.md`](docs/LLM_GUIDE.md)
- [ ] Define evaluation scenarios (golden tests / acceptance prompts)
- [ ] Strengthen CI with quality gates and linting
- [ ] Add architecture and deployment docs when moving to production

---

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.

## License

MIT. See [`LICENSE`](LICENSE).
