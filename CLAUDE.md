# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development environment
make up           # Start full stack: API (8000) + Redis (6379) + Dashboard (8501)
make down         # Stop Docker Compose stack

# Data & training
make setup        # Download and unzip IEEE fraud detection dataset
make train        # Run ZenML training pipeline (pipelines/training_pipeline.py)
make train-dev    # ZenML pipeline with sample data + isolated model name (fast iteration)
make zenml-ui     # Launch ZenML dashboard on http://localhost:8237
make zenml-status # List model versions and active stack
make zenml-rollback VERSION=<n>  # Promote a previous model version to Production

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

Two complementary models trained together by `pipelines/training_pipeline.py`:
- **XGBoost** (Focal Loss, `scale_pos_weight=200`): supervised fraud patterns; optimized on `aucpr`
- **Isolation Forest** (`contamination=0.01`): unsupervised anomaly detection for zero-day synthetic identity clusters

Both models are versioned artifacts in ZenML MCP, stored in S3. The API loads the `Production`-staged version at startup via `load_model_from_zenml()`. A local cache at `.zenml_cache/prod_xgb.joblib` (path overridable via `SENTRYFLOW_MODEL_CACHE_DIR`) provides outage resilience — if ZenML is unreachable on restart, the last known production model is served. If neither is available the API raises `RuntimeError` rather than serving fake scores.

### Policy Engine (`src/policies/evaluator.py`)

- JsonLogic-based rule evaluation — rules can be authored by risk managers in the Streamlit dashboard with no code deploy
- Severity-based conflict resolution: `DECLINE > VIDEO_ID > MFA > DELAY > APPROVE`
- `create_policy_signature()` produces a SHA256 hash for Nacha 2026 policy versioning
- All decisions produce immutable audit records (decision_id, timestamp, policy_version, Adverse Action Code)

### Governance (`src/governance/approval_queue.py`)

Policy changes go through a 4-eyes approval queue. Pending policies are stored as JSON files with ticket IDs derived from policy content + timestamp hash.

### ZenML Training Pipeline (`pipelines/training_pipeline.py`)

5-step pipeline: `ingest_and_engineer` → `build_graph_features` → `train_ensemble_step` → `run_backtest` → `approval_gate`

- Data paths and model name are fully external (no hardcoded defaults): configured via `run_config.yaml` and `SENTRYFLOW_MODEL_NAME` / `SENTRYFLOW_RUN_CONFIG` env vars
- `approval_gate` is the only promotion gate: FPR < 2% → `ModelStages.PRODUCTION` in ZenML MCP
- Step caching enabled — re-runs only steps whose inputs changed; override with `--no-cache`
- Dev run: `make train-dev` uses `run_config_dev.yaml` + `sentryflow_xgb_dev` model name to keep the main model history clean

### Monitoring Dashboard (`research/monitoring_dashboard.py`)

Streamlit control plane on port 8501. Features: interactive JsonLogic policy editor, shadow backtest runner, KPI display (fraud catch rate, FPR, latency, ROI), policy governance submission, CFPB-compliant decision audit trace.

### Infrastructure

- **Redis**: Hot cache for DIBB signals (Device Intelligence + Behavioral Biometrics); frequency counters for velocity checks
- **Docker Compose**: `sentryflow-api` (8000), `redis` (6379), `sentryflow-dashboard` (8501)
- **ZenML**: ML pipeline orchestration, experiment tracking, and Model Control Plane (self-hosted server)
- **S3**: Artifact store for all ZenML pipeline outputs (`s3://sentryflow-mlops/zenml/`)
- **ZenML MCP**: Model versioning and staging (`sentryflow_xgb` model; `Production` stage served by API)

## Key Design Constraints

- The <30ms p99 latency SLA is a hard constraint — nothing on the hot path may block on I/O or computation-heavy work. SHAP always runs in a background thread.
- Nacha 2026 compliance requires: immutable audit logs, SHA256 policy versioning, and Adverse Action Codes on every decline.
- The system must degrade gracefully — if ZenML MCP is unreachable at startup, the API loads from the local `.zenml_cache/` fallback. If no cache exists it raises `RuntimeError` rather than serving a mock model (compliance requirement).
- Never re-introduce `MockModel` as a silent fallback on the API hot path — it bypasses Nacha 2026 audit requirements.
