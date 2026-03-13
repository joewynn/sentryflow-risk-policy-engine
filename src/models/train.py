# src/models/train.py
import xgboost as xgb
from sklearn.ensemble import IsolationForest
import joblib
import os
import pandas as pd

MODEL_DIR = "data/models"
# Default model name for the async explainer call
DEFAULT_XGB_NAME = "xgb_fraud"

def train_ensemble(X, y):
    """
    Trains the 2026-spec ensemble: 
    XGBoost for supervised fraud patterns + Isolation Forest for anomaly detection.
    """
    # 1. Supervised Model (XGBoost)
    # scale_pos_weight=200 handles the extreme class imbalance (<0.5%)
    # Using 'aucpr' as it is the gold standard for fraud (Precision-Recall)
    xgb_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=200, 
        eval_metric="aucpr",
        use_label_encoder=False
    )
    xgb_model.fit(X, y)
    
    # 2. Unsupervised Model (Isolation Forest)
    # contamination=0.01 assumes 1% of data is anomalous (outliers)
    iso_forest = IsolationForest(contamination=0.01, random_state=42)
    iso_forest.fit(X)
    
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(xgb_model, f"{MODEL_DIR}/{DEFAULT_XGB_NAME}.joblib")
    joblib.dump(iso_forest, f"{MODEL_DIR}/iso_anomaly.joblib")
    
    return xgb_model, iso_forest

def load_model(model_name: str = DEFAULT_XGB_NAME):
    """
    Loads a specific model by name. Defaults to the XGBoost fraud model.
    Includes a fallback MockModel to ensure the API stays live during initial dev.
    """
    path = f"{MODEL_DIR}/{model_name}.joblib"
    
    if os.path.exists(path):
        return joblib.load(path)
    
    # Senior TPM Fallback: Ensure the system doesn't crash if model isn't trained yet
    class MockModel:
        def predict(self, X): return [0] * len(X)
        def predict_proba(self, X): return [[0.98, 0.02]] * len(X)
        @property
        def feature_importances_(self): return [0.1] * 10
        
    return MockModel()