# API & Orchestration

The single endpoint `POST /v1/risk-check` runs three stages in sequence on the fast path, then fires SHAP asynchronously.

---

## Stage 1 — Rule evaluation

`evaluate_policy(rules, data)` in `src/policies/evaluator.py`

- Loads the active policy from `data/active_policy.json` on each request
- Evaluates each JsonLogic rule against the request payload
- Collects all triggered actions
- Selects the highest-severity action using `SEVERITY_MAP`:

```python
SEVERITY_MAP = {
    "DECLINE":          5,
    "REQUIRE_VIDEO_ID": 4,
    "REQUIRE_MFA":      3,
    "DELAY_4H":         2,
    "APPROVE":          1,
}
```

If no rules fire, the action defaults to `APPROVE`.

Missing payload fields are logged as warnings and the corresponding rule is skipped — the request never fails due to a missing feature field.

---

## Stage 2 — ML scoring

`ML_MODEL.predict_proba(input_df)` on the XGBoost model loaded at startup

- Model is loaded once at module import time (no per-request file I/O)
- Input: a DataFrame built from the request payload
- Output: fraud probability in [0.0, 1.0]
- If the model file is missing: `MockModel` returns 0.02 for all inputs with a `RuntimeWarning` logged at startup

---

## Stage 3 — Ensemble orchestration

`batch_orchestrate(rule_df, ml_scores)` in `src/policies/evaluator.py`

Conditions are evaluated **in priority order** (first match wins):

| Condition | Strategy tag | Final action |
|---|---|---|
| Rule = PASS **and** ML score > 0.92 | `ML_OVERRIDE_CRITICAL` | REQUIRE_VIDEO_ID |
| Rule = PASS **and** ML score > 0.75 | `ML_ENHANCED_FRICTION` | REQUIRE_MFA |
| Rule = BLOCK (any ML score) | `RULE_LED` | From rule |
| Rule = PASS and ML score ≤ 0.75 | `RULE_LED` | APPROVE |

Threshold constants (defined at the top of `evaluator.py`):

```python
ML_CRITICAL_THRESHOLD = 0.92   # calibrated on v2026.03 validation set
ML_FRICTION_THRESHOLD = 0.75
```

The `strategy` field in the response tells you which path was taken, enabling downstream audit and debugging.

---

## Async SHAP (slow path)

After the response is sent, `start_shadow_shap(payload)` fires a daemon thread that:

1. Loads the XGBoost model
2. Runs `shap.TreeExplainer(model.get_booster())`
3. Computes per-feature SHAP values for the transaction
4. Writes a JSON audit record to `data/shap_audit/{transaction_id}.json`

The SHAP values are **not** in the synchronous response. They arrive within a few seconds at `data/shap_audit/`. If the model is a `MockModel`, SHAP computation is skipped and a warning is logged.

Example SHAP audit file:

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

---

## Error handling

| Scenario | Behaviour |
|---|---|
| Missing required field | HTTP 422 (Pydantic validation) |
| `amount ≤ 0` or out-of-range field | HTTP 422 |
| ML model scoring failure | HTTP 500 with error detail |
| Rule evaluation exception | Warning logged, rule skipped, others still evaluated |
| Model file missing at startup | `RuntimeWarning`, MockModel used, API still serves |
