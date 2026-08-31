# Model Registry service

A small FastAPI service (port **8002**) that wraps MLflow's Model Registry so
the platform can version `CatDogClassifier` models and move them through a
lifecycle — **Pending → Staging → Production → Archived** — without any model
path in application code.

## How it works

The service is an **MLflow client**. It talks to the same MLflow server used by
Tracking (`MLFLOW_TRACKING_URI`) and maps the UI's 5-stage typology onto
MLflow's 4 native stages:

| External stage | MLflow native |
| --- | --- |
| `Pending` | `None` |
| `Staging` | `Staging` |
| `Production` | `Production` (promote archives the old winner) |
| `Archived` | `Archived` |
| `Rejected` | `Archived` + version tag `rejected="true"` |

## Endpoints

| Method | Path | Body | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | — | liveness |
| `GET` | `/models` | — | list every registered version (enriched from its source run) |
| `POST` | `/models/{name}/{version}/stage` | `{"stage": "Staging"}` | move a version's stage |
| `POST` | `/models/{name}/register` | `{"run_id": "…"}` | backfill a finished run as a new version |

`version` is the UI-style `"v3"` (the service strips the `v`). `GET /models`
returns snake_case wire DTOs matching the UI's `ModelVersion`.

## Run locally

```bash
# 1. MLflow server up (from src/): docker compose up -d mlflow
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8002
```

With `MLFLOW_TRACKING_URI` pointing at the running server (default
`http://localhost:5000`).

## Layout

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI routes + CORS |
| `app/registry.py` | `MlflowClient` wrapper + stage mapping |
| `app/config.py` | env-driven `Settings` |