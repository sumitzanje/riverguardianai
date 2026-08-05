class LearningEngine:
    """Placeholder for the local ML layer.

    Stage 1 uses the explainable physics-informed risk engine.
    Stage 2 can add scikit-learn RandomForest/GradientBoosting model inference here.
    """
    def predict(self, features: dict) -> dict:
        return {
            "model_enabled": False,
            "model_risk": None,
            "model_time_to_unsafe_min": None,
        }
