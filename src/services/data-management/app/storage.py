"""Pluggable object storage backends.

The service has two backends selected via ``STORAGE_BACKEND``:

* ``s3``   — MinIO (S3-compatible). This is the real thing used by the platform.
* ``local`` — a plain directory on disk, handy for development and tests when
  MinIO is not running.

``boto3`` is imported lazily inside :class:`S3Storage` so the service can run in
``local`` mode without it installed.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path


class ObjectStorage(ABC):
    @abstractmethod
    def ensure_bucket(self) -> None:
        """Make sure the target bucket/root exists."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> None:
        """Write ``data`` at ``key``."""

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Read the object at ``key``."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether ``key`` exists."""

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]:
        """List object keys beneath ``prefix``."""


class LocalStorage(ObjectStorage):
    """Store objects under a directory. Set ``STORAGE_BACKEND=local`` to use it."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def ensure_bucket(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def put_bytes(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list_keys(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return [p.relative_to(self.root).as_posix() for p in base.rglob("*") if p.is_file()]


class S3Storage(ObjectStorage):
    """S3-compatible storage (MinIO) via boto3."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
    ) -> None:
        import boto3  # lazy import

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if missing, retrying while MinIO is still starting."""
        last_error: Exception | None = None
        for _ in range(10):
            try:
                self.client.head_bucket(Bucket=self.bucket)
                return
            except Exception as exc:  # noqa: BLE001 - bucket missing or MinIO down
                last_error = exc
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    return
                except Exception as exc2:  # noqa: BLE001
                    last_error = exc2
            time.sleep(1)
        raise RuntimeError(f"Could not ensure bucket '{self.bucket}': {last_error}")

    def put_bytes(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get_bytes(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def list_keys(self, prefix: str) -> list[str]:
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in resp.get("Contents", [])]


def build_storage(settings) -> ObjectStorage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.data_dir / "objects")
    return S3Storage(
        endpoint=settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
    )