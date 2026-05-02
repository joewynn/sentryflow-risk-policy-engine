import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
import joblib
import numpy as np
import os
import warnings

MODEL_DIR = "data/models"
DEFAULT_XGB_NAME = "xgb_fraud"
FEATURE_COLS = [
    "amount",
    "device_is_emulator",
    "geo_velocity",
    "typing_entropy",
    "card_count",           # C1 — number of cards on billing address (fraud MI=0.008)
    "days_since_last_tx",   # D1 — days since last transaction on card (fraud MI=0.006)
]


def train_ensemble(X, y):
    """
    Trains the 2026-spec ensemble:
    XGBoost (supervised focal-loss proxy via scale_pos_weight) for known fraud patterns,
    and Isolation Forest (unsupervised) for zero-day synthetic identity anomalies.
    Caller must pass a pre-split training set — do not pass the full dataset.
    """
    # Internal validation split for eval_metric tracking (separate from the outer test set)
    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.15, random_state=42, stratify=y)

    neg = int((y_tr == 0).sum())
    pos = int((y_tr == 1).sum())
    scale_pos_weight = neg / pos if pos > 0 else 100.0

    xgb_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
    )
    xgb_model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    # Contamination mirrors actual fraud rate in training data (clamped to [0.1%, 10%])
    fraud_rate = pos / (pos + neg) if (pos + neg) > 0 else 0.01
    contamination = min(max(fraud_rate, 0.001), 0.1)
    iso_forest = IsolationForest(contamination=contamination, random_state=42)
    iso_forest.fit(X_tr)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(xgb_model, f"{MODEL_DIR}/{DEFAULT_XGB_NAME}.joblib")
    joblib.dump(iso_forest, f"{MODEL_DIR}/iso_anomaly.joblib")

    return xgb_model, iso_forest


def load_model(model_name: str = DEFAULT_XGB_NAME):
    """
    Loads a trained model by name. Falls back to MockModel if the file doesn't exist.
    MockModel is an explicit dev-only fallback — run 'make train' to build a real model.
    """
    path = f"{MODEL_DIR}/{model_name}.joblib"
    if os.path.exists(path):
        return joblib.load(path)

    warnings.warn(
        f"Model file not found at '{path}'. Using MockModel (neutral 2% fraud score). "
        "Run 'make train' to build a real model.",
        RuntimeWarning,
        stacklevel=2,
    )

    class MockModel:
        def predict(self, X):
            return np.zeros(len(X), dtype=int)

        def predict_proba(self, X):
            n = len(X) if hasattr(X, "__len__") else 1
            return np.tile([0.98, 0.02], (n, 1))

        @property
        def feature_importances_(self):
            return np.full(len(FEATURE_COLS), 1.0 / len(FEATURE_COLS))

        def get_booster(self):
            raise AttributeError("MockModel has no booster — run 'make train' first")

    return MockModel()
