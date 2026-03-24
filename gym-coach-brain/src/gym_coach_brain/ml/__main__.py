"""
ML Worker daemon entry point.

Run as:
    python -m gym_coach_brain.ml

Environment variables:
    DATABASE_URL        SQLAlchemy connection string (default: sqlite:///gym_coach.sqlite)
    SCIENCE_YAML        Path to ScienceEvidence.md (default: auto-discover)
    MODEL_DIR           Directory for model checkpoints (default: ./model_weights)
    ML_POLL_INTERVAL    Polling interval in seconds (default: 60)
    ML_FINE_TUNE_THRESHOLD  Minimum eligible sessions before fine-tuning (default: 5)
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from loguru import logger

from gym_coach_brain.core.science import load_science_config
from gym_coach_brain.data.session import get_engine
from gym_coach_brain.ml.constants import MODEL_DIR
from gym_coach_brain.ml.model import RPEModel
from gym_coach_brain.ml.worker import MLWorker


def _discover_latest_checkpoint(model_dir: Path) -> tuple[Path | None, int]:
    """Return the highest-version canonical checkpoint in model_dir, if any.

    Ignores .backup.pt and .anomaly.pt suffix variants.
    Returns (None, 1) when no canonical checkpoints are found.
    """
    latest_path: Path | None = None
    latest_version = 1

    for path in model_dir.glob("model_v*.pt"):
        match = re.fullmatch(r"model_v(\d+)\.pt", path.name)
        if match is None:
            continue
        version = int(match.group(1))
        if latest_path is None or version > latest_version:
            latest_path = path
            latest_version = version

    return latest_path, latest_version


def _bootstrap_model(model: RPEModel, model_dir: Path) -> int:
    """Bootstrap model weights from model_dir with corrupt-file recovery.

    Startup sequence (AC 4):
    1. Create model_dir with exist_ok=True
    2. Discover canonical checkpoints (excluding .backup.pt / .anomaly.pt)
    3. No checkpoints → random init + WARNING (AC 5)
    4. For each version descending:
       a. Try loading canonical file
       b. Corrupt → quarantine as .corrupt.pt, try .backup.pt of same version
       c. If backup also fails → continue to n-1
    5. All failed → random init + WARNING

    Returns the version number of the loaded weights (1 if random init).
    """
    model_dir.mkdir(parents=True, exist_ok=True)

    # Collect canonical versions in descending order
    all_versions: list[int] = []
    for path in model_dir.glob("model_v*.pt"):
        match = re.fullmatch(r"model_v(\d+)\.pt", path.name)
        if match:
            all_versions.append(int(match.group(1)))
    all_versions.sort(reverse=True)

    if not all_versions:
        logger.warning(
            "No canonical checkpoints found in {model_dir}; starting with random weights",
            model_dir=model_dir,
        )
        return 1

    for version in all_versions:
        canonical = model_dir / f"model_v{version}.pt"
        if not canonical.exists():
            continue

        try:
            model.load(canonical)
            logger.info(
                "Loaded model checkpoint model_v{version}.pt from {path}",
                version=version,
                path=canonical,
            )
            return version
        except Exception as exc:
            # Quarantine the corrupt canonical file (AC 4)
            corrupt_path = model_dir / f"model_v{version}.corrupt.pt"
            try:
                os.replace(canonical, corrupt_path)
            except OSError:
                pass
            logger.warning(
                "Corrupt checkpoint model_v{version}.pt quarantined → "
                "model_v{version}.corrupt.pt: {exc}",
                version=version,
                exc=exc,
            )

            # Try same-version backup (AC 4)
            backup = model_dir / f"model_v{version}.backup.pt"
            if backup.exists():
                try:
                    model.load(backup)
                    logger.warning(
                        "Recovered from model_v{version}.backup.pt "
                        "after corrupt canonical",
                        version=version,
                    )
                    return version
                except Exception as backup_exc:
                    logger.warning(
                        "Backup model_v{version}.backup.pt also corrupt: {exc}",
                        version=version,
                        exc=backup_exc,
                    )
            # Continue to n-1 in the sorted list

    logger.warning(
        "All checkpoints corrupt or unavailable in {model_dir}; "
        "starting with random weights",
        model_dir=model_dir,
    )
    return 1


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "sqlite:///gym_coach.sqlite")
    science_yaml_env = os.getenv("SCIENCE_YAML")
    model_dir = Path(os.getenv("MODEL_DIR", str(MODEL_DIR)))
    poll_interval = int(os.getenv("ML_POLL_INTERVAL", "60"))
    fine_tune_threshold = int(os.getenv("ML_FINE_TUNE_THRESHOLD", "5"))

    engine = get_engine(database_url)

    science_path = Path(science_yaml_env) if science_yaml_env else None
    science = load_science_config(science_path)

    model = RPEModel()
    initial_model_version = _bootstrap_model(model, model_dir)

    worker = MLWorker(
        engine=engine,
        model=model,
        science_config=science,
        poll_interval=poll_interval,
        fine_tune_threshold=fine_tune_threshold,
        model_dir=model_dir,
        initial_model_version=initial_model_version,
    )
    worker.run()


if __name__ == "__main__":
    main()
