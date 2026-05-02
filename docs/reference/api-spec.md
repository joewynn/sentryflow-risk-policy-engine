# API Specification

## POST /v1/risk-check

Evaluate a transaction against the active policy and ML ensemble. Returns a real-time decision.

**Content-Type:** `application/json`

---

## Request schema

```json
{
  "transaction_id": "TX-001",
  "tx_type": "WIRE_TRANSFER",
  "amount": 5000.0,
  "device_is_emulator": true,
  "geo_velocity": 800.0,
  "typing_entropy": 1.1
}
```

### Fields

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `transaction_id` | string | Yes | non-empty | Caller-supplied unique identifier |
| `tx_type` | string | Yes | non-empty | Transaction type (e.g. `WIRE_TRANSFER`, `ACH`) |
| `amount` | float | Yes | > 0, ≤ 10,000,000 | Transaction amount in USD |
| `device_is_emulator` | bool | Yes | — | True if device fingerprint matches emulator patterns |
| `geo_velocity` | float | Yes | 0–5000 km/h | Implied speed from consecutive logins |
| `typing_entropy` | float | No | 0.0–6.0, default 3.0 | Shannon entropy of keystroke timing |

Constraint violations return **HTTP 422** with a Pydantic validation error detail before any rule evaluation.

---

## Response schema

```json
{
  "decision": "BLOCK",
  "action": "REQUIRE_VIDEO_ID",
  "strategy": "RULE_LED",
  "metadata": {
    "ml_score": 0.04,
    "audit_id": "3f2a1b9c-8c4d-4a2e-9e7f-1234567890ab",
    "nacha_code": "R01",
    "policy_version": "a3f72c91d4b82e..."
  }
}
```

### Fields

| Field | Type | Description |
|---|---|---|
| `decision` | string | `BLOCK` or `PASS` |
| `action` | string | `DECLINE`, `REQUIRE_VIDEO_ID`, `REQUIRE_MFA`, `DELAY_4H`, or `APPROVE` |
| `strategy` | string | Which ensemble path was taken (see below) |
| `metadata.ml_score` | float | XGBoost fraud probability in [0.0, 1.0] |
| `metadata.audit_id` | string | UUID for cross-referencing with SHAP audit |
| `metadata.nacha_code` | string or null | Nacha Adverse Action Code (R01 / R03 / null) |
| `metadata.policy_version` | string | SHA256 fingerprint of the active rule JSON |

---

## Strategy values

The `strategy` field identifies which ensemble path produced the decision:

| Strategy | Condition | Action |
|---|---|---|
| `ML_OVERRIDE_CRITICAL` | Rule = PASS **and** ML score > 0.92 | `REQUIRE_VIDEO_ID` |
| `ML_ENHANCED_FRICTION` | Rule = PASS **and** 0.75 < ML score ≤ 0.92 | `REQUIRE_MFA` |
| `RULE_LED` | Rule = BLOCK (any ML score) | From rule |
| `RULE_LED` | Rule = PASS **and** ML score ≤ 0.75 | `APPROVE` |

---

## Error responses

| Status | Scenario |
|---|---|
| 422 | Missing required field or constraint violation (Pydantic) |
| 500 | ML scoring failure (model error) |

Rule evaluation failures are logged as warnings and do not cause a 4xx/5xx response — remaining rules still evaluate normally.

---

## Interactive documentation

FastAPI generates Swagger and ReDoc UI automatically:

| URL | Interface |
|---|---|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |

---

## Example: emulator + velocity → BLOCK

```bash
curl -X POST http://localhost:8000/v1/risk-check \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "TX-001",
    "tx_type": "WIRE_TRANSFER",
    "amount": 5000.0,
    "device_is_emulator": true,
    "geo_velocity": 800.0,
    "typing_entropy": 1.1
  }'
```

Expected response:

```json
{
  "decision": "BLOCK",
  "action": "REQUIRE_VIDEO_ID",
  "strategy": "RULE_LED",
  "metadata": {
    "ml_score": 0.04,
    "audit_id": "3f2a1b9c-...",
    "nacha_code": "R01",
    "policy_version": "a3f72c91..."
  }
}
```

## Example: clean transaction → PASS

```bash
curl -X POST http://localhost:8000/v1/risk-check \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "TX-002",
    "tx_type": "ACH",
    "amount": 150.0,
    "device_is_emulator": false,
    "geo_velocity": 12.0,
    "typing_entropy": 3.8
  }'
```

Expected response:

```json
{
  "decision": "PASS",
  "action": "APPROVE",
  "strategy": "RULE_LED",
  "metadata": {
    "ml_score": 0.02,
    "audit_id": "...",
    "nacha_code": null,
    "policy_version": "..."
  }
}
```
