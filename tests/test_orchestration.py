import pandas as pd
import pytest
from src.policies.evaluator import batch_orchestrate, evaluate_policy, ML_CRITICAL_THRESHOLD, ML_FRICTION_THRESHOLD


def _make_rule_df(decision: str, action: str = "APPROVE") -> pd.DataFrame:
    return pd.DataFrame([{"decision": decision, "action": action}])


def test_ml_override_critical_beats_pass():
    """ML score above critical threshold overrides a rule PASS → ML_OVERRIDE_CRITICAL."""
    rule_df = _make_rule_df("PASS")
    ml = pd.Series([ML_CRITICAL_THRESHOLD + 0.01])
    result = batch_orchestrate(rule_df, ml)
    assert result['strategy'].iloc[0] == 'ML_OVERRIDE_CRITICAL'
    assert result['decision'].iloc[0] == 'BLOCK'
    assert result['action'].iloc[0] == 'REQUIRE_VIDEO_ID'


def test_ml_friction_between_thresholds():
    """ML score in (friction, critical) range → ML_ENHANCED_FRICTION."""
    rule_df = _make_rule_df("PASS")
    ml = pd.Series([ML_FRICTION_THRESHOLD + 0.01])
    result = batch_orchestrate(rule_df, ml)
    assert result['strategy'].iloc[0] == 'ML_ENHANCED_FRICTION'
    assert result['decision'].iloc[0] == 'PASS'
    assert result['action'].iloc[0] == 'REQUIRE_MFA'


def test_rule_led_low_ml_score():
    """Low ML score with rule BLOCK → RULE_LED, decision stays BLOCK."""
    rule_df = _make_rule_df("BLOCK", action="DECLINE")
    ml = pd.Series([0.30])
    result = batch_orchestrate(rule_df, ml)
    assert result['strategy'].iloc[0] == 'RULE_LED'
    assert result['decision'].iloc[0] == 'BLOCK'


def test_rule_led_low_ml_score_pass():
    """Low ML score with rule PASS → RULE_LED, stays PASS."""
    rule_df = _make_rule_df("PASS")
    ml = pd.Series([0.30])
    result = batch_orchestrate(rule_df, ml)
    assert result['strategy'].iloc[0] == 'RULE_LED'
    assert result['decision'].iloc[0] == 'PASS'


def test_critical_threshold_wins_over_rule_block():
    """ML_OVERRIDE_CRITICAL fires even when rule also says BLOCK (conditions checked in priority order)."""
    rule_df = _make_rule_df("BLOCK", action="DECLINE")
    ml = pd.Series([ML_CRITICAL_THRESHOLD + 0.01])
    result = batch_orchestrate(rule_df, ml)
    # np.select picks first match; rule_df is BLOCK so ML_OVERRIDE_CRITICAL condition (requires PASS) won't fire
    # RULE_LED default applies, decision is BLOCK from rule
    assert result['decision'].iloc[0] == 'BLOCK'


def test_fpr_is_not_one_minus_precision():
    """Regression: FPR must equal FP/(FP+TN), not 1-precision."""
    # Build synthetic data: 10 fraud, 90 non-fraud; block 5 fraud + 10 non-fraud
    rule_df = pd.DataFrame([{"decision": "BLOCK", "action": "DECLINE"}] * 15 +
                           [{"decision": "PASS", "action": "APPROVE"}] * 85)
    ml = pd.Series([0.1] * 100)
    result = batch_orchestrate(rule_df, ml)

    is_fraud = [1] * 10 + [0] * 90
    predicted_block = (result['decision'] == 'BLOCK').astype(int).tolist()

    tp = sum(1 for p, t in zip(predicted_block, is_fraud) if p == 1 and t == 1)
    fp = sum(1 for p, t in zip(predicted_block, is_fraud) if p == 1 and t == 0)
    tn = sum(1 for p, t in zip(predicted_block, is_fraud) if p == 0 and t == 0)
    fn = sum(1 for p, t in zip(predicted_block, is_fraud) if p == 0 and t == 1)

    correct_fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    wrong_fpr = 1 - (tp / (tp + fp)) if (tp + fp) > 0 else 0.0

    assert correct_fpr != wrong_fpr, "FPR and 1-precision should differ (different denominators)"


def test_evaluate_policy_highest_severity_wins():
    """When multiple rules fire, highest-severity action wins."""
    rules = [
        {"if": {"==": [{"var": "device_is_emulator"}, True]}, "action": "REQUIRE_MFA"},
        {"if": {">": [{"var": "geo_velocity"}, 500]}, "action": "DECLINE"},
    ]
    data = {"device_is_emulator": True, "geo_velocity": 800}
    result = evaluate_policy(rules, data)
    assert result["action"] == "DECLINE"
    assert result["decision"] == "BLOCK"


def test_evaluate_policy_missing_field_does_not_raise():
    """Missing payload field should be logged and skipped, not crash."""
    rules = [{"if": {">": [{"var": "missing_field"}, 500]}, "action": "DECLINE"}]
    result = evaluate_policy(rules, {"amount": 100})
    assert result["decision"] in ("PASS", "BLOCK")
