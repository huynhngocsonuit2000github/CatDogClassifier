# Run UI: http://localhost:4200

cd "D:\me\TMA AI\CatDogClassifier\src\ui>"
npm run start

# Run data-management servide: http://127.0.0.1:8000/docs#/

## Run MiniIO if not exists

cd "D:\me\TMA AI\CatDogClassifier\src"
docker compose up -d minio

## Run local app

cd "D:\me\TMA AI\CatDogClassifier\src\services\data-management"

py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install "dvc[s3]"

## Run the service

$env:STORAGE_BACKEND = "s3"
$env:S3_ENDPOINT = "http://localhost:9000"
$env:S3_ACCESS_KEY   = "minioadmin"
$env:S3_SECRET_KEY = "minioadmin"
$env:S3_BUCKET       = "datasets"
$env:DVC_MODE = "auto"
$env:DVC_REMOTE_PATH = "dvc"
$env:DATA_DIR = "./data"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# MiniIO: http://localhost:9003

# MLFlow: http://localhost:5000/

# Run training service: http://127.0.0.1:8001/docs

## First time only (needs MLFlow up first: `docker compose up -d mlflow`)

cd "D:\me\TMA AI\CatDogClassifier\src\services\training"
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

## Run the service

$env:PYTHONUTF8 = "1"   # Windows: avoids cp1252 crash on Keras/MLflow emoji output
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
