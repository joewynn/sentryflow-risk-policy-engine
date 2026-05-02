# Getting Started

## Prerequisites

- Docker and Docker Compose
- Python 3.12 (for local development outside Docker)
- A Kaggle account with the [IEEE-CIS Fraud Detection dataset](https://www.kaggle.com/competitions/ieee-fraud-detection) accepted

---

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

Or create an isolated virtualenv (recommended):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python3 -r requirements.txt pytest httpx
```

---

## 2. Download training data

```bash
make setup
```

This downloads the IEEE-CIS fraud dataset (~500K transactions) to `data/` and unzips it.

---

## 3. Train the ML models

```bash
make train
```

Runs the Metaflow backtest pipeline (`pipelines/backtest_flow.py`). This:

- Generates a DIBB-enhanced synthetic dataset (or loads IEEE data if available)
- Performs a temporal 80/20 train/test split
- Trains XGBoost + Isolation Forest
- Saves models to `data/models/xgb_fraud.joblib` and `data/models/iso_anomaly.joblib`
- Evaluates on the held-out test set and prints Precision, Recall, FPR, AUPRC

!!! note "MockModel fallback"
    If you skip `make train`, the API still starts but uses a `MockModel` that returns a neutral 2% fraud probability for every transaction. A `RuntimeWarning` is logged at startup. Real SHAP explainability requires a trained model.

---

## 4. Start the stack

```bash
make up
```

Starts three services:

| Service | URL | Purpose |
|---|---|---|
| FastAPI | http://localhost:8000 | Risk decisioning API |
| Redis | localhost:6379 | DIBB signal cache |
| Streamlit dashboard | http://localhost:8501 | Risk Control Plane |

---

## 5. Send a risk check

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

The `device_is_emulator: true` and `geo_velocity: 800` will trigger the default policy rule and return a `BLOCK`.

---

## 6. Open the Risk Dashboard

Navigate to **http://localhost:8501**.

From the dashboard you can:

- Edit JsonLogic policies in the Policy Playground
- Run a vectorized ensemble backtest on 500–5000 simulated transactions
- View live-computed KPIs (catch rate, FPR, latency) after the backtest runs
- Submit policy changes for 4-eyes approval
- Approve or reject pending policies from the Approval Inbox

---

## 7. Run the tests

```bash
.venv/bin/python -m pytest tests/ -v
```

All 31 tests should pass. See [Running Tests](development/testing.md) for details.

---

## Stopping the stack

```bash
make down
```

---

## API documentation (auto-generated)

FastAPI generates interactive Swagger docs at:

- **http://localhost:8000/docs** — Swagger UI
- **http://localhost:8000/redoc** — ReDoc
