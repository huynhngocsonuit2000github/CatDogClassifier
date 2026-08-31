# Prediction service

A small FastAPI service (port **8003**) that serves the current **Production**
`CatDogClassifier` model — dynamically. Each request resolves
`models:/CatDogClassifier/Production`, so promoting a new version in the Registry
changes the served model with **zero code change and no restart**.

## How it works

1. Resolve the Production version with `MlflowClient.search_model_versions`
   (filter `current_stage == "Production"`; the Registry guarantees at most one).
2. Load it with `mlflow.tensorflow.load_model("models:/<name>/<version>")`
   (the trainer logged a Keras-3 `.keras` model under the `tensorflow` flavor —
   `mlflow.keras.load_model` would `KeyError`). Loaded once, cached by version.
3. Preprocess the uploaded image to match training **exactly**: decode as RGB,
   resize to `160×160` (bilinear), as float32 in `[0, 255]` — **no** rescale and
   **no** `mobilenet_v2.preprocess_input` (the frozen trunk was trained on raw values).
4. Sigmoid output → `p >= 0.5` is `dog`, else `cat`; confidence is `p` (dog) or
   `1 - p` (cat). `class_names = ["cats", "dogs"]`, so class 1 = dog.

## Endpoints

| Method | Path | Body | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | — | liveness + currently-served `model_version` |
| `POST` | `/predict` | multipart `file` (image) | `{ prediction, confidence, model_name, model_version }` |

Errors: `400` if no Production model is registered (or the image can't be
decoded); `503` if the MLflow server is unreachable.

## Run locally

Needs MLflow up first and at least one `Production` model (via the Registry).

```bash
# from src/: docker compose up -d mlflow
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # installs TensorFlow — slow
set MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8003
```

Smoke test:

```bash
curl.exe -X POST http://127.0.0.1:8003/predict -F "file=@path\to\cat.jpg"
```

## Layout

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI routes + CORS + error mapping |
| `app/model_loader.py` | resolve/load/cache the Production model, preprocess, predict |
| `app/config.py` | env-driven `Settings` |

The Docker image is large (~2.8 GB, TensorFlow). For local development the
`uvicorn` route above is the primary path (matching how the Training service is run).