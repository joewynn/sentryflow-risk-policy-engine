import shap
import threading
import pandas as pd
from src.models.train import load_model  # stub – replace with your trained model

def _compute_shap_background(payload: dict, callback):
    """Runs in background thread – never blocks the <30ms fast path"""
    model = load_model()
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(pd.DataFrame([payload]))
    callback(shap_values)  # In prod: send to dashboard via Redis/WebSocket

def start_shadow_shap(payload: dict):
    """Fire-and-forget SHAP (called after fast decision)"""
    thread = threading.Thread(target=_compute_shap_background, args=(payload, lambda x: print(f"SHAP ready: {x}")))
    thread.daemon = True
    thread.start()