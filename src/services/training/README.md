# Training service (Step 2)

Trains the cat/dog classifier against a dataset version pulled from the shared
DVC repo, and records every run to MLflow.

```
POST /train  {dataset_version, ...}
   │
   ├─ dvc pull datasets/vN.dvc     (materialise images from MinIO via DVC)
   ├─ MobileNetV2 transfer learning (frozen trunk -> GAP -> Dense(1, sigmoid))
   └─ mlflow.start_run()           (params, metrics, TF model, artifacts)
```

## Prerequisites

1. **MinIO + MLflow** up (from `src/`): `docker compose up -d minio mlflow`.
   - MLflow UI: http://localhost:5000
   > MLflow is pinned to **2.22.4** (`src/docker-compose.yml` + this service's
   > `requirements.txt`). MLflow 3.x moved model storage to "logged models" and
   > stops persisting model files on a plain filesystem artifact root, which
   > would break the later registry/prediction steps. The server command uses
   > `--artifacts-destination` (proxied artifacts) — not `--default-artifact-root`.
2. **`dvc`** on your PATH (already installed for the Data Management service).
3. A **validated dataset** in the shared repo (upload via the Data Management
   service first), so `dvc pull` has something to fetch.

## Run (local dev)

```powershell
cd src\services\training
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# DATA_REPO defaults to ../data-management/data  (the shared DVC repo)
.venv\Scripts\uvicorn app.main:app --port 8001
```

Interactive API docs at http://127.0.0.1:8001/docs.

## Train

```powershell
# List available dataset versions (reads the shared Data Management index)
curl http://127.0.0.1:8001/datasets

# Start a training job on a version (empty ones fall back to TRAIN_* defaults)
curl -X POST http://127.0.0.1:8001/train \
  -H "Content-Type: application/json" \
  -d '{"dataset_version":"v5"}'

# (optional) override hyper-parameters
curl -X POST http://127.0.0.1:8001/train \
  -H "Content-Type: application/json" \
  -d '{"dataset_version":"v5","epochs":20,"learning_rate":0.0005}'
```

`POST /train` returns `202` with a `job_id` immediately; the job runs in a
background thread:

```
curl http://127.0.0.1:8001/jobs/<job_id>   # starting -> pulling -> training -> finished|failed
curl http://127.0.0.1:8001/runs            # all runs recorded in MLflow
```

Then open http://localhost:5000 and select the `catdog` experiment to see the
runs (params, metrics, and the logged TensorFlow model).

## Configuration

See `.env.example`. Key values:

| Var | Default | Purpose |
| --- | --- | --- |
| `DATA_REPO` | `../data-management/data` | Shared DVC repo (path to `.dvc/` + `datasets/`) |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | Tracking server |
| `MLFLOW_EXPERIMENT` | `catdog` | Experiment name (created on startup) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `minioadmin` | Injected into `dvc pull` |
| `TRAIN_EPOCHS` / `TRAIN_BATCH_SIZE` / `TRAIN_LEARNING_RATE` / `TRAIN_IMAGE_SIZE` | `10` / `8` / `0.001` / `160` | Default hyper-params |

## Layout

| File | Concern |
| --- | --- |
| `app/config.py` | Environment-driven settings |
| `app/dvc_service.py` | Pull-only DVC wrapper (subprocess) |
| `app/model.py` | MobileNetV2 transfer model |
| `app/trainer.py` | Dataset loading + fit + MLflow logging |
| `app/main.py` | FastAPI app + routes + background job registry |

> Note: jobs live in memory only (trainings are short). A durable job queue +
> the model registry are the later steps in the plan.