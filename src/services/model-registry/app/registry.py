"""MLflow Model Registry wrapper + stage mapping (Step 3).

This is the only place that knows the model lives in MLflow. The rest of the
platform works in terms of the UI's 5 external stages; this module translates
them to MLflow's 4 native stages.

External stage           MLflow native            Rule
``Pending``              ``None``                 new versions start here
``Staging``              ``Staging``              direct
``Production``           ``Production``           promote archives old winner
``Archived``             ``Archived``             direct
``Rejected``             ``Archived`` + tag       tag ``rejected="true"``
"""
from __future__ import annotations

import logging

import mlflow
from mlflow.tracking import MlflowClient

from .config import Settings

logger = logging.getLogger("model-registry")

# MLflow native (canonical) stages — these are the ONLY strings MLflow 2.x
# accepts in ``transition_model_version_stage``.
NATIVE_NONE = "None"
NATIVE_STAGING = "Staging"
NATIVE_PRODUCTION = "Production"
NATIVE_ARCHIVED = "Archived"

# The UI's 5-stage typology (mirrors ``ModelStage`` in ``core/models.ts``).
EXTERNAL_STAGES = ("Pending", "Staging", "Production", "Archived", "Rejected")

# Tag we set when rejecting a version, to tell "Archived (rejected)" apart from
# "Archived (ex-Production)" on read-back.
REJECTED_TAG = "rejected"


class RegistryError(Exception):
    """A lifecycle guard was violated (mapped to HTTP 409 by ``main.py``)."""


def external_to_native(stage: str) -> str:
    """Map an external stage to its 'pure' MLflow stage (reject handled separately)."""
    if stage == "Pending":
        return NATIVE_NONE
    if stage == "Rejected":
        # Same destination as Archived; the caller adds the rejected tag.
        return NATIVE_ARCHIVED
    return stage  # Staging / Production / Archived map directly


def native_to_external(stage: str | None, tags: dict[str, str] | None) -> str:
    """Map an MLflow stage (+ tags) back to an external stage."""
    if stage in (None, NATIVE_NONE):
        return "Pending"
    if stage == NATIVE_ARCHIVED and (tags or {}).get(REJECTED_TAG) == "true":
        return "Rejected"
    return stage  # Staging / Production / Archived map directly


def _version_num(version: str) -> str:
    """'v3' or '3' → '3' (the integer MLflow expects)."""
    v = str(version)
    return v[1:] if v.startswith("v") else v


class Registry:
    """Thin MLflow client wrapper with the stage mapping baked in."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        self._client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)

    # -- queries ---------------------------------------------------------

    def list_models(self) -> list[dict]:
        """Every registered version (all names), enriched from its source run."""
        models = []
        for mv in self._client.search_model_versions():
            if not mv.name or not mv.run_id:
                continue
            dto = self._to_dto(mv)
            if dto is not None:
                models.append(dto)
        models.sort(key=lambda m: (m["name"], _int_version(m["version"])))
        return models

    def _to_dto(self, mv) -> dict:
        run_id = mv.run_id
        try:
            run = self._client.get_run(run_id)
        except Exception as exc:  # noqa: BLE001 — a missing run shouldn't sink the list
            logger.warning("run %s for %s unavailable: %s", run_id, mv.name, exc)
            run = None
        params = run.data.params if run is not None else {}
        metrics = run.data.metrics if run is not None else {}

        accuracy = metrics.get("accuracy")
        loss = metrics.get("loss")
        return {
            "name": mv.name,
            "version": f"v{mv.version}",
            "stage": native_to_external(mv.current_stage, dict(mv.tags or {})),
            "run_id": run_id,
            "dataset_version": params.get("dataset_version", ""),
            "size_mb": round(self._model_size_mb(run_id), 1),
            "accuracy": round(accuracy * 100, 1) if accuracy is not None else 0.0,
            "loss": round(loss, 3) if loss is not None else 0.0,
        }

    def _model_size_mb(self, run_id: str) -> float:
        """Total bytes of the logged model's artifact files, in MiB.

        Traverses the ``model/`` artifact tree recursively — the weights live a
        level down (e.g. ``model/data/model.keras``) under the ``mlflow.keras``
        flavour, so a single-level listing would report only the metadata files.
        """
        total = 0

        def walk(path: str) -> None:
            nonlocal total
            for art in self._client.list_artifacts(run_id, path=path):
                if art.is_dir:
                    walk(art.path)
                elif art.file_size:
                    total += art.file_size

        walk("model")
        return total / 1e6

    # -- mutations -------------------------------------------------------

    def register(self, name: str, run_id: str) -> list[dict]:
        """Register a finished run as a new version of ``name`` (idempotent).

        Used to backfill runs trained before Step 3 landed; ``mlflow.register_model``
        auto-creates the registered model on first use and assigns the next
        integer version.
        """
        for mv in self._client.search_model_versions(f"name='{name}'"):
            if mv.run_id == run_id:
                logger.info("run %s already registered as %s v%s", run_id, name, mv.version)
                return self.list_models()
        mlflow.register_model(f"runs:/{run_id}/model", name)
        return self.list_models()

    def transition(self, name: str, version: str, stage: str) -> list[dict]:
        """Move ``name``/``version`` to an external stage, guarding the lifecycle.

        Returns the refreshed list. Guards mirror the UI buttons in
        ``pages/registry/registry.ts``.
        """
        mv = self._find_version(name, version)
        if mv is None:
            raise RegistryError(f"Model {name} has no version '{version}'")
        native_version = version_int = str(mv.version)
        current = native_to_external(mv.current_stage, dict(mv.tags or {}))

        if stage == "Staging":
            if current != "Pending":
                raise RegistryError(f"{name} v{native_version} is {current}, not Pending — cannot approve")
            self._client.transition_model_version_stage(name, version_int, NATIVE_STAGING)

        elif stage == "Production":
            # Simple model: promote the winner straight to Production, auto-archiving
            # whoever currently holds it. Re-promoting the live version is a no-op.
            if current != "Production":
                self._client.transition_model_version_stage(
                    name, version_int, NATIVE_PRODUCTION, archive_existing_versions=True
                )

        elif stage == "Rejected":
            if current not in ("Pending", "Staging"):
                raise RegistryError(f"{name} v{native_version} is {current} — only Pending/Staging can be rejected")
            self._client.transition_model_version_stage(name, version_int, NATIVE_ARCHIVED)
            self._client.set_model_version_tag(name, version_int, REJECTED_TAG, "true")

        elif stage == "Archived":
            if current not in ("Staging", "Production"):
                raise RegistryError(f"{name} v{native_version} is {current} — only Staging/Production can be archived")
            self._client.transition_model_version_stage(name, version_int, NATIVE_ARCHIVED)

        elif stage == "Pending":
            # Reset an archived/rejected candidate back to pending (clears the tag).
            if current not in ("Archived", "Rejected"):
                raise RegistryError(f"{name} v{native_version} is {current} — only Archived/Rejected can be reset to Pending")
            self._client.transition_model_version_stage(name, version_int, NATIVE_NONE)
            self._client.set_model_version_tag(name, version_int, REJECTED_TAG, "false")

        else:  # pragma: no cover — validated upstream
            raise RegistryError(f"Unknown stage {stage!r}")

        return self.list_models()

    def _find_version(self, name: str, version: str):
        target = _version_num(version)
        for mv in self._client.search_model_versions(f"name='{name}'"):
            if str(mv.version) == target:
                return mv
        return None


def _int_version(version: str) -> int:
    """Sort key: 'v3'/'3' → 3 so v10 follows v9, not v1."""
    try:
        return int(_version_num(version))
    except ValueError:
        return 0