# Feature Mapping: IEEE-CIS → DIBB Schema

This document maps the IEEE-CIS Fraud Detection dataset features to the SentryFlow DIBB (Device Intelligence + Behavioral Biometrics) feature schema, with mutual information scores from real data analysis.

---

## IEEE-CIS Dataset Overview

- **Transactions**: 590K rows × 394 features
- **Identities**: 144K rows × 41 features (24% match rate)
- **Fraud rate**: 3.5% (20,663 fraudulent transactions)
- **Time span**: ~180 days

---

## Feature Selection: Option B (6 features)

After EDA on real IEEE-CIS data, we selected 6 features based on mutual information scores:

| Feature | IEEE-CIS source | MI score | Type | Notes |
|---|---|---|---|---|
| `amount` | `TransactionAmt` | **0.0279** | direct | Direct mapping; strongest signal |
| `device_is_emulator` | DeviceType + id_31 | 0.0001 | engineered | Very weak in real data; kept for backward compatibility |
| `geo_velocity` | dist1 / D1 | 0.0065 | engineered | Weak but viable; inverse signal (lower = riskier) |
| `typing_entropy` | C1 normalized | 0.0148 | engineered | Good signal; normalized to [0, 6] |
| `card_count` | C1 raw | 0.0078 | direct | New in Phase 4; counts cards on billing address |
| `days_since_last_tx` | D1 | 0.0058 | direct | New in Phase 4; inverse signal (lower = riskier) |

**Why 6 instead of 4?** The `device_is_emulator` proxy (MI=0.0001) is statistically useless. Expanding to `card_count` (MI=0.0078) and `days_since_last_tx` (MI=0.0058) adds meaningful signal. The 4-field API contract is preserved for backward compatibility — the new fields are optional with sensible defaults.

---

## Engineered Features — Derivation Logic

### 1. `amount` — Direct

```
amount = TransactionAmt
```

**IEEE-CIS field**: `TransactionAmt` — transaction amount in USD

**Distribution**:
- Fraud mean: $149.24
- Legit mean: $134.51
- MI: 0.0279 (strongest signal)

### 2. `device_is_emulator` — Mobile + Browser heuristic

```python
is_mobile = (DeviceType == "mobile")
is_suspicious_browser = id_31.contains("mobile browser|webview|unknown")
device_is_emulator = (is_mobile & is_suspicious_browser)
```

**IEEE-CIS fields**:
- `DeviceType`: "mobile" vs "desktop" (76.2% missing)
- `id_31`: browser string, e.g. "chrome 63.0", "mobile safari 11.0" (76.2% missing)

**Note**: Only 24% of transactions have identity rows. When missing, treated as 0 (desktop/unknown browser).

**Distribution**:
- Fraud mean: 0.004 (0.4% of fraud is emulator)
- Legit mean: 0.001 (0.1% of legit is emulator)
- MI: 0.0001 (**very weak** — kept for API stability, not predictive value)

### 3. `geo_velocity` — Distance/Time Ratio

```python
geo_velocity = dist1 / max(D1, 1/24)  # miles / days, clamped to [0, 5000]
```

**IEEE-CIS fields**:
- `dist1`: billing–shipping address distance in miles (59.7% missing)
- `D1`: days since last transaction on card (0.2% missing)

**Logic**: High velocity (far distance in short time) is suspicious. When `dist1` is missing, treated as 0.

**Distribution**:
- Fraud mean: 82.2 (riskier — lower time window)
- Legit mean: 109.4 (safer — more time since last tx)
- **Inverse signal**: lower values are riskier
- MI: 0.0065 (weak but viable)

### 4. `typing_entropy` — Address Diversity Normalized

```python
typing_entropy = min(C1, 20) / 20 * 6  # normalized to [0, 6]
```

**IEEE-CIS field**: `C1` — number of addresses associated with billing card

**Logic**: More addresses on one card = suspicious activity pattern (fraud indicator). Normalized to [0, 6] to match API schema.

**Distribution**:
- Fraud mean: 1.628 (normalized) = 35.5 (raw C1)
- Legit mean: 0.916 (normalized) = 13.3 (raw C1)
- **Direct signal**: higher = riskier
- MI: 0.0148 (good signal)

### 5. `card_count` — Raw Address Count

```python
card_count = C1  # clamped to [0, 50]
```

**IEEE-CIS field**: `C1` (same as typing_entropy, but not normalized)

**Rationale**: Tree-based models (XGBoost, Isolation Forest) learn raw counts more efficiently than normalized versions. The normalized version is used for the API schema (typing_entropy) for interpretability; the raw version is used for training.

**Distribution**:
- Fraud mean: 35.5
- Legit mean: 13.3
- **Direct signal**: higher = riskier
- MI: 0.0078 (useful, added in Phase 4)

### 6. `days_since_last_tx` — Time Delta

```python
days_since_last_tx = D1  # clamped to [0, 365]
```

**IEEE-CIS field**: `D1` — days since last transaction on the payment card

**Logic**: Recent transactions (low D1) are riskier than historical accounts with gaps.

**Distribution**:
- Fraud mean: 38.6 days (active account, recent)
- Legit mean: 96.2 days (older/less frequent account)
- **Inverse signal**: lower = riskier (fraud is more recent activity)
- MI: 0.0058 (weak but viable, added in Phase 4)

---

## Backward Compatibility

The API contract (`RiskPayload` in `src/api/router.py`) accepts:

```python
class RiskPayload(BaseModel):
    # Required (4 DIBB fields)
    amount: float
    device_is_emulator: bool
    geo_velocity: float
    typing_entropy: float
    
    # Optional (2 enriched fields, defaults provided)
    card_count: Optional[float] = 1.0
    days_since_last_tx: Optional[float] = 30.0
```

Callers can:
1. Send only the 4 required fields — defaults are used (MI loss but acceptable)
2. Send all 6 fields — full signal available

The model training always uses all 6 fields when available (from `_engineer_dibb_features()` in the pipeline).

---

## Temporal Stability

The temporal 80/20 split uses `TransactionDT` ordering:

- **Training** (0–144 days): fraud rate 3.49%
- **Test** (145–180 days): fraud rate 3.50%
- **Drift**: < 0.01% (stable, no data leakage risk)

---

## Alternative Features Not Selected

From the IEEE-CIS feature set, these had non-negligible MI but were not selected:

| Feature | IEEE-CIS | MI | Reason for non-selection |
|---|---|---|---|
| `ProductCD` (product category) | Categorical | — | Sparse levels; omitted to keep feature count low |
| `card6` (debit/credit) | Categorical | — | Binary signal; confounded with `card_count` |
| Top V-features (Vesta proprietary) | V1–V339 | ~0.01–0.03 | Proprietary, not generalizable across vendors |

---

## Code Locations

- **Feature engineering**: `pipelines/backtest_flow.py::_engineer_dibb_features()`
- **API schema**: `src/api/router.py::RiskPayload`
- **Model features**: `src/models/train.py::FEATURE_COLS`
- **Training data loading**: `pipelines/backtest_flow.py::start()` step

All three locations must remain synchronized.
