# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development environment
make up           # Start full stack: API (8000) + Redis (6379) + Dashboard (8501)
make down         # Stop Docker Compose stack

# Data & training
make setup        # Download and unzip IEEE fraud detection dataset
make train        # Run Metaflow training pipeline (pipelines/backtest_flow.py)
make deploy       # Deploy SageMaker endpoint via src/pipeline/sentryflow_pipeline.py

# Code quality & tests
make lint         # ruff check src/ tests/
make test         # pytest tests/

# Run a single test
pytest tests/path/to/test_file.py::test_function_name
```

## Architecture

SentryFlow is a two-speed fraud decisioning engine: a fast path (<30ms) for real-time transaction decisions, and a slow path (background thread) for SHAP explainability that never blocks the response.

### Fast Path — POST /v1/risk-check

```
Transaction Payload
  ↓
src/api/router.py          — FastAPI endpoint, loads XGBoost model at module level
  ├─→ src/policies/evaluator.py::evaluate_policy()   — JsonLogic rules against DIBB signals from Redis
  └─→ src/policies/evaluator.py::batch_orchestrate() — Ensemble fusion: rules + ML score → final decision
       └─→ Returns: PASS/BLOCK + action type + Nacha Adverse Action Code + audit metadata
```

**Ensemble strategy selection** in `batch_orchestrate()`:
- `ML_OVERRIDE_CRITICAL`: ML confidence >92% → REQUIRE_VIDEO_ID (overrides rules)
- `ML_ENHANCED_FRICTION`: ML confidence 75–92% → REQUIRE_MFA
- `RULE_LED`: Default rule-based path

### Slow Path — Background SHAP

`src/api/async_explain.py` fires a daemon thread after each response. SHAP feature importance is computed and written to the audit trail without touching the <30ms latency budget.

### ML Models (`src/models/train.py`)

Two complementary models trained together:
- **XGBoost** (Focal Loss, `scale_pos_weight=200`): supervised fraud patterns; optimized on `aucpr`
- **Isolation Forest** (`contamination=0.01`): unsupervised anomaly detection for zero-day synthetic identity clusters

`MockModel` fallback keeps the API live when no trained model exists yet.

### Policy Engine (`src/policies/evaluator.py`)

- JsonLogic-based rule evaluation — rules can be authored by risk managers in the Streamlit dashboard with no code deploy
- Severity-based conflict resolution: `DECLINE > VIDEO_ID > MFA > DELAY > APPROVE`
- `create_policy_signature()` produces a SHA256 hash for Nacha 2026 policy versioning
- All decisions produce immutable audit records (decision_id, timestamp, policy_version, Adverse Action Code)

### Governance (`src/governance/approval_queue.py`)

Policy changes go through a 4-eyes approval queue. Pending policies are stored as JSON files with ticket IDs derived from policy content + timestamp hash.

### Metaflow Training Pipeline (`pipelines/backtest_flow.py`)

5-step DAG: `start` → `train_ensemble_step` → `backtest` (5000 txns shadow mode) → `approval_gate` (FPR <2% check) → `end`

### Monitoring Dashboard (`research/monitoring_dashboard.py`)

Streamlit control plane on port 8501. Features: interactive JsonLogic policy editor, shadow backtest runner, KPI display (fraud catch rate, FPR, latency, ROI), policy governance submission, CFPB-compliant decision audit trace.

### Infrastructure

- **Redis**: Hot cache for DIBB signals (Device Intelligence + Behavioral Biometrics); frequency counters for velocity checks
- **Docker Compose**: `sentryflow-api` (8000), `redis` (6379), `sentryflow-dashboard` (8501)
- **SageMaker**: Production ML endpoint deployment via `src/pipeline/sentryflow_pipeline.py`
- **Metaflow**: ML training orchestration (supports local + AWS Step Functions)
- **MLflow**: Experiment tracking alongside Metaflow runs

## Key Design Constraints

- The <30ms p99 latency SLA is a hard constraint — nothing on the hot path may block on I/O or computation-heavy work. SHAP always runs in a background thread.
- Nacha 2026 compliance requires: immutable audit logs, SHA256 policy versioning, and Adverse Action Codes on every decline.
- The system must degrade gracefully — if XGBoost model is unavailable, rule-based decisions continue independently.
