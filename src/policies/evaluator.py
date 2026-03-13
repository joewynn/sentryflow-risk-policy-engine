# src/policies/evaluator.py
from json_logic import jsonLogic as json_logic
import uuid
from datetime import datetime

# Centralized severity for system-wide consistency
SEVERITY_MAP = {
    "DECLINE": 5,
    "REQUIRE_VIDEO_ID": 4,
    "REQUIRE_VIDEO": 4, # Backward compatibility
    "REQUIRE_MFA": 3,
    "DELAY_4H": 2,
    "APPROVE": 1
}

def evaluate_policy(rules: list, data: dict) -> dict:
    """
    Evaluates JsonLogic rules and returns a structured decision with 
    regulatory audit metadata.
    """
    triggered_actions = []
    
    for rule in rules:
        try:
            if isinstance(rule, dict) and len(rule) > 0:
                # Support both wrapped and raw JsonLogic
                if "if" in rule:
                    condition = rule["if"]
                    action = rule.get("action", "REQUIRE_MFA")
                    if json_logic(condition, data):
                        triggered_actions.append(action)
                else:
                    if json_logic(rule, data):
                        triggered_actions.append("DECLINE")
        except Exception as e:
            print(f"Rule Evaluation Error: {str(e)}")
            continue
            
    # 1. Resolve conflicts using highest severity
    final_action = "APPROVE"
    if triggered_actions:
        final_action = max(triggered_actions, key=lambda x: SEVERITY_MAP.get(x, 0))

    # 2. Map to Nacha-compliant Adverse Action Codes
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
            "timestamp": datetime.utcnow().isoformat(),
            "triggered_rules_count": len(triggered_actions),
            "policy_version": "v2026.03.13" # Lineage tracking
        }
    }

def orchestrate_decision(rule_result: dict, ml_score: float) -> dict:
    """
    The 'Senior TPM' Conflict Resolver.
    Combines static rules with ML anomaly scores to find the 'Gray Zone'.
    """
    final_action = rule_result["action"]
    final_decision = rule_result["decision"]
    strategy = "RULE_LED"

    # ML Gray-Zone Escalation: 
    # If rules say 'PASS' but ML is high-risk, we force friction (MFA/Video)
    # This is the 'Sardine Moat' in action.
    if final_decision == "PASS":
        if ml_score > 0.92:
            final_decision = "BLOCK"
            final_action = "REQUIRE_VIDEO_ID"
            strategy = "ML_OVERRIDE_CRITICAL"
        elif ml_score > 0.75:
            final_decision = "PASS" # Still pass, but with friction
            final_action = "REQUIRE_MFA"
            strategy = "ML_ENHANCED_FRICTION"
        
    return {
        "decision": final_decision,
        "action": final_action,
        "ml_score": round(ml_score, 4),
        "strategy": strategy,
        "audit_id": rule_result["audit"]["decision_id"],
        "aan_code": rule_result["adverse_action_code"]
    }