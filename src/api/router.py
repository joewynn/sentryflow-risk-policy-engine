# src/api/router.py
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.policies.evaluator import evaluate_policy, batch_orchestrate
from src.api.async_explain import start_shadow_shap
from src.models.train import load_model, FEATURE_COLS

import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter()

# Tier 1 Scaling: model loaded once at module startup (warm path — no per-request I/O)
# Loads xgb_fraud_latest.joblib (updated on each approved training run)
ML_MODEL = load_model()

_DEFAULT_RULE = [{"if": {"==": [{"var": "device_is_emulator"}, True]}, "action": "DECLINE"}]


def _load_active_rules() -> list:
    policy_path = Path("data/active_policy.json")
    if policy_path.exists():
        try:
            return json.loads(policy_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load active policy from %s: %s. Using default rule.", policy_path, e)
    return _DEFAULT_RULE


class RiskPayload(BaseModel):
    transaction_id: str
    tx_type: str
    amount: float = Field(..., gt=0, le=10_000_000, description="Transaction amount in USD")
    device_is_emulator: bool
    geo_velocity: float = Field(..., ge=0, le=5000, description="Risk proxy: distance/time ratio")
    typing_entropy: float = Field(default=3.0, ge=0.0, le=6.0, description="Risk proxy: behavioral anomaly (0-6)")
    card_count: Optional[float] = Field(default=1.0, ge=0, le=50, description="Number of cards on billing address")
    days_since_last_tx: Optional[float] = Field(default=30.0, ge=0, le=365, description="Days since last transaction on card")
    # Phase 2: Account enrichment features (batch-only — require aggregation history, default to neutral)
    uid_tx_count: Optional[float] = Field(default=5.0, ge=0, le=1000, description="Transactions on unique customer ID")
    uid_amt_mean: Optional[float] = Field(default=None, description="Average transaction amount per UID")
    uid_amt_std: Optional[float] = Field(default=0.0, ge=0, le=1000, description="Variance in spending per UID")
    email_domain_risk: Optional[int] = Field(default=0, ge=0, le=1, description="Binary: risky email domain")
    email_domain_freq: Optional[float] = Field(default=0.01, ge=0.0, le=1.0, description="Rarity of email domain")
    card1_addr1_freq: Optional[float] = Field(default=1.0, ge=0, le=1000, description="Frequency of card+address pairs")
    tx_hour: Optional[int] = Field(default=12, ge=0, le=23, description="Hour of day (0-23)")
    is_late_night: Optional[int] = Field(default=0, ge=0, le=1, description="Binary: transaction 22:00-05:00")
    D2_norm: Optional[float] = Field(default=0.0, ge=-365, le=365, description="Days since 2nd-to-last tx, normalized")


@router.post("/v1/risk-check")
async def risk_check(payload: RiskPayload):
    rules = _load_active_rules()
    data = payload.model_dump()

    # 1. Rule evaluation
    rule_res = evaluate_policy(rules, data)

    # 2. ML score
    ml_score = 0.0
    try:
        input_df = pd.DataFrame([data])[FEATURE_COLS]
        proba = ML_MODEL.predict_proba(input_df)
        ml_score = float(proba[0, 1]) if hasattr(proba, 'shape') else float(proba[0][1])
    except Exception as e:
        logger.error("ML scoring failed: %s — falling back to rule-only decision", e)
        raise HTTPException(status_code=500, detail=f"ML scoring error: {e}")

    # 3. Ensemble orchestration (same logic as dashboard and backtest pipeline)
    rule_df = pd.DataFrame([rule_res])
    ml_series = pd.Series([ml_score])
    orchestrated = batch_orchestrate(rule_df, ml_series)

    # 4. Async SHAP (fire-and-forget — never blocks response)
    start_shadow_shap(data)

    return {
        "decision": orchestrated['decision'].iloc[0],
        "action": orchestrated['action'].iloc[0],
        "strategy": orchestrated['strategy'].iloc[0],
        "metadata": {
            "ml_score": float(orchestrated['ml_score'].iloc[0]),
            "audit_id": rule_res['audit']['decision_id'],
            "nacha_code": rule_res['adverse_action_code'],
            "policy_version": rule_res['audit']['policy_version'],
        }
    }
