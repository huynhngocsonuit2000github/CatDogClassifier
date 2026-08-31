"""Model Registry service (Step 3 of the MLOps plan).

Wraps MLflow's Model Registry so the rest of the platform can version
``CatDogClassifier`` models and move them through
``Pending → Staging → Production → Archived`` without hard-coding any model
path. Prediction (Step 4) will resolve ``models:/CatDogClassifier/Production``.
"""