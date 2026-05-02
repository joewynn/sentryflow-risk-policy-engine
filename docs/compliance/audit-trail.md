# Decision Audit Trail

SentryFlow generates two audit records per transaction — one synchronous, one asynchronous — plus a separate record for emergency overrides.

---

## 1. Decision audit (synchronous)

Returned in every API response under `metadata`:

```json
{
  "decision": "BLOCK",
  "action": "REQUIRE_VIDEO_ID",
  "strategy": "RULE_LED",
  "metadata": {
    "ml_score": 0.04,
    "audit_id": "3f2a1b9c-...",
    "nacha_code": "R01",
    "policy_version": "a3f72c91d4b82e..."
  }
}
```

| Field | Source | Description |
|---|---|---|
| `audit_id` | `evaluate_policy()` | UUID per request — links to SHAP audit |
| `nacha_code` | `evaluate_policy()` | Adverse Action Code (R01 / R03 / null) |
| `policy_version` | `evaluate_policy()` | SHA256(rule JSON) — identifies the exact policy version |
| `ml_score` | XGBoost `predict_proba` | Fraud probability in [0.0, 1.0] |
| `strategy` | `batch_orchestrate()` | Which ensemble path was taken |

The `policy_version` hash is computed from the content of `data/active_policy.json` at request time, not from a version label. This means the hash changes automatically whenever the policy file changes.

---

## 2. SHAP audit (asynchronous)

Written to `data/shap_audit/{transaction_id}.json` after the response is sent. Computed in a background daemon thread by `src/api/async_explain.py`.

```json
{
  "transaction_id": "TX-001",
  "top_shap_features": [
    ["geo_velocity", 0.42],
    ["typing_entropy", -0.31],
    ["device_is_emulator", 0.18],
    ["amount", 0.04]
  ],
  "all_shap_values": {
    "amount": 0.04,
    "geo_velocity": 0.42,
    "typing_entropy": -0.31,
    "device_is_emulator": 0.18
  },
  "base_value": -2.1,
  "computed_at": "2026-05-01T14:32:00Z",
  "model_id": "xgb_fraud"
}
```

`top_shap_features` is sorted by absolute SHAP value, descending. `base_value` is the model's log-odds intercept (the score for an "average" transaction before feature contributions).

SHAP values are **not** in the synchronous response. They typically appear within 1–5 seconds. If the model is a `MockModel` (no trained model loaded), SHAP is skipped and a warning is logged.

---

## 3. Emergency override audit

Written to `data/audit_trail/emergency_{timestamp}.json` when the Emergency Push is triggered from the dashboard:

```json
{
  "event": "emergency_policy_push",
  "pushed_at": "2026-05-01T22:15:00Z",
  "policy": [...],
  "policy_signature": "a3f72c91..."
}
```

This record satisfies the requirement that emergency bypasses of the 4-eyes approval queue are documented for post-mortem compliance review.

---

## Cross-referencing records

To reconstruct the full audit for a disputed transaction:

1. Look up the `audit_id` from the API response
2. Read `metadata.policy_version` to identify the rule set
3. Read `data/shap_audit/{transaction_id}.json` for feature attribution
4. Check `data/policy_queue/` for the approval record for that policy version

The `audit_id` (UUID) and `transaction_id` are different identifiers. `audit_id` is generated per request; `transaction_id` is supplied by the caller.
