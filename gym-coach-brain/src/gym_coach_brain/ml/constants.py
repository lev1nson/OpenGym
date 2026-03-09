"""
ML module constants.

Kept separate from ScienceConfig so the ML package can share stable defaults
without importing the runtime science loader.
"""
from __future__ import annotations

import os
from pathlib import Path

CONFIDENCE_THRESHOLD: float = 0.6
DEFAULT_FINE_TUNE_THRESHOLD: int = 5
MC_DROPOUT_PASSES: int = 20
FEATURE_DIM: int = 19

_DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[4] / "model_weights"
MODEL_DIR: Path = Path(os.getenv("MODEL_DIR", str(_DEFAULT_MODEL_DIR)))
