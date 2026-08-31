"""Dynamic serving of the Production model (Step 4 of the MLOps plan).

Resolves ``models:/CatDogClassifier/Production`` on the fly but only actually
reloads the Keras model when the Production *version* changes, so a promotion
through the Registry takes effect with no code change and no restart.
"""
from __future__ import annotations

import logging
import threading

import mlflow
import mlflow.tensorflow  # noqa: F401 — registers the tensorflow load path
import numpy as np
import tensorflow as tf
from mlflow.tracking import MlflowClient

logger = logging.getLogger("prediction")


class NoProductionModelError(Exception):
    """No model version is in Production yet (mapped to HTTP 400 by ``main.py``)."""


def preprocess(data: bytes, size: int) -> np.ndarray:
    """Decode raw image bytes into the exact tensor the model was trained on.

    This must mirror ``image_dataset_from_directory`` byte-for-byte: decode as
    RGB (channels=3), resize to ``(size, size)`` with bilinear interpolation,
    producing float32 **in [0, 255]** — NO rescale to [0, 1] and NO
    ``mobilenet_v2.preprocess_input``. The frozen MobileNetV2 trunk was trained
    on that raw range, so feeding anything else silently shifts its features.
    """
    img = tf.image.decode_image(data, channels=3, expand_animations=False)  # uint8 (H, W, 3)
    img = tf.image.resize(img, (size, size), method="bilinear")  # float32 (size, size, 3), [0,255]
    return np.expand_dims(img.numpy(), axis=0)  # (1, size, size, 3)


class ModelLoader:
    """Resolves + loads the current Production model, cached across requests.

    ``mlflow.tensorflow.load_model`` re-downloads the artifacts on every call,
    so the loaded ``tf.keras.Model`` is kept in-process and only replaced when
    ``production_version()`` reports a different version than the one served.
    """

    def __init__(self, settings) -> None:
        self.settings = settings
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        self._client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
        self._lock = threading.Lock()
        self._served_version: str | None = None
        self._model = None

    @property
    def served_version(self) -> str | None:
        """The model version currently loaded (e.g. ``"v1"``); None until first load."""
        return self._served_version

    def _production_version_int(self) -> str | None:
        """The integer Production version (e.g. ``"1"``), or None.

        ``current_stage`` can't be filtered server-side in mlflow 2.22, so we
        filter client-side. The registry's promotion archives the previous
        winner, guaranteeing at most one Production version.
        """
        mvs = [
            mv
            for mv in self._client.search_model_versions(f"name='{self.settings.model_name}'")
            if mv.current_stage == "Production"
        ]
        if not mvs:
            return None
        return str(max(int(mv.version) for mv in mvs))

    def production_version(self) -> str | None:
        """The Production version as displayed (e.g. ``"v1"``), or None."""
        version = self._production_version_int()
        return None if version is None else f"v{version}"

    def _require_production_int(self) -> str:
        version = self._production_version_int()
        if version is None:
            raise NoProductionModelError(
                "No Production model registered — promote a version in the Registry first."
            )
        return version

    def get_model(self):
        """Return the loaded model, reloading only if the Production version changed."""
        version_int = self._require_production_int()
        served = f"v{version_int}"
        if served != self._served_version:
            with self._lock:
                # Re-check under the lock so concurrent requests don't double-load.
                version_int = self._require_production_int()
                served = f"v{version_int}"
                if served != self._served_version:
                    logger.info("loading %s v%s from MLflow…", self.settings.model_name, version_int)
                    # `models:/<name>/<version>` needs the *integer* version
                    # ("1"), not the "v1" display string (that would be read as
                    # an invalid stage).
                    self._model = mlflow.tensorflow.load_model(
                        f"models:/{self.settings.model_name}/{version_int}",
                        keras_model_kwargs={"compile": False},
                    )
                    self._served_version = served
        return self._model

    def predict_probability(self, x: np.ndarray) -> float:
        """P(dog) in [0, 1] — the single sigmoid unit's output."""
        return float(self.get_model().predict(x, verbose=0)[0, 0])

    def warmup(self) -> None:
        """Best-effort: load + run one dummy prediction so the first real request is fast.

        Runs inside ``lifespan`` but never fails startup — the service still boots
        (and ``/predict`` responds 400) if no Production model is registered yet.
        """
        try:
            if self.production_version() is not None:
                size = self.settings.image_size
                dummy = np.zeros((1, size, size, 3), dtype="float32")
                self.get_model().predict(dummy, verbose=0)
                logger.info("model %s loaded and warmed up", self._served_version)
            else:
                logger.warning("no Production model yet — /predict will return 400 until one is promoted")
        except Exception as exc:  # noqa: BLE001 — warmup is best-effort
            logger.warning("warmup skipped: %s", exc)