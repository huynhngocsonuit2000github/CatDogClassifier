# Training service (Step 2). Same shape as data-management: needs git + dvc[s3]
# for `dvc pull` on the shared repo, plus TensorFlow for the model itself.
FROM python:3.11-slim

# git is required by DVC remote operations (`dvc pull`).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "dvc[s3]"

COPY app ./app

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]