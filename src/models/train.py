import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
import joblib
import numpy as np
import pandas as pd
import os
import warnings
import mlflow
import hashlib
import subprocess
import time

MODEL_DIR = "data/models"
DEFAULT_XGB_NAME = "xgb_fraud"
FEATURE_COLS = [
    # Phase 1: Core DIBB signals (6 features)
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
    MLflow run is started here; metrics logged separately in the pipeline.
    Returns: (xgb_model, iso_forest, mlflow_run_id)
    """
    # Capture git hash for reproducibility
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        git_sha = "unknown"

    # Versioned artifact path: data/models/<timestamp>_<git_sha>/
    run_ts = int(time.time())
    version_tag = f"{run_ts}_{git_sha}"
    model_dir = f"{MODEL_DIR}/{version_tag}"
    os.makedirs(model_dir, exist_ok=True)

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

    # Compute data fingerprint
    try:
        data_hash = hashlib.md5(pd.util.hash_pandas_object(X, index=True).values).hexdigest()[:8]
    except Exception:
        data_hash = "unknown"

    with mlflow.start_run(run_name=f"train_{version_tag}") as run:
        # Log hyperparameters
        mlflow.log_params({
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "scale_pos_weight": round(scale_pos_weight, 2),
            "contamination": round(contamination, 4),
            "n_features": len(X.columns),
            "feature_cols": ",".join(X.columns.tolist()),
            "git_sha": git_sha,
            "data_hash": data_hash,
        })

        # Save versioned artifacts
        xgb_path = f"{model_dir}/xgb_fraud.joblib"
        iso_path = f"{model_dir}/iso_anomaly.joblib"
        joblib.dump(xgb_model, xgb_path)
        joblib.dump(iso_forest, iso_path)

        # Also keep "latest" symlinks for the API to load
        joblib.dump(xgb_model, f"{MODEL_DIR}/xgb_fraud_latest.joblib")
        joblib.dump(iso_forest, f"{MODEL_DIR}/iso_anomaly_latest.joblib")

        # Log artifacts
        mlflow.log_artifact(xgb_path, artifact_path="models")
        mlflow.log_artifact(iso_path, artifact_path="models")
        mlflow.log_text(",".join(X.columns.tolist()), "feature_cols.txt")

        mlflow_run_id = run.info.run_id

    return xgb_model, iso_forest, mlflow_run_id


def load_model(model_name: str = None):
    """
    Loads a trained model by name. Default loads xgb_fraud_latest.joblib.
    Falls back to MockModel if the file doesn't exist.
    MockModel is an explicit dev-only fallback — run 'make train' to build a real model.
    """
    if model_name is None:
        model_name = "xgb_fraud_latest"

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
