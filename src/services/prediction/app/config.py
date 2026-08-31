"""Configuration for the Prediction service (Step 4 of the MLOps plan).

All values come from environment variables (see ``.env.example``). The service
is an MLflow *client*: it resolves the Production model by name + stage over
HTTP and never touches the MLflow server's filesystem.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _get(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None or value.strip() == "" else value.strip()


def _get_int(name: str, default: int) -> int:
    value = _get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = _get(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # MLflow tracking/registry server (same store that holds registered models).
    mlflow_tracking_uri: str

    # Registered-model name, resolved as ``models:/<model_name>/Production``.
    # Must match what the Training service registers (REGISTER_MODEL_NAME).
    model_name: str

    # Input size the model was trained on — must match Training's image size.
    image_size: int

    # Sigmoid decision boundary: probability >= threshold is "dog" (class 1).
    threshold: float


@lru_cache
def get_settings() -> Settings:
    return Settings(
        mlflow_tracking_uri=_get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        model_name=_get("REGISTER_MODEL_NAME", "CatDogClassifier"),
        image_size=_get_int("IMAGE_SIZE", 160),
        threshold=_get_float("PREDICT_THRESHOLD", 0.5),
    )