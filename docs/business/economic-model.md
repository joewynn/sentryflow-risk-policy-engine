# Economic Model

SentryFlow's economic case rests on three levers: lower infrastructure cost-per-transaction, higher fraud catch rate, and faster policy response to emerging attack patterns.

---

## Comparative unit economics

*Note: catch rate and FPR figures below are modeled targets. Observed values on synthetic simulation data are reported by the training pipeline on each `make train` run. Do not cite these as production guarantees.*

| Driver | Legacy Vendor Stack | SentryFlow (Integrated) |
|---|---|---|
| API cost (per tx) | $0.45 (3–4 vendors) | $0.12 (infrastructure) |
| Fraud catch rate | 72% | 89% (model target) |
| False Positive Rate | 4.2% | 1.8% (model target) |
| Policy deployment | 14–21 days | < 10 minutes |
| Engineering overhead | 2 FTEs (hard-coded rules) | 0.5 TPM (self-serve) |

---

## 3-year TCO model

*Assumes $1B annual transaction volume, 2% baseline fraud attempt rate ($20M at risk).*

### Legacy scenario

| Cost driver | Annual |
|---|---|
| Direct fraud loss (28% slippage) | $5.6M |
| API fees (1M tx × $0.45) | $450k |
| Good-user churn from false positives | $4.2M |
| Engineering overhead | $400k |
| **Total** | **~$10.7M** |

### SentryFlow scenario

| Cost driver | Annual |
|---|---|
| Direct fraud loss (11% slippage) | $2.2M |
| Infrastructure COGS (1M tx × $0.12) | $120k |
| Good-user churn (1.8% FPR) | $1.8M |
| Operations (0.5 TPM) | $100k |
| **Total** | **~$4.2M** |

**Net delta: ~$6.5M saved annually** (varies with actual catch rate and transaction volume).

---

## Velocity of protection

The economic case extends beyond static costs. When a new social engineering script goes viral:

- **Legacy:** Engineering ships a hard-coded fix in 14 days. Exposure window: ~$1.2M in losses.
- **SentryFlow:** Risk Manager identifies the pattern via SHAP feature attribution, authors a JsonLogic rule in the dashboard, submits for 4-eyes review, deploys in under 10 minutes. Exposure window: <$50k.

Policy agility is an asymmetric advantage — each hour of response time advantage compounds during a viral fraud wave.

---

## Infrastructure cost model

SentryFlow's $0.12/tx COGS reflects self-hosted infrastructure:

- FastAPI on a single instance handles ~500 req/s at < 30ms p99
- Redis for DIBB signal caching
- Metaflow for batch training (runs weekly or on-demand)

The marginal cost per transaction is compute (not vendor API fees), making the unit economics improve at scale rather than degrade.
