"""Prediction service — FastAPI app (Step 4 of the MLOps plan).

Endpoints:

- ``GET  /health``      — liveness + which model version is served.
- ``POST /predict``     — multipart image upload → preprocess → sigmoid → cat/dog.

The model is resolved dynamically (``models:/<name>/Production``); see
``model_loader.py``.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .model_loader import ModelLoader, NoProductionModelError, preprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prediction")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.loader = ModelLoader(settings)
    logger.info("prediction ready — serving %s from MLflow at %s",
                settings.model_name, settings.mlflow_tracking_uri)
    app.state.loader.warmup()
    yield


app = FastAPI(title="Prediction service", version="0.1.0", lifespan=lifespan)

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
    loader: ModelLoader = app.state.loader
    version = None
    try:
        version = loader.production_version()
    except Exception as exc:  # noqa: BLE001 — health shouldn't fail on an MLflow hiccup
        logger.warning("health: cannot reach MLflow: %s", exc)
    return {
        "status": "ok",
        "service": "prediction",
        "model": settings.model_name,
        "model_version": version,
    }


@app.post("/predict")
async def predict(file: UploadFile = File(...)) -> dict:
    settings: Settings = app.state.settings
    loader: ModelLoader = app.state.loader

    data = await file.read()
    try:
        batch = preprocess(data, settings.image_size)
    except Exception as exc:  # noqa: BLE001 — undecodable bytes = bad request
        raise HTTPException(400, detail=f"Could not decode image: {exc}") from exc

    try:
        probability = loader.predict_probability(batch)
    except NoProductionModelError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface the upstream error clearly
        logger.exception("predict failed")
        raise HTTPException(503, detail=f"MLflow/serving error: {exc}") from exc

    probability = round(probability, 4)
    is_dog = probability >= settings.threshold
    return {
        "prediction": "dog" if is_dog else "cat",
        "confidence": round(probability if is_dog else 1 - probability, 4),
        "model_name": settings.model_name,
        "model_version": loader.served_version,
    }