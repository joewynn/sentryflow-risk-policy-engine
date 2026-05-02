# ML Models

SentryFlow uses two complementary models that cover different parts of the fraud landscape.

---

## XGBoost — supervised fraud classifier

**Purpose:** Detect known fraud patterns (social engineering, account takeover, card fraud) using labeled historical data.

**Configuration** (`src/models/train.py`):

```python
xgb.XGBClassifier(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    scale_pos_weight=neg / pos,   # computed from actual class ratio
    eval_metric="aucpr",           # precision-recall AUC — correct for imbalanced fraud
    random_state=42,
)
```

**Class imbalance:** `scale_pos_weight` is computed dynamically from the training data's fraud rate — not hardcoded. For a 3% fraud rate this is ~33; for 0.5% it is ~200.

**Training split:** An internal 85/15 train/validation split is used inside `train_ensemble()` to track `aucpr` during fitting. This is separate from the outer 80/20 temporal train/test split used by the pipeline for final evaluation.

**Evaluation metric:** AUPRC (Area Under Precision-Recall Curve) is the correct metric for fraud — it is robust to class imbalance where AUROC can be misleadingly high.

**Saved to:** `data/models/xgb_fraud.joblib`

---

## Isolation Forest — unsupervised anomaly detector

**Purpose:** Detect zero-day synthetic identity clusters and novel attack patterns that have no historical labels for supervised learning to train on.

**Configuration:**

```python
IsolationForest(
    contamination=fraud_rate,   # matches actual fraud rate in training data
    random_state=42,
)
```

**Contamination:** Set to the observed fraud rate in training data, clamped to [0.001, 0.1]. This avoids the common mistake of hardcoding `contamination=0.01` when the actual fraud rate is different.

**Evaluation:** Isolation Forest predictions are evaluated against ground-truth `is_fraud` labels in `backtest_flow.py`, reporting recall and precision for the unsupervised component independently.

**Current API integration:** The Isolation Forest is evaluated in the backtest pipeline but its score is not yet combined into the real-time API fast path. The XGBoost `predict_proba` score is what drives `batch_orchestrate()`.

**Saved to:** `data/models/iso_anomaly.joblib`

---

## Feature columns

Both models are trained on the same four features:

| Feature | Type | Description |
|---|---|---|
| `amount` | float | Transaction amount in USD |
| `geo_velocity` | float | km/h since last known location |
| `typing_entropy` | float | Shannon entropy of keystroke timing |
| `device_is_emulator` | bool (int) | 1 if device fingerprint matches emulator patterns |

See [DIBB Signals](dibb.md) for full signal definitions.

---

## MockModel fallback

When `data/models/xgb_fraud.joblib` doesn't exist (e.g. before `make train` is run), `load_model()` returns a `MockModel` with a `RuntimeWarning`. The MockModel:

- Returns `predict_proba` of `[0.98, 0.02]` for every input (neutral 2% fraud probability)
- Has no `get_booster()` method — async SHAP is skipped when MockModel is active
- Allows the API to serve requests so rule-based decisions still work during initial development

**Do not rely on MockModel in production.** Run `make train` to build the real model.

---

## Training pipeline

The full training workflow is in `pipelines/backtest_flow.py` (Metaflow DAG):

```
start → train_ensemble_step → backtest → approval_gate → end
```

1. **start** — generate synthetic DIBB dataset (or load IEEE data)
2. **train_ensemble_step** — temporal 80/20 split, train XGB + IsoForest on training 80%
3. **backtest** — run ensemble orchestration on held-out 20%, compute full metric suite
4. **approval_gate** — check FPR < 2%; fail the pipeline if threshold exceeded
5. **end** — print JSON audit log with all metrics

Run with:

```bash
make train
# or directly:
python pipelines/backtest_flow.py run
```
