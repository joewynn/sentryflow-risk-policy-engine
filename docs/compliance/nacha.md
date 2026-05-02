# Nacha 2026 Compliance

SentryFlow is designed to satisfy Nacha 2026 "proactive monitoring" requirements. Every decision includes a cryptographic policy signature and an Adverse Action Code, giving regulators a complete reconstruction of the logic used at any point in time.

---

## Adverse Action Codes

Every decision response includes a `nacha_code` in `metadata`. The mapping is enforced in `src/policies/evaluator.py`:

| Action | Nacha Code | Customer-facing message |
|---|---|---|
| `DECLINE` | R03 | Security verification failed. |
| `REQUIRE_VIDEO_ID` | R01 | Additional identity verification required. |
| `REQUIRE_MFA` | R01 | Step-up authentication required. |
| `APPROVE` | — | — (no adverse action) |
| `DELAY_4H` | — | — (soft hold, not an adverse action) |

`R03` is used for hard declines where the transaction is refused outright. `R01` is used when additional verification is required rather than an outright refusal.

---

## Policy signature

Each response includes `metadata.policy_version` — a SHA256 fingerprint of the active rule JSON:

```python
hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()[:16]
```

Because the signature is computed from the exact rule content (not a version label), a regulator can:

1. Retrieve the decision audit record for a disputed transaction
2. Read the `policy_version` hash from the record
3. Compare it against any historical policy snapshot to identify the exact rule set active at that moment

This satisfies Nacha's requirement to demonstrate *what logic was applied* to each transaction — not just that monitoring existed.

---

## Compliance record layout

For each transaction, SentryFlow creates two records:

### 1. Decision record (synchronous)

Returned inline in the API response under `metadata`:

```json
{
  "ml_score": 0.04,
  "audit_id": "3f2a1b...",
  "nacha_code": "R01",
  "policy_version": "a3f72c91..."
}
```

`audit_id` is a UUID generated per request in `evaluate_policy()`. It uniquely identifies this decision for cross-referencing with SHAP and emergency override records.

### 2. SHAP audit record (asynchronous)

Written to `data/shap_audit/{transaction_id}.json` within a few seconds of the response:

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

This provides the **feature-level attribution** that satisfies the "explainability" component of Nacha's adverse action requirements.

---

## Training pipeline governance gate

`pipelines/backtest_flow.py` includes an `approval_gate` step that fails the Metaflow DAG if FPR > 2% on the held-out test set:

```python
if fpr > 0.02:
    raise ValueError(f"FPR {fpr:.3f} exceeds 2% threshold — model not promoted")
```

This prevents a model with excessive false-positive rates from being deployed, which would cause disproportionate adverse actions against legitimate users.

---

## Emergency override

When a Senior Risk Admin triggers an Emergency Push via the dashboard, the override is written to `data/audit_trail/emergency_{timestamp}.json` with:

- Full policy content (not just a hash)
- `policy_signature` (SHA256 of the rule JSON)
- Timestamp and approver identity

This record satisfies Nacha's requirement that emergency bypass actions are documented for post-mortem review.
