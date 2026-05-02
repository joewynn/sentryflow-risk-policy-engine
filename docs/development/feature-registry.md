# Feature Availability

Not all features can be used in real-time policy rules. Some require aggregation over historical windows and must be computed by a feature store.

---

## Real-time features

These fields are available in every live API request and can be referenced in `data/active_policy.json` rules.

| Feature | Type | Validation |
|---|---|---|
| `transaction_id` | string | Required, non-empty |
| `tx_type` | string | Required |
| `amount` | float | Required, > 0.0 |
| `geo_velocity` | float | Required, 0–5000 km/h |
| `typing_entropy` | float | Required, 0.0–6.0 |
| `device_is_emulator` | bool | Optional, defaults to false |

Pydantic enforces range constraints at the API boundary (`src/api/router.py`). Requests violating these constraints return HTTP 422 before evaluation begins.

---

## Batch-only features

These signals require historical aggregation and are not available in the synchronous request payload. Rules referencing them will log a warning and be **silently skipped** at runtime.

| Feature | Description | Requires |
|---|---|---|
| `velocity_7d` | Number of transactions in the last 7 days | Feature store / time-series aggregation |
| `consortium_match_count` | Cross-client device/behavior matches | External device graph integration |
| `account_age_days` | Days since account creation | Identity database query |
| `chargeback_rate_30d` | Rolling chargeback rate for this user | Aggregated label history |

---

## What happens when a rule references a missing field

If a rule's condition references a field not present in the payload:

1. `evaluate_policy()` catches the `KeyError`
2. Logs: `WARNING: Missing field in payload during rule evaluation: <field> | rule=<rule>`
3. Skips that rule
4. Continues evaluating remaining rules
5. The request never fails due to a missing feature

This design allows risk managers to author rules for future signals — the rule will activate automatically once the caller starts sending that field.

---

## Adding a new real-time feature

1. Add the field to `RiskPayload` in `src/api/router.py` with appropriate Pydantic constraints
2. Verify the field is passed through to `evaluate_policy()` in the data dict
3. If using it for ML scoring, add it to `FEATURE_COLS` in `src/models/train.py` and retrain
4. Reference the field in `data/active_policy.json` rules
