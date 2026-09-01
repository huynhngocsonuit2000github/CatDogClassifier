# Run the app locally

> These commands target **cmd.exe** (a plain Windows Command Prompt, `(.venv) D:\...>`).
> In PowerShell the env-var syntax differs: `$env:VAR = "value"` instead of
> `set VAR=value`, and `.venv\Scripts\Activate.ps1` to activate a venv.
> `python` here is 3.11.15 — `py -3.11` is **not** wired up (it resolves to 3.12),
> so create every venv with `python -m venv`.

---

# Run UI: http://localhost:4200

cd "D:\me\TMA AI\CatDogClassifier\src\ui"
npm run start

# Run data-management service: http://127.0.0.1:8000/docs#/

## Run MiniIO if not exists

cd "D:\me\TMA AI\CatDogClassifier\src"
docker compose up -d minio

## First time only

cd "D:\me\TMA AI\CatDogClassifier\src\services\data-management"

python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install "dvc[s3]"

## Run the service

set STORAGE_BACKEND=s3
set S3_ENDPOINT=http://localhost:9000
set S3_ACCESS_KEY=minioadmin
set S3_SECRET_KEY=minioadmin
set S3_BUCKET=datasets
set DVC_MODE=auto
set DVC_REMOTE_PATH=dvc
set DATA_DIR=./data
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# MiniIO: http://localhost:9003

# MLFlow: http://localhost:5000/

# Run training service: http://127.0.0.1:8001/docs

## First time only (needs MLFlow up first: `docker compose up -d mlflow`)

cd "D:\me\TMA AI\CatDogClassifier\src\services\training"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

## Run the service

set PYTHONUTF8=1
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# Run model-registry service: http://127.0.0.1:8002/docs

## First time only (needs MLFlow up first: `docker compose up -d mlflow`)

cd "D:\me\TMA AI\CatDogClassifier\src\services\model-registry"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

## Run the service

set MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8002

## Backfill the 3 finished MLflow runs as CatDogClassifier v1/v2/v3

Idempotent — an already-registered run is skipped (no duplicate version).
`curl.exe` (not `curl`) so PowerShell doesn't alias it to Invoke-WebRequest.

curl.exe -X POST http://127.0.0.1:8002/models/CatDogClassifier/register -H "Content-Type: application/json" -d "{\"run_id\":\"bc75a16d19a44de0bc3f756b44fbb994\"}"
curl.exe -X POST http://127.0.0.1:8002/models/CatDogClassifier/register -H "Content-Type: application/json" -d "{\"run_id\":\"e729a099dbb7451ca200d3618a1cd0fb\"}"
curl.exe -X POST http://127.0.0.1:8002/models/CatDogClassifier/register -H "Content-Type: application/json" -d "{\"run_id\":\"559a3d1fa1254b579b6260190b7385eb\"}"

## Drive the lifecycle (approve -> promote -> archive/reject)

Either use the Registry page in the UI, or the API:

curl.exe -X POST http://127.0.0.1:8002/models/CatDogClassifier/v1/stage -H "Content-Type: application/json" -d "{\"stage\":\"Staging\"}"
curl.exe -X POST http://127.0.0.1:8002/models/CatDogClassifier/v1/stage -H "Content-Type: application/json" -d "{\"stage\":\"Production\"}"

# Run prediction service: http://127.0.0.1:8003/docs

## First time only (needs MLflow up first: `docker compose up -d mlflow`, plus at least one Production model — see Registry above)

cd "D:\me\TMA AI\CatDogClassifier\src\services\prediction"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

> This installs TensorFlow (a large download): slow the first time.

## Run the service

set MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8003

> Optional overrides (all have defaults — see `.env.example`):
> `set REGISTER_MODEL_NAME=CatDogClassifier`, `set IMAGE_SIZE=160`, `set PREDICT_THRESHOLD=0.5`, `set PREDICTIONS_DB_PATH=./data/predictions.db`.

## Smoke test

> `/health` reports which model version is currently served:

curl.exe http://127.0.0.1:8003/health

> `/predict` takes an image file (e.g. one from a pulled dataset):

curl.exe -X POST http://127.0.0.1:8003/predict -F "file=@path\to\cat.jpg"

> The served model is resolved dynamically as `models:/CatDogClassifier/Production`.
> Promote a different version in the Registry and `/predict` switches to it with
> no restart and no code change.

## Prediction history

> History is stored in SQLite (`data/predictions.db`), not the browser, so it
> survives reloads and is cleaned with the rest of the data. `GET /predictions`
> lists it; `DELETE /predictions` clears it (there's a "Clear history" button on
> the Predict page).
>
> curl.exe http://127.0.0.1:8003/predictions
> curl.exe -X DELETE http://127.0.0.1:8003/predictions