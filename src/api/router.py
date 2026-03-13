# src/api/router.py
from fastapi import FastAPI
from pydantic import BaseModel
from src.policies.evaluator import evaluate_policy
from src.api.async_explain import start_shadow_shap
from typing import Dict

# ──────────────────────────────────────────────────────────────
# Pydantic payload (used by both endpoint and internal calls)
# ──────────────────────────────────────────────────────────────
class RiskPayload(BaseModel):
    tx_type: str
    amount: float
    device_is_emulator: bool
    geo_velocity: float
    typing_entropy: float = 4.2          # default for demo
    transaction_id: int
    # Add any other DIBB/vendor fields here

# ──────────────────────────────────────────────────────────────
# FastAPI app (kept here for simplicity; main.py just imports)
# ──────────────────────────────────────────────────────────────
app = FastAPI(title="SentryFlow Risk Engine")

@app.post("/v1/risk-score")
async def get_risk(payload: RiskPayload):
    """
    Main risk endpoint.
    - <30ms fast path (decision + Adverse Action)
    - Background SHAP for Risk Dashboard
    - Supports multi-model routing for SageMaker Inference Components
    """
    # ───── Multi-model routing (Social Eng vs Synthetic ID) ─────
    if payload.tx_type == "WIRE_TRANSFER":
        # Social Engineering / Pig-Butchering ruleset
        rules = [
            {"and": [{"==": ["device_is_emulator", True]}, {">": ["geo_velocity", 500]}]},
            {"if": {"==": ["typing_entropy", 0]}, "action": "REQUIRE_MFA"},
            {"if": {">": ["amount", 5000]}, "action": "DELAY_4H"}
        ]
        target_model = "sentryflow-social-eng-v2"
    else:
        # Synthetic ID ruleset
        rules = [
            {"==": ["device_is_emulator", True]},
            {"if": {"<": ["typing_entropy", 1.0]}, "action": "REQUIRE_VIDEO"}
        ]
        target_model = "sentryflow-synthetic-id-v4"

    # ───── Highest-Severity conflict resolution + audit ─────
    result = evaluate_policy(rules, payload.dict())

    # ───── Async Shadow SHAP (never blocks the fast path) ─────
    start_shadow_shap(payload.dict())

    # ───── Return Nacha/CFPB-ready response ─────
    return {
        "decision": result["decision"],
        "action": result["action"],
        "adverse_action_code": result.get("adverse_action_code"),
        "customer_facing_message": result.get("customer_facing_message"),
        "policy_version": "v2026.03",
        "model_version": "v4.1",
        "target_model": target_model,
        "note": "SHAP explanation queued for Risk Manager dashboard (arrives in ~2s)",
        "audit_id": result["audit"]["decision_id"]
    }