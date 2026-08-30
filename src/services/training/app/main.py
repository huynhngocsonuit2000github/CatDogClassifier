"""Training service — FastAPI application (Step 2 of the MLOps plan).

Endpoints:

* ``GET  /health``        — liveness check.
* ``GET  /datasets``      — available dataset versions (read from the shared
  Data Management index).
* ``POST /train``         — start a training job (async, returns 202 + job id).
* ``GET  /jobs/{job_id}`` — status of one training job.
* ``GET  /runs``          — training runs recorded in MLflow.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import mlflow
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mlflow.tracking import MlflowClient
from pydantic import BaseModel

from .config import Settings, get_settings
from .dvc_service import DvcRepo

logger = logging.getLogger("training")
logging.basicConfig(level=logging.INFO)


class TrainRequest(BaseModel):
    dataset_version: str
    epochs: int | None = None
    batch_size: int | None = None
    learning_rate: float | None = None
    image_size: int | None = None


# In-memory job registry (trainings are short-lived; persisted jobs would need a
# DB, deferred to a later step).
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    dvc = DvcRepo(settings.data_repo, settings.s3_env)
    dvc.ensure_repo()

    # MLflow setup is best-effort: /health and /datasets still work if the
    # tracking server is down; /train and /runs will surface the error then.
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    try:
        mlflow.set_experiment(settings.mlflow_experiment)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MLflow not reachable at %s: %s", settings.mlflow_tracking_uri, exc)

    app.state.settings = settings
    app.state.dvc = dvc
    logger.info(
        "training ready (data_repo=%s, mlflow=%s)",
        settings.data_repo,
        settings.mlflow_tracking_uri,
    )
    yield


app = FastAPI(title="Training service", version="0.1.0", lifespan=lifespan)

# Forward-compatible with the Angular dashboard (Step 5). Dev-wide open CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_catalog(settings: Settings) -> list[dict]:
    """Dataset versions from the shared Data Management index.json."""
    path = settings.index_path
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


@app.get("/health")
def health() -> dict:
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "service": "training",
        "mlflow": settings.mlflow_tracking_uri,
    }


@app.get("/datasets")
def list_datasets() -> dict:
    settings: Settings = app.state.settings
    entries = [
        {
            "version": e.get("version"),
            "name": e.get("name"),
            "images": e.get("images"),
            "cats": e.get("cats"),
            "dogs": e.get("dogs"),
            "status": e.get("status"),
        }
        for e in _read_catalog(settings)
    ]
    return {"total": len(entries), "datasets": entries}


@app.post("/train", status_code=202)
def start_train(req: TrainRequest) -> dict:
    settings: Settings = app.state.settings

    catalog = _read_catalog(settings)
    if not any(e.get("version") == req.dataset_version for e in catalog):
        raise HTTPException(
            status_code=404,
            detail=f"Dataset version {req.dataset_version} not found",
        )

    params = {
        "dataset_version": req.dataset_version,
        "epochs": req.epochs or settings.default_epochs,
        "batch_size": req.batch_size or settings.default_batch_size,
        "learning_rate": (
            req.learning_rate if req.learning_rate is not None else settings.default_learning_rate
        ),
        "image_size": req.image_size or settings.default_image_size,
    }

    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "starting",
            "dataset_version": req.dataset_version,
            "run_id": None,
            "metrics": None,
            "error": None,
            "created_at": _utcnow_iso(),
        }
    threading.Thread(target=_run_training, args=(job_id, params), daemon=True).start()

    return {"job_id": job_id, "status": "starting", **params}


def _set_job(job_id: str, **fields) -> None:
    with _jobs_lock:
        _jobs[job_id].update(fields)


def _run_training(job_id: str, params: dict) -> None:
    from . import trainer  # lazy import: keeps TensorFlow out of API startup

    settings: Settings = app.state.settings
    dvc: DvcRepo = app.state.dvc
    version = params["dataset_version"]

    try:
        _set_job(job_id, status="pulling")
        dvc.pull(f"datasets/{version}.dvc")

        _set_job(job_id, status="training")
        result = trainer.train(settings, params)

        _set_job(
            job_id,
            status="finished",
            run_id=result["run_id"],
            metrics=result["metrics"],
        )
        logger.info("training finished for %s -> run %s", version, result["run_id"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("training failed for %s", version)
        _set_job(job_id, status="failed", error=str(exc))


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@app.get("/runs")
def list_runs() -> dict:
    settings: Settings = app.state.settings
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    try:
        experiment = client.get_experiment_by_name(settings.mlflow_experiment)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"MLflow tracking server unreachable: {exc}",
        )

    if experiment is None:
        return {"total": 0, "runs": []}

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["start_time DESC"],
    )

    records = []
    for run in runs:
        records.append(
            {
                "run_id": run.info.run_id,
                "status": run.info.status,
                "run_name": run.info.run_name,
                "start_time": _iso_ms(run.info.start_time),
                "params": dict(run.data.params),
                "metrics": dict(run.data.metrics),
            }
        )
    return {"total": len(records), "runs": records}


def _iso_ms(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")