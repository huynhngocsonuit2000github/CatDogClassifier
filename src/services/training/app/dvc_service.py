"""Thin, pull-only DVC wrapper for the Training service.

The shared DVC repo is owned by the Data Management service, which handles
``init`` + remote registration + ``add``/``push``. The training side only needs
to materialise a tracked dataset via ``dvc pull``, so this wrapper deliberately
keeps a small surface: it never re-inits the repo or re-registers the remote
(which would clobber the Data Management setup).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path


class DvcRepo:
    def __init__(self, repo_dir: Path, s3_env: dict[str, str]) -> None:
        self.repo_dir = Path(repo_dir)
        self.s3_env = s3_env
        self._lock = threading.Lock()
        self.available = shutil.which("dvc") is not None

    def _enabled(self) -> bool:
        return self.available

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

    def ensure_repo(self) -> None:
        """Create the repo dir if missing and ``dvc init`` only if truly absent."""
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        if not self._enabled():
            return
        with self._lock:
            if not (self.repo_dir / ".dvc").exists():
                # Fresh clone scenario only. Normally the Data Management
                # service has already initialised this repo + remote.
                self._run("init", "--no-scm")

    def pull(self, target: str) -> None:
        """``dvc pull <repo-relative .dvc path>`` (e.g. ``datasets/v1.dvc``)."""
        if not self._enabled():
            raise RuntimeError("`dvc` was not found on PATH; cannot pull data")
        with self._lock:
            self._run("pull", target)