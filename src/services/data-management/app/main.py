"""Data Management service — FastAPI application (Step 1 of the MLOps plan).

Endpoints:

* ``GET  /health``            — liveness check.
* ``GET  /datasets``          — list dataset versions.
* ``POST /datasets``          — upload a ZIP of labelled images (multipart
  ``file`` + optional ``name``); validates, versions via DVC, and stores it.
* ``GET  /datasets/{version}``— details for one version.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .dvc_service import DvcService
from .schemas import DatasetList, DatasetVersion, HealthResponse
from .storage import ObjectStorage, build_storage
from .validation import validate_archive
from .version_index import VersionIndex, utcnow_iso

logger = logging.getLogger("data-management")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    storage = build_storage(settings)
    storage.ensure_bucket()

    dvc = DvcService(
        repo_dir=settings.data_dir,
        remote_name=settings.dvc_remote_name,
        remote_url=settings.dvc_remote_url(),
        endpoint=settings.s3_endpoint,
        mode=settings.dvc_mode,
        s3_env={
            "AWS_ACCESS_KEY_ID": settings.s3_access_key,
            "AWS_SECRET_ACCESS_KEY": settings.s3_secret_key,
        },
    )
    dvc.ensure_initialized()

    app.state.settings = settings
    app.state.storage = storage
    app.state.index = VersionIndex(settings.index_path)
    app.state.dvc = dvc
    logger.info("data-management ready (backend=%s, dvc=%s)", settings.storage_backend, dvc.mode)
    yield


app = FastAPI(title="Data Management service", version="0.1.0", lifespan=lifespan)

# Forward-compatible with the Angular dashboard (Step 5). Dev-wide open CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok", "service": "data-management"}


@app.get("/datasets", response_model=DatasetList)
def list_datasets() -> dict:
    entries = app.state.index.list()
    return {"total": len(entries), "datasets": entries}


@app.get("/datasets/{version}", response_model=DatasetVersion)
def get_dataset(version: str) -> dict:
    entry = app.state.index.get(version)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Dataset version {version} not found")
    return entry


@app.post("/datasets", status_code=202, response_model=DatasetVersion)
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str | None = Form(None),
) -> dict:
    settings: Settings = app.state.settings
    index: VersionIndex = app.state.index
    dvc: DvcService = app.state.dvc

    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds the maximum size")

    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp) / "extract"
        try:
            report = validate_archive(raw, extract_dir)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        if not report.ok:
            raise HTTPException(
                status_code=422,
                detail="Archive contains no valid cat or dog images",
            )

        version = index.next_version()
        target_dir = settings.datasets_dir / version
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(extract_dir), str(target_dir))

        # Local, fast: content-address the dataset with DVC. The `.dvc` file is
        # stored repo-relative so the background push can target it.
        dvc_file: Path = dvc.add(target_dir)
        dvc_rel = dvc_file.relative_to(settings.data_dir).as_posix()

        created = index.create(
            {
                "version": version,
                "name": name or file.filename,
                "images": report.images,
                "cats": report.cats,
                "dogs": report.dogs,
                "cat_pct": report.cat_pct,
                "status": "validating",
                "object_key": f"raw/{version}.zip",
                "dvc_file": dvc_rel,
                "warnings": report.warnings,
                "created_at": utcnow_iso(),
            }
        )

    background_tasks.add_task(_finalize, version, raw, dvc_rel)
    return created


def _finalize(version: str, raw_zip: bytes, dvc_rel: str) -> None:
    """Upload the raw archive to object storage, ``dvc push``, mark validated."""
    storage: ObjectStorage = app.state.storage
    index: VersionIndex = app.state.index
    dvc: DvcService = app.state.dvc

    entry = index.get(version) or {}
    warnings = list(entry.get("warnings", []))
    try:
        storage.put_bytes(f"raw/{version}.zip", raw_zip)
        dvc.push(dvc_rel)
        index.update(version, status="validated")
        logger.info("dataset %s validated (%s images)", version, entry.get("images"))
    except Exception as exc:  # noqa: BLE001 — record failure, keep serving
        logger.exception("finalize failed for dataset %s", version)
        warnings.append(f"finalize failed: {exc}")
        index.update(version, status="failed", warnings=warnings)