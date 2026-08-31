"""Prediction service (Step 4 of the MLOps plan).

Serves the current Production ``CatDogClassifier`` model dynamically: each
request resolves ``models:/CatDogClassifier/Production``, so promoting a new
version through the Registry changes the served model with no code change and
no restart.
"""