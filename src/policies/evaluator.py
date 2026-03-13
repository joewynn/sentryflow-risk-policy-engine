from jsonlogic import jsonLogic
import uuid
from datetime import datetime
import json
from typing import List, Dict

# Severity map: higher = more restrictive
SEVERITY = {
    "NONE": 0,
    "REQUIRE_MFA": 1,
    "DELAY_4H": 2,
    "REQUIRE_VIDEO": 3,
    "BLOCK": 4
}

def evaluate_policy(rules: List[Dict], data: Dict) -> Dict:
    """Highest Severity wins + full audit trace (Nacha-compliant)"""
    triggered = []
    highest_action = "NONE"
    highest_score = 0

    for rule in rules:
        result = jsonLogic(rule, data)
        if result:
            action = rule.get("action", "NONE")
            score = SEVERITY.get(action, 0)
            triggered.append({"rule": rule, "action": action})
            if score > highest_score:
                highest_score = score
                highest_action = action

    audit_log = {
        "decision_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "policy_version": "v2026.03",
        "model_version": "v4.1",
        "rules_evaluated": len(rules),
        "triggered_rules": triggered,
        "final_action": highest_action,
        "severity_score": highest_score,
        "input_hash": hash(json.dumps(data, sort_keys=True))
    }

    print(f"[AUDIT] {audit_log}")  # In prod → S3/Snowflake
    return {
        "decision": "BLOCK" if highest_action == "BLOCK" else "ALLOW",
        "action": highest_action,
        "adverse_action_code": "R03" if highest_action != "NONE" else None,
        "customer_facing_message": "We couldn't verify your device security. Please try a different browser." if highest_action != "NONE" else None,
        "audit": audit_log
    }