"""Thread-safe JSON-backed index of dataset versions.

DVC content-addresses the actual image blobs; this index is the source of truth
for the *logical* versions (``v1``, ``v2``, …) — one entry per version with its
metadata (counts, balance, status, object key, DVC file, timestamp).
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _version_number(version: str) -> int:
    match = re.search(r"(\d+)$", version)
    return int(match.group(1)) if match else 0


class VersionIndex:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2, ensure_ascii=False)
        tmp.replace(self.path)

    def list(self) -> list[dict]:
        with self._lock:
            entries = self._read()
        return sorted(entries, key=lambda e: _version_number(e.get("version", "")))

    def get(self, version: str) -> Optional[dict]:
        with self._lock:
            for entry in self._read():
                if entry.get("version") == version:
                    return dict(entry)
        return None

    def next_version(self, prefix: str = "v") -> str:
        with self._lock:
            entries = self._read()
        if not entries:
            return f"{prefix}1"
        return f"{prefix}{max(_version_number(e.get('version', '')) for e in entries) + 1}"

    def create(self, entry: dict) -> dict:
        with self._lock:
            entries = self._read()
            entries.append(entry)
            self._write(entries)
        return entry

    def update(self, version: str, **fields: Any) -> Optional[dict]:
        with self._lock:
            entries = self._read()
            for entry in entries:
                if entry.get("version") == version:
                    entry.update(fields)
                    self._write(entries)
                    return dict(entry)
        return None