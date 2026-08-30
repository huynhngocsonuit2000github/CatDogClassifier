"""Data Management service.

A standalone FastAPI service (Step 1 of the Cat/Dog MLOps plan) that uploads,
validates, and versions image datasets. Object storage is MinIO (S3-compatible),
and data versioning is handled by DVC.
"""