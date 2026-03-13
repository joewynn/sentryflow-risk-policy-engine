# src/api/router.py
from fastapi import APIRouter, HTTPException
from src.policies.evaluator import evaluate_policy, batch_orchestrate
from src.models.train import load_model # Assume this helper exists
import pandas as pd

router = APIRouter()

# Tier 1 Scaling: Load model once at module level (Model Warming)
try:
    ML_MODEL = load_model("xgb_fraud_v2026")
except Exception:
    ML_MODEL = None 

@router.post("/v1/risk-check")
async def risk_check(payload: dict):
    # 1. Evaluate Static Rules
    rules = [{"if": {"var": "device_is_emulator"}, "action": "DECLINE"}] # Mocked for brevity
    rule_res = evaluate_policy(rules, payload)
    
    # 2. Get ML Score
    # We convert payload to DF for vectorized prediction
    input_df = pd.DataFrame([payload])
    ml_score = 0.0
    if ML_MODEL:
        ml_score = float(ML_MODEL.predict_proba(input_df)[:, 1][0])

    # 3. BRIDGE THE GAP: Use the SAME orchestration as the dashboard
    rule_df = pd.DataFrame([rule_res])
    ml_series = pd.Series([ml_score])
    
    orchestrated = batch_orchestrate(rule_df, ml_series)
    
    return {
        "decision": orchestrated['decision'].iloc[0],
        "action": orchestrated['action'].iloc[0],
        "strategy": orchestrated['strategy'].iloc[0], # The missing 'Gray Zone' tag
        "metadata": {
            "ml_score": orchestrated['ml_score'].iloc[0],
            "audit_id": rule_res['audit']['decision_id'],
            "nacha_code": rule_res['adverse_action_code']
        }
    }