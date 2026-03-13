# src/policies/evaluator.py
from json_logic import jsonLogic as json_logic  # Alias to maintain snake_case usability
import uuid
from datetime import datetime

def evaluate_policy(rules: list, data: dict) -> dict:
    """
    Evaluates a list of JsonLogic rules against transaction data.
    Implements Highest-Severity conflict resolution.
    """
    triggered_actions = []
    
    # 1. Run each rule
    for rule in rules:
        try:
            # Ensure the rule is a non-empty dictionary before passing to library
            if isinstance(rule, dict) and len(rule) > 0:
                
                # Check if it's our wrapped structure {"if": logic, "action": name}
                if "if" in rule:
                    condition = rule["if"]
                    action = rule.get("action", "REVIEW")
                    if json_logic(condition, data):
                        triggered_actions.append(action)
                else:
                    # It's a raw JsonLogic rule (e.g., {"==": [...]})
                    if json_logic(rule, data):
                        triggered_actions.append("DECLINE")
        except Exception as e:
            # Graceful degradation: log error but don't crash the whole risk check
            print(f"Rule Evaluation Error: {str(e)}")
            continue
            
    # 2. Highest-Severity Conflict Resolution
    # Hierarchy: DECLINE > REQUIRE_VIDEO > REQUIRE_MFA > DELAY_4H > APPROVE
    severity_map = {
        "DECLINE": 5,
        "REQUIRE_VIDEO": 4,
        "REQUIRE_MFA": 3,
        "DELAY_4H": 2,
        "APPROVE": 1
    }
    
    final_action = "APPROVE"
    if triggered_actions:
        final_action = max(triggered_actions, key=lambda x: severity_map.get(x, 0))

    # 3. Generate Nacha-compliant Adverse Action Notice (AAN)
    aan_map = {
        "DECLINE": ("R03", "Security verification failed."),
        "REQUIRE_VIDEO": ("R01", "Additional identity verification required."),
        "REQUIRE_MFA": ("R01", "Step-up authentication required.")
    }
    
    code, msg = aan_map.get(final_action, (None, None))

    return {
        "decision": "BLOCK" if severity_map.get(final_action, 0) > 3 else "PASS",
        "action": final_action,
        "adverse_action_code": code,
        "customer_facing_message": msg,
        "audit": {
            "decision_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "triggered_rules_count": len(triggered_actions)
        }
    }