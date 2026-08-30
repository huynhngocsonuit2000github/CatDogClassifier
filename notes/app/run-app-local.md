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
