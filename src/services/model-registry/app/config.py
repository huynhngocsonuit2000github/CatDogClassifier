"""Configuration for the Model Registry service (Step 3 of the MLOps plan).

All values come from environment variables (see ``.env.example``). The service
is an MLflow *client*: it talks to the MLflow tracking/registry server over
HTTP and never touches the server's filesystem.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _get(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None or value.strip() == "" else value.strip()


@dataclass(frozen=True)
class Settings:
    # MLflow server. The Model Registry lives in the same store as tracking, so
    # this single URI serves both (registered models + their source runs).
    mlflow_tracking_uri: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        mlflow_tracking_uri=_get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
    )