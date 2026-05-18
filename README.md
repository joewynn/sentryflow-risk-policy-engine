# SentryFlow: Real-Time Fraud & Synthetic Identity Detection

![Python 3.12](https://img.shields.io/badge/python-3.12-blue) 
![License MIT](https://img.shields.io/badge/license-MIT-green)
![Nacha 2026](https://img.shields.io/badge/Compliance-Nacha_2026-orange)

A production-grade real-time risk orchestration engine combining **supervised ML** (XGBoost on 590K real fraud transactions) + **unsupervised anomaly detection** (Isolation Forest for synthetic identity patterns) with **policy autonomy** for Risk Managers to deploy rules in minutes, not weeks.

---

## 🎯 Why This Exists

**The Problem:** Legacy fraud vendors are slow (2–3 weeks to deploy rules), expensive ($0.45/transaction), and miss modern attack patterns (synthetic identity fraud, AI-generated behavior). SentryFlow decouples risk logic from engineering deployments, enabling rapid iteration on real data.

**The Result:** Trained on **IEEE-CIS Fraud Detection dataset (590K real e-commerce transactions)** with rigorous temporal evaluation and three phases of feature engineering:

| Metric | Current (Phase 3: 19 features) | Note |
|--------|------|------|
| **Fraud Detection Recall** | **22.1%** @ 0.36% FPR | Catch ~1 in 5 frauds with <1% false positives |
| **AUROC** | **0.8351** | Strong discriminative power; dataset ceiling at ~0.84 |
| **Precision** | 68.6% | High confidence decisions |
| **Isolation Forest Recall** | **12.13%** | Anomaly detection effective for zero-days |
| **Decision Latency (p99)** | **<30ms** | Fast path only; async SHAP in background |
| **Policy Deploy Time** | **<5 minutes** | Risk managers via dashboard, no code deploy |
| **Governance** | ✅ **FPR 0.36% < 2% gate** | All decisions pass regulatory requirement |

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
- **XGBoost (Focal Loss):** Supervised fraud patterns. Trained on 80% of real data; validated on 20% hold-out set. AUROC 0.8351.
- **Isolation Forest:** Unsupervised zero-day detection. Catches synthetic identity clusters that supervised models miss. Recall improved 6.25pp with graph features.
- **Feature Engineering (19 features):**
  - **Phase 1 (6 DIBB):** amount, device_is_emulator, geo_velocity, typing_entropy, card_count, days_since_last_tx
  - **Phase 2 (9 enriched):** uid_tx_count, uid_amt_mean, uid_amt_std, email_domain_risk, email_domain_freq, card1_addr1_freq, tx_hour, is_late_night, D2_norm
  - **Phase 3 (4 graph):** graph_degree, graph_cc_size, graph_shared_email_cnt, graph_shared_addr_cnt (91M edges from shared identity attributes)

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
└── training_pipeline.py  # ZenML pipeline: ingest → graph → train → backtest → approve

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

This project is **fully reproducible** with real data and comprehensive experiment tracking:

### Experiments Report
See **`docs/EXPERIMENTS.md`** for complete analysis of three feature engineering phases:
- **Phase 1:** Threshold calibration (found model discrimination bottleneck)
- **Phase 2:** 9 enriched features (AUROC 0.776 → 0.8347, +7.6%)
- **Phase 3:** 4 graph features (AUROC flat, Isolation Forest +6.25pp, Recall +3.84pp)

### Implementation Details
1. **Data:** IEEE-CIS Fraud Detection (590K transactions, 3.5% fraud rate)
2. **Feature Research:** `research/eda_ieee_fraud.ipynb` computes mutual information scores for all candidate features
3. **Training:** `make train` runs ZenML pipeline with temporal 80/20 split (no data leakage)
4. **Experiment Tracking:** `make zenml-ui` launches the ZenML dashboard — runs, metrics, and model versions
5. **Evaluation:** All metrics computed on held-out test set; governance gate (FPR < 2%) required for promotion
6. **Documentation:** `docs/EXPERIMENTS.md` maps IEEE-CIS columns → 19 engineered features with phase-by-phase improvements

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
- ZenML for reproducible ML pipelines with Model Control Plane (local + cloud)
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
make train     # ZenML training pipeline on real data (S3 + MCP)
make train-dev # ZenML pipeline with sample data + isolated model name
make zenml-ui  # ZenML dashboard on http://localhost:8237
make docs-serve # MkDocs on localhost:8000
```

For single test: `pytest tests/path/to/test.py::test_name`

---

## 📈 What's Achievable vs. Future Work

### ✅ Current Capabilities (Phase 3 - Optimized)
- **22.1% fraud recall** @ 0.36% FPR (catch ~1 in 5 frauds, <1% false positives)
- **12.13% anomaly detection** via Isolation Forest (zero-day synthetic identity clusters)
- **AUROC 0.8351** (strong model discrimination)
- **<30ms decision latency** (real-time decisioning)
- **Full governance** (Nacha 2026 compliance, 4-eyes approval, audit trails)

### ⚠️ Current Limitations
- **Not achievable with current approach:** 80% recall @ <2% FPR
  - Would require AUROC >0.90 (IEEE-CIS dataset tops out at ~0.84 with tabular features)
  - Fundamental issue: dataset lacks external signals (IP reputation, merchant networks, device fingerprinting)

### 🔮 Future Improvements (Phase 4+)
To reach 80% recall, would require one of:
1. **External data integration:** IP reputation + merchant networks + BIN risk scores (could improve AUROC to 0.90+)
2. **Graph Neural Networks:** GraphSAGE embeddings (modest gains, likely +2-5% recall)
3. **Velocity checks:** Real-time customer behavior profiling (different signal type)

**Decision:** Phase 4 shelved. Current 22% recall @ FPR<0.5% is valuable for fraud prevention. External data integration prioritized as higher-ROI path for future improvement.

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

See `docs/getting-started.md` for full walkthrough, `CLAUDE.md` for architecture deep-dives, or `docs/zenml-adoption-2026-05-17.md` for the ZenML migration plan and bootstrap commands.
