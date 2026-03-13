# **SentryFlow: Economic Model & Vendor Displacement Strategy**

## **1. Executive Summary: The "Transparency Tax"**

Currently, mid-market fintechs rely on a fragmented stack of 3–5 specialized vendors for identity, device, and behavioral signals. This creates a "Transparency Tax"—high costs per transaction, data silos that lead to lower catch rates, and an inability to respond to real-time attacks.

SentryFlow displaces this model by consolidating high-fidelity signals (DIBB) into a single, orchestrated policy layer.

---

## **2. Comparative Unit Economics**

| Driver | Legacy Vendor Stack | SentryFlow (Integrated) | Impact |
| --- | --- | --- | --- |
| **Direct COGS (per Tx)** | $0.45 | **$0.12** | 73% Cost Reduction |
| **Fraud Catch Rate** | 72% | **89%** | 17% Detection Lift |
| **False Positive Rate** | 4.2% | **1.8%** | 57% Friction Reduction |
| **Policy Agility** | 14-21 Days | **< 10 Minutes** | Near-instant Response |

---

## **3. 3-Year Total Cost of Ownership (TCO) Model**

*Assumes $1B annual transaction volume with a 2% baseline fraud attempt rate ($20M at risk).*

### **Scenario A: The Legacy Cost ($12.4M Loss)**

* **Direct Fraud Loss:** 28% slippage = **$5.6M**
* **API Fees:** 1M transactions * $0.45 = **$450k**
* **Good User Churn:** 4.2% FPR on $1B volume (assuming 10% conversion loss on blocked good users) = **$4.2M**
* **Engineering Overhead:** 2 FTEs dedicated to hard-coding risk rules = **$400k**

### **Scenario B: The SentryFlow Win ($3.1M Loss)**

* **Direct Fraud Loss:** 11% slippage = **$2.2M**
* **Infrastructure COGS:** 1M transactions * $0.12 = **$120k**
* **Recovered GMV:** 1.8% FPR = **$1.8M** (A **$2.4M recovery** vs. Legacy)
* **Operational Efficiency:** 0.5 TPM for self-serve policy management = **$100k**

**Net Delta:** **$9.3M saved annually.**

---

## **4. The "Velocity of Protection" Multiplier**

Beyond static costs, SentryFlow addresses the **Viral Fraud** problem.

* **Legacy:** A new social engineering script goes viral on Telegram. By the time the vendor updates their "Black Box" or Engineering ships a hard-coded fix (14 days), the platform has lost **$1.2M**.
* **SentryFlow:** Risk Managers identify the pattern via SHAP explanations and deploy a `JsonLogic` block in **8 minutes**. Total loss exposure is capped at **<$50k**.

---

## **5. Build vs. Buy Logic for Sardine Customers**

When presenting this to a prospect (or an interviewer), anchor on **Gross Margin Improvement**:

> *"By moving from a variable-cost vendor model to an integrated SentryFlow infrastructure, we move risk from a line-item expense to a margin-expansion lever. We aren't just saving money on fraud; we're making every transaction more profitable."*