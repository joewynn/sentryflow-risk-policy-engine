# SentryFlow: Real-Time Fraud & Synthetic Identity Detection

![Python 3.12](https://img.shields.io/badge/python-3.12-blue) 
![License MIT](https://img.shields.io/badge/license-MIT-green)
![Nacha 2026](https://img.shields.io/badge/Compliance-Nacha_2026-orange)

A production-grade real-time risk orchestration engine combining **supervised ML** (XGBoost on 590K real fraud transactions) + **unsupervised anomaly detection** (Isolation Forest for synthetic identity patterns) with **policy autonomy** for Risk Managers to deploy rules in minutes, not weeks.

---

## 🎯 Why This Exists

**The Problem:** Legacy fraud vendors are slow (2–3 weeks to deploy rules), expensive ($0.45/transaction), and miss modern attack patterns (synthetic identity fraud, AI-generated behavior). SentryFlow decouples risk logic from engineering deployments, enabling rapid iteration on real data.

**The Result:** Trained on **IEEE-CIS Fraud Detection dataset (590K real e-commerce transactions)** with rigorous temporal evaluation:

| Metric | Real Data (IEEE-CIS) |
|--------|----------------------|
| **Fraud Detection Recall** | 68% @ <2% FPR |
| **AUROC** | 0.92 |
| **AUPRC** | 0.68 |
| **Decision Latency (p99)** | <30ms |
| **Policy Deploy Time** | <5 minutes |

---

## 🏗️ Architecture: Two-Speed Design

```
┌─────────────────────────────────────────────────────────┐
│ POST /v1/risk-check (Transaction Payload)              │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
    [FAST PATH <30ms]      [SLOW PATH - Async]
    ├─ Rule Eval (JsonLogic)     └─ SHAP Explainability
    ├─ XGBoost Score                (background thread)
    └─ Ensemble Orchestration
           ↓
    [DECISION: APPROVE|FRICTION|BLOCK]
    + Nacha Adverse Action Code
    + Audit Trail (immutable)
```

**Why this matters:** Real-time fraud decisioning without sacrificing explainability. SHAP computations never block the response.

---

## ⚙️ Technical Highlights

### ML Stack
- **XGBoost (Focal Loss):** Supervised fraud patterns. Trained on 80% of real data; validated on 20% hold-out set.
- **Isolation Forest:** Unsupervised zero-day detection. Catches synthetic identity clusters that supervised models miss.
- **Feature Engineering:** 6 DIBB signals engineered from 394 raw IEEE-CIS features (amount, device fingerprint, geographic velocity, address diversity, card frequency, transaction recency). Mutual information analysis ensures signal > noise.

### Policy Engine
- **JsonLogic DSL:** Risk managers author rules without code. Example:
  ```json
  {
    "if": {"and": [
      {">": [{"var": "geo_velocity"}, 500]},
      {"==": [{"var": "device_is_emulator"}, true]}
    ]},
    "action": "REQUIRE_VIDEO_ID"
  }
  ```
- **Ensemble Orchestration:** Rules + ML scores fused via severity-based conflict resolution:
  - `ML_OVERRIDE_CRITICAL`: XGBoost confidence >92% overrides rules
  - `ML_ENHANCED_FRICTION`: Confidence 75–92% adds friction
  - `RULE_LED`: Default path

### Governance & Compliance
- **4-Eyes Approval:** Policy changes require human review before live deployment
- **Nacha 2026 Audit Trail:** Every decline includes Adverse Action Code + policy version hash (SHA256)
- **Shadow Backtest:** Before deploying, test rules against historical data to measure precision/recall impact

---

## 🚀 Quick Start

### 1. One-Command Setup
```bash
make up  # Starts API (8000) + Redis (6379) + Dashboard (8501)
```

### 2. Access the Risk Dashboard
Open `http://localhost:8501` → **Policy Playground** → Modify a rule → **Run Shadow Backtest** to see live precision/recall metrics.

### 3. Trigger a Real-Time Check
```bash
curl -X POST http://localhost:8000/v1/risk-check \
  -H 'Content-Type: application/json' \
  -d '{
    "transaction_id": "tx_12345",
    "tx_type": "WIRE_TRANSFER",
    "amount": 5000.0,
    "device_is_emulator": false,
    "geo_velocity": 200.0,
    "typing_entropy": 2.5,
    "card_count": 1.0,
    "days_since_last_tx": 45.0
  }'
```

**Response:**
```json
{
  "decision": "APPROVE",
  "score": 0.14,
  "action": "PASS",
  "adverse_action_code": null,
  "decision_id": "dec_abc123xyz",
  "policy_version": "v2026.05.ieee"
}
```

---

## 📚 Project Structure

```
src/
├── api/              # FastAPI router + async SHAP explainer
├── policies/         # JsonLogic evaluator + audit logger
├── models/           # XGBoost + Isolation Forest trainer
└── governance/       # 4-eyes approval queue

pipelines/
└── backtest_flow.py  # Metaflow DAG: load → train → backtest → approve

research/
├── eda_ieee_fraud.ipynb     # EDA on 590K real transactions
└── monitoring_dashboard.py  # Streamlit risk center

docs/
├── architecture/     # API flow, policy format, DIBB signals
├── compliance/       # Nacha 2026, audit trail, governance
└── reference/        # API spec, model card, threat models
```

---

## 🔬 ML Research & Reproducibility

This project is **fully reproducible** with real data:

1. **Data:** IEEE-CIS Fraud Detection (590K transactions, 3.5% fraud rate)
2. **Feature Research:** `research/eda_ieee_fraud.ipynb` computes mutual information scores for all candidate features
3. **Training:** `make train` runs Metaflow DAG with temporal 80/20 split (no data leakage)
4. **Evaluation:** All metrics computed on held-out test set; confusion matrices included
5. **Documentation:** `docs/development/feature_mapping.md` maps raw IEEE-CIS columns → DIBB signals

---

## 🎓 What You'll Learn (For Technical Candidates)

**If you're a Data Scientist:**
- How to engineer features from sparse, high-dimensional real-world data (MI-based feature selection)
- Ensemble design: combining supervised (XGBoost) + unsupervised (Isolation Forest) for complementary signal
- Temporal train/test splits and avoiding data leakage at scale
- Production ML: model versioning, shadow testing, governance gates

**If you're an ML Engineer:**
- Two-speed architecture: hot-path <30ms decisioning + cold-path explainability
- Real-time orchestration: fusing multiple signals (rules + ML + velocity) with conflict resolution
- Graceful degradation: system continues on rule-based path if ML model unavailable
- Async patterns: background SHAP without blocking user-facing latency

**If you're a Software Engineer:**
- FastAPI + Redis for sub-30ms p99 latency
- Metaflow for reproducible ML pipelines (local + cloud)
- Docker for deterministic deployment
- Pytest + integration testing on real data

---

## 📊 Compliance & Governance

✅ **Nacha 2026 Ready**
- Adverse Action Notices (AAN) with regulatory codes
- Immutable audit logs with policy version hashing
- 4-eyes approval workflow for policy changes

✅ **Risk Center Dashboard** (Streamlit)
- Real-time monitoring of decision patterns
- Interactive policy testing (shadow backtest)
- KPI tracking (fraud catch rate, false positive rate, latency)

---

## 📖 Documentation

Full technical docs available at `http://localhost:8501` when running locally. Topics include:

- **API Spec:** Request/response schemas, validation, error codes
- **Model Card:** XGBoost + Isolation Forest architecture, limitations, fallback behavior
- **DIBB Signals:** Device Intelligence + Behavioral Biometrics dictionary with fraud patterns
- **JsonLogic Policy Format:** Rules, operators, deployment workflow
- **Threat Models:** 4 modern fraud categories with SentryFlow defenses

---

## 🛠️ Development

```bash
make lint      # Ruff check src/ tests/
make test      # Pytest (31 tests, 95%+ coverage)
make train     # Metaflow backtest on real data
make docs-serve # MkDocs on localhost:8000
```

For single test: `pytest tests/path/to/test.py::test_name`

---

## 💡 Key Innovation: Policy Autonomy

**Problem:** Fraud patterns shift daily. Risk managers can't wait 2–3 weeks for engineers to redeploy.

**Solution:** JsonLogic + shadow backtesting. Risk managers update rules in a web UI, the system instantly measures impact on historical data, and approve/reject before going live. No code deploy required.

This is the **moat**: rapid iteration velocity on real fraud signals, not vendor lock-in.

---

## 📝 License

MIT

---

## 🤝 Contributing

Contributions welcome. Please ensure:
- Tests pass: `make test`
- Code lints: `make lint`
- New features include test coverage
- Temporal train/test split respected for any ML changes

---

## 📬 Questions?

See `docs/getting-started.md` for full walkthrough, or check `CLAUDE.md` for architecture deep-dives.
