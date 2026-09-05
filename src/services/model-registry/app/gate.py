"""Model promotion gate — evaluation + editable thresholds (Step 3).

A freshly-trained candidate starts as a ``Pending`` version in the MLflow
registry. Before the user may Approve it into ``Staging``, it must pass the
*gate*: a comparison of the run's logged metrics against user-configurable
floors. Today that is two checks:

* ``train_accuracy`` — the final training accuracy must meet
  ``train_accuracy_min`` (catches underfitting).
* ``val_accuracy``   — the hold-out accuracy must meet ``val_accuracy_min``
  (generalization; absent when the dataset was too small to split).

Thresholds are stored as **percentages** (0–100), matching the ``accuracy``
fields the registry DTO already returns, and are editable from the Registry UI
via ``GET/PUT /settings``. The verdict itself is computed on read (not
persisted), so it always reflects the current thresholds.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

# User-editable floors, in percent. Any value missing from the saved file (or
# invalid) falls back to these.
DEFAULT_THRESHOLDS = {
    "train_accuracy_min": 93.0,
    "val_accuracy_min": 90.0,
}

# Checks in display order: (key, label, source metric, threshold key).
_CHECKS = (
    ("train_accuracy", "Training accuracy", "accuracy", "train_accuracy_min"),
    ("val_accuracy", "Validation accuracy", "val_accuracy", "val_accuracy_min"),
)


def _pct(value: float | None) -> float | None:
    """0..1 metric → percent, rounded to one decimal (None stays None)."""
    return round(value * 100, 1) if value is not None else None


def evaluate_gate(metrics: dict, thresholds: dict) -> dict:
    """Score one run's metrics against the thresholds.

    Returns ``{"qualified": bool, "checks": [{key,label,value,threshold,passed}]}``.
    A missing metric (e.g. no validation run for a tiny dataset) fails its
    check, so a candidate cannot be hard-approved without demonstrably hitting
    the bar.
    """
    checks = []
    for key, label, metric_key, threshold_key in _CHECKS:
        value = _pct(metrics.get(metric_key))
        threshold = float(thresholds.get(threshold_key, DEFAULT_THRESHOLDS[threshold_key]))
        checks.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "threshold": round(threshold, 1),
                "passed": value is not None and value >= threshold,
            }
        )
    return {"qualified": all(c["passed"] for c in checks), "checks": checks}


class GateStore:
    """Thread-safe JSON file holding the editable gate thresholds.

    Mirrors ``data-management/app/version_index.py``: atomic write via a temp
    file + ``replace``, tolerant of a missing/corrupt file (falls back to
    defaults).
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def load(self) -> dict:
        """Current thresholds, each merged over its default (invalid → default)."""
        saved = self._read()
        return {
            key: float(saved[key]) if isinstance(saved.get(key), (int, float)) else default
            for key, default in DEFAULT_THRESHOLDS.items()
        }

    def save(self, raw: dict) -> dict:
        """Normalize (clamp 0..100, round 2dp) and persist ``raw``. Returns it."""
        normalized = {}
        for key, default in DEFAULT_THRESHOLDS.items():
            try:
                value = float(raw.get(key, default))
            except (TypeError, ValueError):
                value = default
            normalized[key] = round(min(100.0, max(0.0, value)), 2)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(normalized, fh, indent=2)
            tmp.replace(self.path)
        return normalized