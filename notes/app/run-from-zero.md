# Clean Up data (if any)

cd "D:\me\TMA AI\CatDogClassifier\src"
docker compose down -v
rmdir /s /q "D:\me\TMA AI\CatDogClassifier\src\services\data-management\data"
rmdir /s /q "D:\me\TMA AI\CatDogClassifier\src\services\prediction\data"

# Run dependencies

cd "D:\me\TMA AI\CatDogClassifier\src"
docker compose up -d minio
docker compose up -d mlflow

# Run UI service

cd "D:\me\TMA AI\CatDogClassifier\src\ui"
npm install
npm run start

# Run Data Management Service http://127.0.0.1:8000/docs#/

cd "D:\me\TMA AI\CatDogClassifier\src\services\data-management"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install "dvc[s3]"
set STORAGE_BACKEND=s3
set S3_ENDPOINT=http://localhost:9000
set S3_ACCESS_KEY=minioadmin
set S3_SECRET_KEY=minioadmin
set S3_BUCKET=datasets
set DVC_MODE=auto
set DVC_REMOTE_PATH=dvc
set DATA_DIR=./data
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Run Training Service http://127.0.0.1:8001/docs#/

cd "D:\me\TMA AI\CatDogClassifier\src\services\training"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
set PYTHONUTF8=1
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# Run Model Registry Service http://127.0.0.1:8002/docs#/

cd "D:\me\TMA AI\CatDogClassifier\src\services\model-registry"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
set MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8002

# Run Prediction Service http://127.0.0.1:8003/docs#/

cd "D:\me\TMA AI\CatDogClassifier\src\services\prediction"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
set MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8003
