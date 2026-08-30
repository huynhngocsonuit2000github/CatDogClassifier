"""MobileNetV2 transfer-learning model (Step 2).

Small, fast-to-train CNN for the cat/dog binary classifier: a frozen
ImageNet-pretrained MobileNetV2 trunk feeding a GlobalAveragePooling2D head and
a single sigmoid output (>= 0.5 -> "dogs").
"""
from __future__ import annotations

import tensorflow as tf


def build_model(image_size: int = 160, learning_rate: float = 1e-3) -> tf.keras.Model:
    base = tf.keras.applications.MobileNetV2(
        input_shape=(image_size, image_size, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False  # freeze the pretrained trunk

    model = tf.keras.Sequential(
        [
            base,
            tf.keras.layers.GlobalAveragePooling2D(),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(1, activation="sigmoid"),
        ],
        name="catdog-mobilenetv2",
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model