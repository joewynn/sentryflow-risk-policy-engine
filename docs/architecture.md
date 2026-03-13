# **SentryFlow System Architecture**

## **Overview**

SentryFlow uses a **Two-Speed Architecture** to decouple critical-path decisions from heavy-compute explainability.

## **High-Level Diagram**

## **Component Breakdown**

1. **Inference Gateway (FastAPI):**
   * **Latency Target:** <30ms p99.
   * **Function:** Orchestrates the "Fast-Path." It retrieves features from the hot-cache (Redis) and runs the `evaluator.py` (JsonLogic).

2. **The Ensemble Engine:**
    * **XGBoost:** Supervised learning for known fraud patterns (Social Engineering, ATO).
   * **Isolation Forest:** Unsupervised anomaly detection for "Zero-Day" synthetic identity clusters.


3. **Shadow-SHAP Worker (Asynchronous):**
   * Fires a background thread via `async_explain.py` immediately after the response is sent.
   * Ensures that computationally expensive feature importance (SHAP) does not block the user's transaction.

4. **The "Sardine" Feature Store (Redis):**

* Stores real-time **DIBB signals** (Device Intelligence & Behavioral Biometrics) like `typing_entropy` and `geo_velocity`.

**"Graceful Degradation."** If the ML model is down, the JsonLogic engine still functions on static rules.

## **Data Flow**

1. **Ingress:** API receives a transaction payload.
2. **Orchestration:** Engine pulls DIBB signals and checks against current `JsonLogic` policy.
3. **Decision:** Returns `PASS/BLOCK` + `AdverseActionCode`.
4. **Explainability:** Background thread calculates SHAP and logs to the **Audit Trail** (S3/Snowflake).
