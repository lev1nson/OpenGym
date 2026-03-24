from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = REPO_ROOT / "gym-coach-brain"
SYSTEMD_DIR = PROJECT_ROOT / "systemd"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ml_service_uses_shared_env_file_and_expected_runtime_contract() -> None:
    service_text = read_text(SYSTEMD_DIR / "gym-coach-brain-ml.service")

    assert "ExecStart=/opt/opengym/gym-coach-brain/.venv/bin/python -m gym_coach_brain.ml" in service_text
    assert "Restart=on-failure" in service_text
    assert "MemoryMax=8G" in service_text
    assert "EnvironmentFile=/opt/opengym/gym-coach-brain/systemd/gym-coach-brain.env" in service_text
    assert "Environment=DATABASE_URL=" not in service_text
    assert "Environment=MODEL_DIR=" not in service_text
    assert "Environment=ML_POLL_INTERVAL=" not in service_text
    assert "Environment=ML_FINE_TUNE_THRESHOLD=" not in service_text


def test_bot_service_exists_and_uses_packaged_bot_entrypoint() -> None:
    service_path = SYSTEMD_DIR / "gym-coach-brain-bot.service"
    service_text = read_text(service_path)

    assert "ExecStart=/opt/opengym/gym-coach-brain/.venv/bin/python -m gym_coach_brain.bot.main" in service_text
    assert "EnvironmentFile=/opt/opengym/gym-coach-brain/systemd/gym-coach-brain.env" in service_text
    assert "Restart=on-failure" in service_text
    assert "WantedBy=multi-user.target" in service_text
    assert "gym_coach_brain.api" not in service_text


def test_env_example_covers_required_runtime_variables_without_live_secrets() -> None:
    env_text = read_text(SYSTEMD_DIR / "gym-coach-brain.env.example")

    for key in (
        "DATABASE_URL",
        "MODEL_DIR",
        "TELEGRAM_BOT_TOKEN",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "ML_POLL_INTERVAL",
        "ML_FINE_TUNE_THRESHOLD",
    ):
        assert f"{key}=" in env_text

    assert "your-openrouter-api-key" in env_text
    assert "your-telegram-bot-token" in env_text


def test_ci_workflow_runs_locked_uv_pytest_from_project_directory() -> None:
    workflow_text = read_text(REPO_ROOT / ".github" / "workflows" / "ci.yml")

    assert "pull_request:" in workflow_text
    assert "push:" in workflow_text
    assert "uses: actions/checkout@v5" in workflow_text
    assert "uses: actions/setup-python@v5" in workflow_text
    assert "uses: astral-sh/setup-uv@v7" in workflow_text
    assert "working-directory: gym-coach-brain" in workflow_text
    assert "python-version-file: gym-coach-brain/.python-version" in workflow_text
    assert "uv sync --locked --dev" in workflow_text
    assert "uv run pytest" in workflow_text


def test_readme_documents_operator_deployment_workflow() -> None:
    readme_text = read_text(PROJECT_ROOT / "README.md")

    assert "gym-coach-brain.env.example" in readme_text
    assert "gym-coach-brain.env" in readme_text
    assert "chmod 600" in readme_text
    assert "systemctl enable --now gym-coach-brain-ml.service" in readme_text
    assert "systemctl enable --now gym-coach-brain-bot.service" in readme_text
    assert "journalctl -u gym-coach-brain-ml.service -f" in readme_text
    assert "journalctl -u gym-coach-brain-bot.service -f" in readme_text
    assert "Telegram bot token" in readme_text
    assert "OpenRouter API key" in readme_text
    assert "uv run pytest" in readme_text
