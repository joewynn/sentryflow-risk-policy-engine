# src/api/async_explain.py
import shap
import threading
import pandas as pd
import numpy as np
from src.models.train import load_model

def _compute_shap_background(payload: dict, callback):
    """
    Runs in background thread – never blocks the <30ms fast path.
    Demonstrates 'Asynchronous Explainability' – a key TPM requirement for 2026.
    """
    try:
        model = load_model()
        
        # Check if we are using the real model or the MockModel
        if hasattr(model, 'predict'):
            # Convert dict to DataFrame for SHAP compatibility
            df = pd.DataFrame([payload])
            
            # Simple summary logic for demo purposes
            # In a full prod env, this would use shap.TreeExplainer
            feature_importance = {"amount": 0.4, "geo_velocity": 0.5, "typing_entropy": 0.1}
            callback(feature_importance)
            
    except Exception as e:
        print(f"Background SHAP Error: {str(e)}")

def start_shadow_shap(payload: dict):
    """Fire-and-forget SHAP (called after fast decision)"""
    thread = threading.Thread(
        target=_compute_shap_background, 
        args=(payload, lambda x: print(f"✅ SHAP Analysis for ID {payload.get('transaction_id')}: {x}"))
    )
    thread.daemon = True
    thread.start()