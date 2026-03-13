# **Governance & Policy Lifecycle Management**

## **1. The "Four-Eyes" Principle**

In compliance with **Nacha 2026** and **SOC2 Type II** requirements, SentryFlow enforces a strict separation of duties. No single user can draft and deploy a risk policy to production without a secondary peer review.

### **Roles & Permissions**

* **Risk Analyst:** Can create, edit, and backtest rules in the "Shadow" environment.
* **Senior TPM / Risk Manager:** Authorized to review backtest results (Precision/Recall) and approve deployment.
* **Compliance Officer:** Has "Read-Only" access to all historical audit traces and policy versions.

---

## **2. Policy Promotion Lifecycle**

The following stages ensure that new fraud-fighting rules do not cause massive "Good User" friction or operational outages.

### **Stage 1: Draft & Playback**

* **Action:** Analyst writes a new `JsonLogic` rule in the Playground.
* **Goal:** Ensure the logic is syntactically correct.
* **Outcome:** A unique `Draft_ID` is generated.

### **Stage 2: Shadow Mode Backtesting**

* **Action:** The Draft policy is run against the last 24–48 hours of historical data via the `pipelines/backtest_flow.py`.
* **Metric Thresholds:** A rule must maintain a **False Positive Rate (FPR) < 2.0%** to proceed without a manual override justification.
* **ML Interaction:** The system analyzes where the **Isolation Forest** (unsupervised) and the **Rules** (deterministic) conflict.

### **Stage 3: Peer Review & Approval**

* **Action:** A second authorized user reviews the **Precision-Recall Curve** and the **Total Block Rate**.
* **Audit Log:** The approver’s UID is permanently attached to the policy metadata.

### **Stage 4: Edge Deployment**

* **Action:** Upon approval, the policy is promoted to the `ACTIVE` status in the Redis cache and FastAPI gateway.
* **SLA:** Global propagation to all edge nodes in **< 10 minutes**.

---

## **3. Compliance & Auditability (Nacha 2026)**

Every transaction processed by SentryFlow generates a **Decision Lineage Packet**. If a regulator audits a specific "Decline" action, SentryFlow can reconstruct:

1. **Policy_ID:** The specific JSON logic active at that millisecond.
2. **Model_ID:** The XGBoost/Isolation Forest weights used for the ensemble score.
3. **AAN Code:** The specific Adverse Action Code (e.g., R03) sent to the user.
4. **SHAP Attribution:** The top 3 behavioral features (e.g., `typing_entropy`) that drove the decision.

---

## **4. Emergency Override Protocol ("Red Button")**

In the event of a **Viral Fraud Outbreak** (e.g., a romance scam trending on social media), a Senior TPM can trigger an **Emergency Push**.

* **Bypass:** Skips the Peer Review stage for immediate protection.
* **Consequence:** Triggers an automatic "High Priority" incident report to the Compliance team for post-mortem review within 24 hours.
