# Clean Up data (if any)

> Removes every container **and** the named volumes that hold all platform data
> (MinIO buckets, the shared DVC repo, MLflow store, prediction history). This
> returns the app to a completely empty state; run it before a fresh start.

cd "D:\me\TMA AI\CatDogClassifier\src"
docker compose down -v

# Run every service (API + UI) in Docker
#
# First build is slow: the training and prediction images include TensorFlow
# (~2.8 GB each). MinIO, MLflow, registry and data-management are small.
# Host ports are offset +100 from the local-dev ports so containers can run
# alongside locally-started services without colliding.

cd "D:\me\TMA AI\CatDogClassifier\src"
docker compose up --build

# UI:              http://localhost:4300
# data-management: http://127.0.0.1:8100/docs
# training:        http://127.0.0.1:8101/docs
# model-registry:  http://127.0.0.1:8102/docs
# prediction:      http://127.0.0.1:8103/docs
# MinIO console:   http://localhost:9003
# MLflow:          http://localhost:5000