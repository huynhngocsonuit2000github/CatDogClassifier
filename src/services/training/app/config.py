"""Configuration for the Training service (Step 2 of the MLOps plan).

All values are read from environment variables (see ``.env.example``). The
service does **not** own the DVC repo — it points at the shared repo managed by
the Data Management service and only ``dvc pull``s already-tracked datasets.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


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
    # Shared DVC repo owned by the Data Management service (local dev points at
    # its ``data/`` dir; in Docker this is a shared volume).
    data_repo: Path

    # MLflow tracking server.
    mlflow_tracking_uri: str
    mlflow_experiment: str

    # S3/MinIO credentials injected into the ``dvc pull`` subprocess (the shared
    # remote config carries the endpoint+url but not credentials).
    s3_access_key: str
    s3_secret_key: str

    # Default hyper-parameters (each can be overridden per request).
    default_epochs: int
    default_batch_size: int
    default_learning_rate: float
    default_image_size: int

    # Registered-model name in the MLflow Model Registry (Step 3). Every trained
    # run is auto-registered as a new version of this model.
    model_registry_name: str

    @property
    def datasets_dir(self) -> Path:
        return self.data_repo / "datasets"

    @property
    def index_path(self) -> Path:
        return self.data_repo / ".datasets" / "index.json"

    @property
    def s3_env(self) -> dict[str, str]:
        return {
            "AWS_ACCESS_KEY_ID": self.s3_access_key,
            "AWS_SECRET_ACCESS_KEY": self.s3_secret_key,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings(
        data_repo=Path(_get("DATA_REPO", "../data-management/data")).resolve(),
        mlflow_tracking_uri=_get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        mlflow_experiment=_get("MLFLOW_EXPERIMENT", "catdog"),
        s3_access_key=_get("S3_ACCESS_KEY", "minioadmin"),
        s3_secret_key=_get("S3_SECRET_KEY", "minioadmin"),
        default_epochs=_get_int("TRAIN_EPOCHS", 10),
        default_batch_size=_get_int("TRAIN_BATCH_SIZE", 8),
        default_learning_rate=_get_float("TRAIN_LEARNING_RATE", 1e-3),
        default_image_size=_get_int("TRAIN_IMAGE_SIZE", 160),
        model_registry_name=_get("REGISTER_MODEL_NAME", "CatDogClassifier"),
    )