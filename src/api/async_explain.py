# src/api/async_explain.py
import json
import logging
import threading
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import shap

from src.models.train import FEATURE_COLS

logger = logging.getLogger(__name__)

SHAP_AUDIT_DIR = Path("data/shap_audit")


def _compute_shap_background(
    payload: dict,
    transaction_id: str,
    model: Any,
) -> None:
    """
    Runs in a background daemon thread — never blocks the <30ms fast path.
    Computes real SHAP values via TreeExplainer and persists them to data/shap_audit/.

    The model is passed in from the router's module-level ML_MODEL — no ZenML or
    filesystem access happens here, keeping the background thread lightweight.
    """
    try:
        if not hasattr(model, "get_booster"):
            logger.warning(
                "SHAP skipped for transaction %s: model has no booster (cache miss in use). "
                "Run 'make train' to enable real explainability.",
                transaction_id,
            )
            return

        row = {col: payload.get(col, 0) for col in FEATURE_COLS}
        df = pd.DataFrame([row])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            explainer = shap.TreeExplainer(model.get_booster())
            shap_values = explainer(df)

        feature_shap = {
            col: float(shap_values.values[0][i])
            for i, col in enumerate(FEATURE_COLS)
        }
        top_features = sorted(feature_shap.items(), key=lambda x: abs(x[1]), reverse=True)[:5]

        audit_record = {
            "transaction_id": transaction_id,
            "top_shap_features": top_features,
            "all_shap_values": feature_shap,
            "base_value": float(shap_values.base_values[0]),
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "model_id": "xgb_fraud",
        }

        SHAP_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        (SHAP_AUDIT_DIR / f"{transaction_id}.json").write_text(
            json.dumps(audit_record, indent=2)
        )
        logger.info("SHAP audit written for transaction %s", transaction_id)

    except Exception as e:
        logger.error("Background SHAP failed for transaction %s: %s", transaction_id, e)


def start_shadow_shap(payload: dict, model: Any) -> None:
    """
    Fire-and-forget SHAP — called after the fast-path decision is returned.
    The caller passes the already-loaded model so this thread never touches ZenML or disk.
    """
    transaction_id = str(payload.get("transaction_id", "unknown"))
    thread = threading.Thread(
        target=_compute_shap_background,
        args=(payload, transaction_id, model),
        daemon=True,
    )
    thread.start()
