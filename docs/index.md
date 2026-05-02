# SentryFlow Risk Engine

**Real-time fraud decisioning with ML orchestration and Nacha 2026 compliance.**

SentryFlow stops AI-driven social engineering, synthetic identity fraud, and account takeover by combining fast JsonLogic rule evaluation with an XGBoost + Isolation Forest ensemble — all under a 30ms p99 latency budget.

---

## What SentryFlow does

Every transaction flows through a three-stage fast path:

1. **Rule evaluation** — JsonLogic policies authored by Risk Managers in the dashboard, evaluated against real-time DIBB signals (device intelligence, behavioral biometrics)
2. **ML scoring** — XGBoost fraud probability, trained on labeled transaction data
3. **Ensemble orchestration** — combines rule result + ML score into a final `decision`, `action`, and `strategy` tag

The response carries a Nacha 2026 Adverse Action Code and a cryptographic policy signature, satisfying regulatory audit requirements without any post-processing.

---

## Key capabilities

| Capability | Details |
|---|---|
| **No-code policy authoring** | Risk Managers write JsonLogic rules in the Streamlit dashboard — no engineering deploy |
| **Adaptive friction** | Three friction levels: REQUIRE_MFA (medium risk), REQUIRE_VIDEO_ID (high risk), DECLINE (block) |
| **4-eyes governance** | Policy changes require peer review before promotion to `data/active_policy.json` |
| **Async SHAP explainability** | Feature attribution computed in background, written to `data/shap_audit/` — never blocks response |
| **Nacha 2026 compliance** | Every decision includes a SHA256 policy signature and Adverse Action Code for CFPB/FinCEN audits |

---

## Quick start

```bash
make setup      # Download IEEE fraud dataset
make train      # Train XGBoost + Isolation Forest (saves to data/models/)
make up         # Start API (8000) + Redis (6379) + Dashboard (8501)
```

Try a risk check:

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
    "audit_id": "3f2a1b...",
    "nacha_code": "R01",
    "policy_version": "v2026.03.13"
  }
}
```

---

## Technology stack

- **FastAPI** — inference gateway (<30ms fast path)
- **XGBoost + Isolation Forest** — supervised + unsupervised fraud ensemble
- **JsonLogic** — no-code rule authoring for Risk Managers
- **Metaflow** — ML training and backtesting pipeline
- **Streamlit** — Risk Control Plane dashboard with shadow backtesting
- **Redis** — hot cache for DIBB signals
- **SHAP** — asynchronous model explainability

---

## Navigation

- [Getting Started](getting-started.md) — full setup walkthrough
- [Architecture Overview](architecture/overview.md) — two-speed design and data flow
- [API Reference](reference/api-spec.md) — endpoint schema and validation rules
- [Compliance](compliance/nacha.md) — Nacha 2026, audit trail, governance
