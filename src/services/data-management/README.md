# Data Management service

**Step 1** of the Cat/Dog MLOps platform — a standalone FastAPI service that
uploads, validates, and versions image datasets. Storage is **MinIO** (S3), and
versioning is handled by **DVC**.

```
Dataset (.zip) ─▶ validate ─▶ datasets/vN/ ─▶ dvc add ─▶ dvc push ─▶ MinIO (S3)
                 (schema +   (data repo)     (.dvc file)   (remote)
                  balance)
```

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/datasets` | List dataset versions |
| `POST` | `/datasets` | Upload a ZIP (`file`) + optional `name` → validate + version |
| `GET` | `/datasets/{version}` | Details for one version |

A dataset archive is a ZIP with images under `cats/` and `dogs/` folders. On
upload the service: validates the structure and image integrity → assigns the
next version (`v1`, `v2`, …) → tracks it with DVC → pushes to MinIO in the
background. Status flows `validating → validated` (or `failed`).

## Prerequisites

- Python 3.11+
- [DVC](https://dvc.org/) with S3 support: `pip install "dvc[s3]"`
- Docker (for MinIO), or use local dev mode below

## Quick start

```bash
cd src/services/data-management

# 1. start MinIO (S3)
docker compose up -d minio

# 2. install deps
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install "dvc[s3]"

# 3. run
uvicorn app.main:app --reload --port 8000
```

Then upload a dataset:

```bash
curl -F "file=@catsdogs.zip" -F "name=initial subset" http://localhost:8000/datasets
curl http://localhost:8000/datasets
```

Open the API docs at <http://localhost:8000/docs>.

## Local dev mode (no Docker / DVC)

For a fast smoke test with no external services:

```bash
STORAGE_BACKEND=local DVC_MODE=disabled uvicorn app.main:app --port 8000
```

Objects write to `data/objects/` and the version index to
`data/.datasets/index.json`. DVC is bypassed so `dvc push` becomes a no-op and
versions read `validated` immediately after the raw archive is stored.

## Configuration

See [`.env.example`](.env.example). Key knobs: `STORAGE_BACKEND` (`s3`/`local`),
`S3_*` (MinIO endpoint + credentials), `DVC_MODE` (`auto`/`required`/`disabled`),
`DATA_DIR`, `MAX_UPLOAD_MB`.

## Design notes

- **Separation of concerns** — the version index (JSON) is the source of truth
  for logical versions; DVC (content-addressing) and MinIO (storage) hold the
  bytes. The service never hard-codes a dataset path.
- **Pluggable storage** — `storage.py` provides `S3Storage` (MinIO) and
  `LocalStorage`; `boto3` is imported lazily so local mode needs no AWS deps.
- **DVC via subprocess** — decouples the service from a specific DVC Python API.
- **Next step** — the Training service pulls a dataset version with `dvc pull`,
  so the `.dvc` file path is recorded on each version entry.