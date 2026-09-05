"""MobileNetV2 transfer-learning model (Step 2).

Small, fast-to-train CNN for the cat/dog binary classifier: a frozen
ImageNet-pretrained MobileNetV2 trunk feeding a GlobalAveragePooling2D head and
a single sigmoid output (>= 0.5 -> "dogs").

The full training configuration is wired through here so every field on the
Training page genuinely affects the model:

* ``optimizer`` maps to ``Adam`` / ``AdamW`` / ``SGD`` (all accept
  ``learning_rate`` + ``weight_decay``).
* ``pretrained=False`` drops the ImageNet weights (``weights=None``).
* ``augment`` toggles a short stack of Keras preprocessing layers inserted
  before the trunk (flip / rotation ±15deg / brightness+contrast / random crop
  + resize), so augmentation runs inside the graph and is captured by the
  logged model.
"""
from __future__ import annotations

import tensorflow as tf

# Rotation ±15°, expressed as the fraction of 2pi that RandomRotation expects.
_ROTATION_FACTOR = 15 / 360


def _make_optimizer(name: str, learning_rate: float, weight_decay: float):
    if name == "adamw":
        return tf.keras.optimizers.AdamW(
            learning_rate=learning_rate, weight_decay=weight_decay
        )
    if name == "sgd":
        return tf.keras.optimizers.SGD(
            learning_rate=learning_rate, momentum=0.9, weight_decay=weight_decay
        )
    return tf.keras.optimizers.Adam(
        learning_rate=learning_rate, weight_decay=weight_decay
    )


def _apply_augmentation(x, image_size: int, augment: dict | None):
    """Chain the enabled augmentation layers onto ``x`` (shape-preserving)."""
    if not augment:
        return x
    if augment.get("flip"):
        x = tf.keras.layers.RandomFlip(mode="horizontal")(x)
    if augment.get("rotation"):
        x = tf.keras.layers.RandomRotation(_ROTATION_FACTOR)(x)
    if augment.get("color_jitter"):
        x = tf.keras.layers.RandomBrightness(0.2)(x)
        x = tf.keras.layers.RandomContrast(0.2)(x)
    if augment.get("crop"):
        crop = int(image_size * 0.8)
        x = tf.keras.layers.RandomCrop(crop, crop)(x)
        x = tf.keras.layers.Resizing(image_size, image_size)(x)
    return x


def build_model(
    image_size: int = 160,
    learning_rate: float = 1e-3,
    optimizer: str = "adam",
    weight_decay: float = 0.0,
    pretrained: bool = True,
    augment: dict | None = None,
) -> tf.keras.Model:
    base = tf.keras.applications.MobileNetV2(
        input_shape=(image_size, image_size, 3),
        include_top=False,
        weights="imagenet" if pretrained else None,
    )
    base.trainable = False  # freeze the pretrained trunk

    inputs = tf.keras.Input(shape=(image_size, image_size, 3))
    x = _apply_augmentation(inputs, image_size, augment)
    # ImageNet normalization. ``image_dataset_from_directory`` yields [0, 255]
    # and MobileNetV2's ``include_preprocessing`` is off by default, so without
    # this the pretrained trunk sees out-of-range inputs and its features are
    # useless. This rescale is exactly ``mobilenet_v2.preprocess_input``.
    x = tf.keras.layers.Rescaling(1.0 / 127.5, offset=-1.0)(x)
    x = base(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid")(x)

    model = tf.keras.Model(inputs, outputs, name="catdog-mobilenetv2")
    model.compile(
        optimizer=_make_optimizer(optimizer, learning_rate, weight_decay),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model