import numpy as np
import pandas as pd
import hashlib
import json
import uuid
from datetime import datetime, timezone
from json_logic import jsonLogic as json_logic

def evaluate_policy(rules: list, data: dict) -> dict:
    """Evaluates single transaction logic (used for API / Live Audit)."""
    triggered_actions = []
    for rule in rules:
        try:
            if isinstance(rule, dict) and rule:
                logic = rule.get("if", rule) if "if" in rule else rule
                action = rule.get("action", "DECLINE") if "if" in rule else "DECLINE"
                if isinstance(logic, dict) and json_logic(logic, data):
                    triggered_actions.append(action)
        except: continue
            
    severity_map = {"DECLINE": 5, "REQUIRE_VIDEO_ID": 4, "REQUIRE_MFA": 3, "APPROVE": 1}
    final_action = max(triggered_actions, key=lambda x: severity_map.get(x, 0)) if triggered_actions else "APPROVE"
    
    return {
        "decision": "BLOCK" if severity_map.get(final_action, 0) > 3 else "PASS",
        "action": final_action,
        "adverse_action_code": "R03" if final_action == "DECLINE" else "R01" if "REQUIRE" in final_action else None,
        "audit": {"decision_id": str(uuid.uuid4())}
    }

def batch_orchestrate(rule_results_df: pd.DataFrame, ml_scores: pd.Series) -> pd.DataFrame:
    """
    VECTORIZED ENSEMBLE ENGINE: 
    Used by the Dashboard to simulate 10k+ transactions without latency spikes.
    """
    # Define Gray Zone Conditions
    cond_critical = (rule_results_df['decision'] == 'PASS') & (ml_scores > 0.92)
    cond_friction = (rule_results_df['decision'] == 'PASS') & (ml_scores > 0.75)
    
    # Vectorized Strategy Selection
    strategies = np.select(
        [cond_critical, cond_friction],
        ['ML_OVERRIDE_CRITICAL', 'ML_ENHANCED_FRICTION'],
        default='RULE_LED'
    )
    
    # Vectorized Decision Resolution
    final_decisions = np.where(
        (strategies == 'ML_OVERRIDE_CRITICAL') | (rule_results_df['decision'] == 'BLOCK'),
        'BLOCK', 'PASS'
    )
    
    # Vectorized Action Mapping
    final_actions = np.select(
        [strategies == 'ML_OVERRIDE_CRITICAL', strategies == 'ML_ENHANCED_FRICTION'],
        ['REQUIRE_VIDEO_ID', 'REQUIRE_MFA'],
        default=rule_results_df['action']
    )

    return pd.DataFrame({
        'strategy': strategies,
        'decision': final_decisions,
        'action': final_actions,
        'ml_score': ml_scores.round(4),
        'aan_code': np.where(final_decisions == 'BLOCK', 'R03', 'PASS') # Simplified for demo
    })

def create_policy_signature(rules: dict, version: str) -> str:
    """Implements cryptographic lineage for Nacha 2026."""
    blob = json.dumps(rules, sort_keys=True) + version
    return hashlib.sha256(blob.encode()).hexdigest()