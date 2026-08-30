"""Thin DVC wrapper driven via subprocess.

DVC is the data-versioning engine. We shell out to the ``dvc`` executable
(rather than importing DVC's Python API) so the service stays decoupled from a
specific DVC version. In ``auto`` mode, when ``dvc`` is not on ``PATH``, the
service degrades to plain filesystem storage — the version index remains the
source of truth either way.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path


class DvcService:
    def __init__(
        self,
        repo_dir: Path,
        remote_name: str,
        remote_url: str,
        endpoint: str,
        mode: str,
        s3_env: dict[str, str],
    ) -> None:
        self.repo_dir = Path(repo_dir)
        self.remote_name = remote_name
        self.remote_url = remote_url
        self.endpoint = endpoint
        self.mode = mode
        self.s3_env = s3_env
        self._lock = threading.Lock()
        self.available = shutil.which("dvc") is not None
        if mode == "required" and not self.available:
            raise RuntimeError("DVC_MODE=required but `dvc` was not found on PATH")

    def _enabled(self) -> bool:
        return self.mode != "disabled" and self.available

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        env = {**os.environ, **self.s3_env}
        return subprocess.run(
            ["dvc", *args, "-q"],
            cwd=str(self.repo_dir),
            env=env,
            capture_output=True,
            text=True,
            check=check,
        )

    def ensure_initialized(self) -> None:
        """``dvc init`` (if needed) and register the S3 remote."""
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        if not self._enabled():
            return
        with self._lock:
            if not (self.repo_dir / ".dvc").exists():
                # --no-scm: we manage versions via the JSON index, not git commits.
                self._run("init", "--no-scm")
            self._run("remote", "add", "-d", "-f", self.remote_name, self.remote_url)
            if self.endpoint:
                self._run("remote", "modify", self.remote_name, "endpointurl", self.endpoint)

    def _repo_relative(self, path: Path) -> str:
        """Return ``path`` relative to the DVC repo dir (DVC runs with its cwd
        as the repo dir, so targets must be repo-relative)."""
        path = Path(path)
        try:
            return path.resolve().relative_to(self.repo_dir.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def add(self, path: Path) -> Path:
        """Track ``path`` with DVC; returns the generated ``.dvc`` file path."""
        if not self._enabled():
            return path
        rel = self._repo_relative(path)
        with self._lock:
            self._run("add", rel)
        return Path(f"{path}.dvc")

    def push(self, target: str) -> None:
        """Push a tracked target (repo-relative ``.dvc`` path) to the remote."""
        if not self._enabled():
            return
        with self._lock:
            self._run("push", target)

    def pull(self, target: str | None = None) -> None:
        """Pull tracked data from the remote (used by the training service)."""
        if not self._enabled():
            return
        args = ["pull"]
        if target:
            args.append(target)
        with self._lock:
            self._run(*args)