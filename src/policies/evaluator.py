# src/policies/evaluator.py
from src.utils.json_logic_compat import jsonLogic as json_logic
import uuid
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import hashlib
import json

logger = logging.getLogger(__name__)

# Centralized severity for system-wide consistency
SEVERITY_MAP = {
    "DECLINE": 5,
    "REQUIRE_VIDEO_ID": 4,
    "REQUIRE_MFA": 3,
    "DELAY_4H": 2,
    "APPROVE": 1
}

# Ensemble thresholds calibrated on v2026.03 validation set (precision-recall curve, 2026-03-15).
# ML_CRITICAL: model confidence > 92% overrides a rule-based PASS → REQUIRE_VIDEO_ID
# ML_FRICTION: 75–92% confidence adds MFA friction, reducing FPR vs a hard BLOCK
ML_CRITICAL_THRESHOLD = 0.92
ML_FRICTION_THRESHOLD = 0.75


def evaluate_policy(rules: list, data: dict) -> dict:
    """Evaluates rules for a single transaction (API fast path)."""
    triggered_actions = []
    for rule in rules:
        try:
            if isinstance(rule, dict) and rule:
                logic = rule.get("if", rule) if "if" in rule else rule
                action = rule.get("action", "DECLINE") if "if" in rule else "DECLINE"
                if isinstance(logic, dict) and json_logic(logic, data):
                    triggered_actions.append(action)
        except KeyError as e:
            logger.warning("Missing field in payload during rule evaluation: %s | rule=%s", e, rule)
            continue
        except Exception as e:
            logger.error("Rule evaluation failed: %s | rule=%s", e, rule)
            continue

    final_action = max(triggered_actions, key=lambda x: SEVERITY_MAP.get(x, 0)) if triggered_actions else "APPROVE"

    aan_map = {
        "DECLINE": ("R03", "Security verification failed."),
        "REQUIRE_VIDEO_ID": ("R01", "Additional identity verification required."),
        "REQUIRE_MFA": ("R01", "Step-up authentication required.")
    }
    code, msg = aan_map.get(final_action, (None, None))

    return {
        "decision": "BLOCK" if SEVERITY_MAP.get(final_action, 0) > 3 else "PASS",
        "action": final_action,
        "adverse_action_code": code,
        "customer_facing_message": msg,
        "audit": {
            "decision_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "policy_version": "v2026.03.13"
        }
    }


def batch_orchestrate(rule_results: pd.DataFrame, ml_scores: pd.Series) -> pd.DataFrame:
    """Vectorized ensemble engine — conditions evaluated in priority order (critical first)."""
    conditions = [
        (rule_results['decision'] == 'PASS') & (ml_scores > ML_CRITICAL_THRESHOLD),
        (rule_results['decision'] == 'PASS') & (ml_scores > ML_FRICTION_THRESHOLD),
    ]
    choices = ['ML_OVERRIDE_CRITICAL', 'ML_ENHANCED_FRICTION']
    strategies = np.select(conditions, choices, default='RULE_LED')

    final_decisions = np.where(
        (strategies == 'ML_OVERRIDE_CRITICAL') | (rule_results['decision'] == 'BLOCK'),
        'BLOCK', 'PASS'
    )
    final_actions = np.select(
        [strategies == 'ML_OVERRIDE_CRITICAL', strategies == 'ML_ENHANCED_FRICTION'],
        ['REQUIRE_VIDEO_ID', 'REQUIRE_MFA'],
        default=rule_results['action']
    )

    return pd.DataFrame({
        'strategy': strategies,
        'decision': final_decisions,
        'action': final_actions,
        'ml_score': ml_scores.round(4),
        'aan_code': np.where(final_decisions == 'BLOCK', 'R03', 'PASS')
    })


def create_policy_signature(rules: dict, version: str) -> str:
    """Cryptographic lineage for Nacha 2026 non-repudiation."""
    policy_string = json.dumps(rules, sort_keys=True) + version
    return hashlib.sha256(policy_string.encode()).hexdigest()
