"""Training + MLflow logging (Step 2).

Loads a dataset version from the shared DVC repo, trains the MobileNetV2
classifier, and records every run to the MLflow tracking server (params,
metrics, the TensorFlow model, and a few artifacts).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import mlflow
import mlflow.tensorflow
import tensorflow as tf

from .config import Settings
from .model import build_model

CLASS_DIRS = ("cats", "dogs")


def _force_utf8(stream) -> None:
    """Make a stream tolerant of Keras's emoji progress bar.

    TensorFlow/Keras writes the ``🏃`` (runner) glyph to stdout while training;
    on Windows the console/pipe defaults to ``cp1252``, which cannot encode it
    and raises ``UnicodeEncodeError`` mid-fit. Reconfigure the stream to UTF-8
    (with replacement) so it degrades gracefully instead of crashing.
    """
    encoding = (getattr(stream, "encoding", None) or "").lower().replace("_", "-")
    if encoding and encoding != "utf-8":
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def count_images(ds_dir: Path) -> int:
    total = 0
    for cls in CLASS_DIRS:
        sub = ds_dir / cls
        if sub.is_dir():
            total += sum(1 for p in sub.iterdir() if p.is_file())
    return total


def load_datasets(ds_dir: Path, image_size: int, batch_size: int, seed: int = 42):
    """Return ``(train_ds, val_ds, class_names)`` from a version directory.

    With very small datasets a 20% split can collapse to zero validation
    images, in which case we train on everything and return ``None`` for
    ``val_ds``.
    """
    args = dict(
        directory=str(ds_dir),
        image_size=(image_size, image_size),
        batch_size=batch_size,
        label_mode="binary",
    )

    full = tf.keras.utils.image_dataset_from_directory(**args, seed=seed)
    class_names = list(full.class_names)

    if count_images(ds_dir) < 5:
        return full, None, class_names

    train = tf.keras.utils.image_dataset_from_directory(
        **args, validation_split=0.2, subset="training", seed=seed
    )
    val = tf.keras.utils.image_dataset_from_directory(
        **args, validation_split=0.2, subset="validation", seed=seed
    )
    return train, val, class_names


def train(settings: Settings, params: dict) -> dict:
    """Train one run and log it to MLflow. Returns run summary info."""
    _force_utf8(sys.stdout)
    _force_utf8(sys.stderr)

    version = params["dataset_version"]
    image_size = params["image_size"]
    batch_size = params["batch_size"]
    epochs = params["epochs"]
    learning_rate = params["learning_rate"]

    ds_dir = settings.datasets_dir / version
    if not ds_dir.is_dir():
        raise FileNotFoundError(f"{ds_dir} missing — did `dvc pull` succeed?")

    train_ds, val_ds, class_names = load_datasets(ds_dir, image_size, batch_size)
    n_images = count_images(ds_dir)

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment)

    with mlflow.start_run(run_name=f"{version}-mobilenetv2") as run:
        mlflow.log_params(
            {
                "dataset_version": version,
                "model_name": "mobilenetv2",
                "epochs": epochs,
                "batch_size": batch_size,
                "learning_rate": learning_rate,
                "image_size": image_size,
                "train_samples": n_images,
            }
        )

        model = build_model(image_size, learning_rate)
        history = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=epochs,
            verbose=1,
        ).history

        metrics = {
            "loss": float(history["loss"][-1]),
            "accuracy": float(history["accuracy"][-1]),
        }
        if val_ds is not None:
            metrics["val_loss"] = float(history["val_loss"][-1])
            metrics["val_accuracy"] = float(history["val_accuracy"][-1])
        mlflow.log_metrics(metrics)

        mlflow.tensorflow.log_model(model, "model")
        mlflow.register_model(
            f"runs:/{run.info.run_id}/model", settings.model_registry_name
        )
        mlflow.log_dict(
            {"class_names": class_names, "threshold": 0.5, "note": "sigmoid >= 0.5 -> dogs"},
            "metadata.json",
        )
        mlflow.log_text(json.dumps(metrics, indent=2), "metrics.json")

        return {
            "run_id": run.info.run_id,
            "metrics": metrics,
            "class_names": class_names,
            "train_samples": n_images,
        }