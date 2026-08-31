"""Model Registry service — FastAPI app (Step 3 of the MLOps plan).

Exposes the MLflow Model Registry as a small REST API. Endpoints:

- ``GET  /health``                                   — liveness.
- ``GET  /models``                                   — list every version (enriched).
- ``POST /models/{name}/{version}/stage``            — move a version's stage.
- ``POST /models/{name}/register``                   — backfill a trained run.

See ``registry.py`` for the external↔native stage mapping.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import Settings, get_settings
from .registry import EXTERNAL_STAGES, Registry, RegistryError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model-registry")


class StageRequest(BaseModel):
    stage: str


class RegisterRequest(BaseModel):
    run_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.registry = Registry(settings)
    logger.info("model-registry ready — mlflow at %s", settings.mlflow_tracking_uri)
    yield


app = FastAPI(title="Model Registry service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    settings: Settings = app.state.settings
    return {"status": "ok", "service": "model-registry", "mlflow": settings.mlflow_tracking_uri}


@app.get("/models")
def list_models() -> dict:
    registry: Registry = app.state.registry
    try:
        return {"models": registry.list_models()}
    except Exception as exc:  # noqa: BLE001 — surface the upstream error clearly
        logger.exception("list_models failed")
        raise HTTPException(503, detail=f"MLflow tracking server unreachable: {exc}") from exc


@app.post("/models/{name}/{version}/stage")
def set_stage(name: str, version: str, req: StageRequest) -> dict:
    registry: Registry = app.state.registry
    if req.stage not in EXTERNAL_STAGES:
        allowed = ", ".join(EXTERNAL_STAGES)
        raise HTTPException(422, detail=f"Invalid stage {req.stage!r}; expected one of {allowed}")
    try:
        return {"models": registry.transition(name, version, req.stage)}
    except RegistryError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("transition failed")
        raise HTTPException(502, detail=f"MLflow error: {exc}") from exc


@app.post("/models/{name}/register")
def register(name: str, req: RegisterRequest) -> dict:
    registry: Registry = app.state.registry
    try:
        return {"models": registry.register(name, req.run_id)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("register failed")
        raise HTTPException(502, detail=f"Registration failed: {exc}") from exc