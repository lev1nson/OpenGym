"""
Custom exception hierarchy for gym-coach-brain.

All internal modules raise typed exceptions — NOT return error dicts.
Only api/ layer converts exceptions to exit_code + stdout.
"""


class GymCoachError(Exception):
    """Base exception for all gym-coach-brain errors."""
    pass


class ScienceLimitError(GymCoachError):
    """Raised when PUOS/safety limits are violated.

    Raised by: core/puos.py
    Caught by: adaptation/engine.py (never ignored), api/ (exit_code=1)
    """
    pass


class MLPredictionError(GymCoachError):
    """Raised when ML Worker fails to produce a prediction.

    Raised by: ml/worker.py, ml/model.py
    Caught by: adaptation/engine.py (fallback to Double Progression — NOT re-raised)
    """
    pass


class ConfigError(GymCoachError):
    """Raised when ScienceConfig cannot be parsed.

    Raised by: core/science.py (load_science_config)
    Caught by: api/main.py (exit_code=2, process should restart)
    """
    pass
