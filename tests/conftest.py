import numpy as np
from unittest.mock import MagicMock, patch


def _make_test_model():
    """Minimal XGBoost-like mock for test isolation — no ZenML or disk access."""
    m = MagicMock()
    m.predict_proba.return_value = np.array([[0.86, 0.14]])
    m.predict.return_value = np.array([0])
    m.get_booster.side_effect = AttributeError("MockModel in test — run make train for real SHAP")
    return m


# Module-level patch (not inside a fixture) so it's active before pytest imports
# test_api.py, which triggers src.api.router module-level model loading.
patch("src.models.train.load_model_from_zenml", return_value=_make_test_model()).start()
