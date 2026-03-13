# **PRD: SentryFlow Risk Policy Engine (v2026.03)**

## **1. Executive Summary**

SentryFlow is a real-time risk orchestration layer designed to stop **AI-driven Social Engineering** and **Synthetic Identity** fraud. By decoupling risk logic from core engineering deployments using `JsonLogic`, SentryFlow allows Risk teams to deploy protective "friction" (MFA, Video ID, Delay) in minutes rather than weeks.

## **2. Problem Statement**

* **The Response Gap:** In 2026, LLM-powered fraud tactics rotate daily. Hard-coded rules result in a **2–3 week lag**, causing preventable losses of **$800k - $2M** per incident.
* **Compliance Burden:** New **Nacha 2026** "Failure to Prevent Fraud" mandates proactive monitoring. Legacy "black-box" scores lack the granular auditability required for regulatory exams.
* **High COGS:** Fragmented vendor stacks cost **$0.45/tx** and create high False Positive Rates (4.2%).

## **3. Goals & Key Results (OKRs)**

* **Goal 1: Reduce Fraud Losses.** Target: Lift Fraud Catch Rate from 72% to **89%**.
* **Goal 2: Lower Operational Friction.** Target: Reduce FPR from 4.2% to **1.8%**.
* **Goal 3: Operational Agility.** Target: Reduce "Time to Policy Deployment" from 14 days to **<10 minutes**.
* **Goal 4: Cost Efficiency.** Target: Reduce platform COGS to **$0.12/tx**.

## **4. Technical Requirements**

### **4.1 Real-Time Decisioning (The "Fast Path")**

* **SLA:** <30ms p99 latency for the core decision response.
* **Logic Engine:** Support for `JsonLogic` to allow no-code rule updates.
* **Input Signals:** Integration of **DIBB** (Device Intelligence & Behavioral Biometrics) including `typing_entropy` and `geo_velocity`.

### **4.2 Asynchronous Explainability (The "Slow Path")**

* **Feature:** Trigger a background thread for SHAP (Feature Importance) calculation immediately after a decision is returned.
* **Requirement:** Ensure background threads do not compete with the request/response loop for CPU resources during peak traffic.

## **5. Compliance & Auditability (Nacha 2026 Ready)**

To meet 2026 regulatory standards, every automated decision **must** be traceable.

* **Audit Payload:** Every API response must log:
* `PolicyVersionID`: The specific JSON logic used.
* `ModelVersionID`: The ML model weights at the time of inference.
* `AdverseActionCode`: Standardized codes (e.g., R03 for Security, R01 for Identity) for transparency.

* **Traceability:** One-click retrieval of the "Why" (SHAP top features) for any `TransactionID` in the Risk Manager dashboard.

## **6. User Persona & JTBD (Jobs To Be Done)**

* **The Risk Manager:** "I need to stop a new fraud attack on Saturday morning without waiting for a developer to ship code."
* **The Compliance Officer:** "I need to prove to the CFPB/FinCEN that our automated blocks are based on objective, non-biased data."
* **The CTO:** "I need our risk engine to scale to 10k TPS without increasing our AWS bill or slowing down the checkout flow."

## **7. Economic Model (Build vs. Buy)**

| Scenario | Vendor-Only | SentryFlow |
| --- | --- | --- |
| **Catch Rate** | 72% | 89% |
| **COGS per Tx** | $0.45 | $0.12 |
| **3-Year ROI ($1B Vol)** | -$12.4M (Loss) | -$3.1M (75% Reduction) |
