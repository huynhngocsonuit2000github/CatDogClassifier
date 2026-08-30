"""Configuration for the Data Management service.

All values are read from environment variables (see ``.env.example``). The
defaults are chosen so the service can start against the bundled
``docker-compose.yml`` MinIO instance without extra configuration.
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


@dataclass(frozen=True)
class Settings:
    # Object storage backend: "s3" (MinIO) or "local" (dev/testing on disk).
    storage_backend: str

    # S3 / MinIO endpoint and credentials.
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    s3_region: str

    # DVC behaviour:
    #   "auto"     -> use DVC if `dvc` is on PATH, else degrade to filesystem.
    #   "required" -> fail fast if DVC is missing.
    #   "disabled" -> never invoke DVC (dev/testing).
    dvc_mode: str
    dvc_remote_name: str
    dvc_remote_path: str

    # Directory hosting the DVC repo and the extracted datasets.
    data_dir: Path

    # Maximum upload size in bytes (default 512 MiB).
    max_upload_bytes: int

    @property
    def index_path(self) -> Path:
        return self.data_dir / ".datasets" / "index.json"

    @property
    def datasets_dir(self) -> Path:
        return self.data_dir / "datasets"

    def dvc_remote_url(self) -> str:
        path = self.dvc_remote_path.strip("/")
        return f"s3://{self.s3_bucket}/{path}" if path else f"s3://{self.s3_bucket}"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        storage_backend=_get("STORAGE_BACKEND", "s3").lower(),
        s3_endpoint=_get("S3_ENDPOINT", "http://localhost:9000"),
        s3_access_key=_get("S3_ACCESS_KEY", "minioadmin"),
        s3_secret_key=_get("S3_SECRET_KEY", "minioadmin"),
        s3_bucket=_get("S3_BUCKET", "datasets"),
        s3_region=_get("S3_REGION", "us-east-1"),
        dvc_mode=_get("DVC_MODE", "auto").lower(),
        dvc_remote_name=_get("DVC_REMOTE_NAME", "minio"),
        dvc_remote_path=_get("DVC_REMOTE_PATH", ""),
        data_dir=Path(_get("DATA_DIR", "./data")),
        max_upload_bytes=_get_int("MAX_UPLOAD_MB", 512) * 1024 * 1024,
    )