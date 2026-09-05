"""Configuration for the Model Registry service (Step 3 of the MLOps plan).

Values come from environment variables (see ``.env.example``). The service is an
MLflow *client*: it talks to the MLflow tracking/registry server over HTTP. It
also keeps one small local file — the editable promotion-gate thresholds
(``gate-settings.json``) — so those settings survive restarts without being
pinned to environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _get(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None or value.strip() == "" else value.strip()


@dataclass(frozen=True)
class Settings:
    # MLflow server. The Model Registry lives in the same store as tracking, so
    # this single URI serves both (registered models + their source runs).
    mlflow_tracking_uri: str

    # Writable dir hosting the local gate-settings file (see gate.py).
    data_dir: Path

    @property
    def gate_settings_path(self) -> Path:
        return self.data_dir / "gate-settings.json"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        mlflow_tracking_uri=_get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        data_dir=Path(_get("DATA_DIR", "./data")),
    )