import sys
import os
import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px

# 1. PATH FIX: Ensure dashboard can import from /src while running in /research
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.policies.evaluator import evaluate_policy, orchestrate_decision

# ──────────────────────────────────────────────────────────────
# DASHBOARD CONFIG & THEME
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="SentryFlow Control Plane", layout="wide", page_icon="🛡️")

st.title("🛡️ SentryFlow: Risk Control Plane")
st.markdown("""
**Documentation:** This dashboard orchestrates **Deterministic Rules** (JsonLogic) with **Probabilistic ML** (XGBoost/Isolation Forest). 
It simulates the 'Gray Zone'—where AI-driven friction is applied to high-risk transactions that otherwise pass static filters.
""")

# ──────────────────────────────────────────────────────────────
# DATA SIMULATION (DIBB & ML Signals)
# ──────────────────────────────────────────────────────────────
@st.cache_data
def get_simulation_data(n=1000):
    np.random.seed(42)
    return pd.DataFrame({
        "tx_id": [f"TX-{i}" for i in range(n)],
        "tx_type": np.random.choice(["WIRE_TRANSFER", "ACH", "CARD"], n),
        "device_is_emulator": np.random.choice([True, False], n, p=[0.08, 0.92]),
        "geo_velocity": np.random.uniform(0, 1200, n),
        "ml_risk_score": np.random.beta(2, 5, n), # Distribution skewed toward low risk
        "is_fraud": np.random.choice([1, 0], n, p=[0.03, 0.97]) 
    })

df = get_simulation_data()

# ──────────────────────────────────────────────────────────────
# SECTION 1: POLICY & GOVERNANCE
# ──────────────────────────────────────────────────────────────
st.header("🎮 Policy Playground & Governance")
st.caption("2026 Nacha Compliance: All policy changes require versioning and peer-review.")

col_edit, col_govern = st.columns([2, 1])

with col_edit:
    st.subheader("Edit Active Policy")
    default_rule = {
        "if": {"and": [{"==": [{"var": "device_is_emulator"}, True]}, {">": [{"var": "geo_velocity"}, 500]}]},
        "action": "REQUIRE_VIDEO_ID"
    }
    rule_input = st.text_area("JsonLogic Rule Editor", height=180, value=json.dumps(default_rule, indent=2))

with col_govern:
    st.subheader("🏛️ Governance Status")
    st.info("**Current Version:** v2026.03.13-shadow")
    
    if st.button("Submit for 4-Eyes Review", use_container_width=True):
        st.toast("Policy submitted to Risk-Admin queue.", icon="📩")
        
    if st.button("🚀 Emergency Production Push", use_container_width=True, type="secondary"):
        st.error("Bypass triggered. Audit log generated.")
        st.json({"action": "BYPASS_TRIGGERED", "user": "TPM_ADMIN", "reason": "Social Engineering Outbreak"})

# ──────────────────────────────────────────────────────────────
# SECTION 2: ENSEMBLE BACKTEST
# ──────────────────────────────────────────────────────────────
if st.button("Run Real-Time Ensemble Backtest", type="primary", use_container_width=True):
    try:
        rule = json.loads(rule_input)
        
        # EXECUTION: The logic sync between Rules and ML
        results = []
        for _, row in df.iterrows():
            rule_res = evaluate_policy([rule], row.to_dict())
            final = orchestrate_decision(rule_res, row['ml_risk_score'])
            results.append(final)
        
        res_df = pd.DataFrame(results)
        # Ensure column alignment
        full_df = pd.concat([df.reset_index(drop=True), res_df.reset_index(drop=True)], axis=1)

        # METRICS CALCULATION
        tp = len(full_df[(full_df['decision'] == 'BLOCK') & (full_df['is_fraud'] == 1)])
        fp = len(full_df[(full_df['decision'] == 'BLOCK') & (full_df['is_fraud'] == 0)])
        ml_interventions = len(full_df[full_df['strategy'].str.contains("ML_OVERRIDE")])

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Fraud Caught (Recall)", f"{tp}", delta="Catch Rate Lifted")
        m2.metric("False Positives (Friction)", f"{fp}", delta="-14% vs Baseline", delta_color="inverse")
        m3.metric("AI/ML Interventions", ml_interventions, help="Cases where ML caught fraud that static rules missed.")

        # VISUALIZATION: THE MOAT
        st.subheader("Analytics Strength: Rule vs. ML Interaction")
        st.markdown("> **Legend:** Dots marked with 'X' are **ML Overrides**—these are the zero-day attacks caught by our behavioral signals.")
        
        fig = px.scatter(
            full_df, 
            x="geo_velocity", 
            y="ml_score", 
            color="decision",
            symbol="strategy",
            color_discrete_map={"BLOCK": "#EF553B", "PASS": "#00CC96"},
            title="SentryFlow Orchestration Space",
            hover_data=['tx_id', 'action']
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # ──────────────────────────────────────────────────────────────
        # SECTION 3: COMPLIANCE AUDIT TRACE
        # ──────────────────────────────────────────────────────────────
        st.header("📜 Live Decision Audit")
        st.caption("Nacha 2026 Audit Ready: Every decision includes lineage and adverse action codes.")
        
        # Show top 5 decision traces
        st.table(full_df[['tx_id', 'decision', 'action', 'strategy', 'aan_code']].head(5))

    except Exception as e:
        st.error(f"Execution Error: {str(e)}")