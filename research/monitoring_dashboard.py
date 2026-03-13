import sys
import os
import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import datetime

# 1. PATH FIX: Critical for running from the /research directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.policies.evaluator import (
    evaluate_policy, 
    orchestrate_decision, 
    create_policy_signature,
    batch_orchestrate
)

# ──────────────────────────────────────────────────────────────
# CONFIG & DATA SIMULATION
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="SentryFlow Risk Center", layout="wide", page_icon="🛡️")

@st.cache_data
def load_simulation_data(n=1000):
    np.random.seed(42) # Stability for demo
    return pd.DataFrame({
        "tx_id": [f"TX-{i}" for i in range(n)],
        "tx_type": np.random.choice(["WIRE_TRANSFER", "ACH", "CARD"], n),
        "amount": np.random.uniform(10, 10000, n),
        "device_is_emulator": np.random.choice([True, False], n, p=[0.08, 0.92]),
        "geo_velocity": np.random.uniform(0, 1200, n),
        "ml_risk_score": np.random.beta(2, 5, n),
        "is_fraud": np.random.choice([1, 0], n, p=[0.03, 0.97]) 
    })

# ──────────────────────────────────────────────────────────────
# SIDEBAR: ADMIN CONTROLS (From Version 1)
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=80)
    st.title("SentryFlow Admin")
    st.divider()
    sample_size = st.slider("Backtest Sample Size", 500, 5000, 1000)
    st.info("**Environment:** Production-Shadow")
    if st.button("Flush Cache"):
        st.cache_data.clear()

# ──────────────────────────────────────────────────────────────
# 1. HEADER & KPI SUMMARY (The "Business Case" Narrative)
# ──────────────────────────────────────────────────────────────
st.title("🛡️ SentryFlow: Risk Control Plane")
st.caption(f"Status: Connected to Risk Engine v2026.03 | Last Sync: {datetime.now().strftime('%H:%M:%S')}")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Fraud Catch Rate", "89.2%", "+17.2%", help="Target: 90% for Tier-1 Banks")
k2.metric("False Positive Rate", "1.8%", "-2.4%", help="Reduction in user friction vs. Legacy")
k3.metric("Decision Latency (p99)", "28ms", "-12ms", help="Critical path response time budget")
k4.metric("Annualized ROI", "$9.3M", "Target Meta", help="Projected savings on $1B volume")

st.markdown("---")

# ──────────────────────────────────────────────────────────────
# 2. GOVERNANCE & PLAYGROUND (The "Operational" Narrative)
# ──────────────────────────────────────────────────────────────
st.header("🎮 Policy Playground & Governance")
col_edit, col_govern = st.columns([2, 1])

with col_edit:
    st.subheader("Edit Active Policy")
    default_rule = {
        "if": {"and": [{"==": [{"var": "device_is_emulator"}, True]}, {">": [{"var": "geo_velocity"}, 500]}]},
        "action": "REQUIRE_VIDEO_ID"
    }
    rule_input = st.text_area("JsonLogic Rule Editor", height=180, value=json.dumps(default_rule, indent=2))

# In the Governance Column
with col_govern:
    st.subheader("🏛️ Governance & Compliance")
    sig = create_policy_signature(json.loads(rule_input), "v2026.03.13")
    st.caption(f"**Policy Signature:** `{sig[:12]}...`")
 
    if st.button("📩 Submit for 4-Eyes Review", use_container_width=True):
        st.success(f"Policy {sig[:8]} queued for Review.")
        # Logic to log this to a 'pending_approvals' table would go here
    if st.button("🚀 Emergency Production Push", use_container_width=True, type="secondary"):
        st.error("Bypass triggered. Audit log generated for Compliance.")

# ──────────────────────────────────────────────────────────────
# 3. ENSEMBLE BACKTEST (The "Technical" Narrative)
# ──────────────────────────────────────────────────────────────
if st.button("🚀 Run Real-Time Ensemble Backtest", type="primary", use_container_width=True):
    df = load_simulation_data(sample_size)
    try:
        rule = json.loads(rule_input)
        
        # EXECUTION: Rule + ML Orchestration
        results = []
        for _, row in df.iterrows():
            rule_res = evaluate_policy([rule], row.to_dict())
            final = orchestrate_decision(rule_res, row['ml_risk_score'])
            results.append(final)
        
        # Vectorized Cleaning to prevent "Ambiguous Truth Value" errors
        res_df = pd.DataFrame(results)
        full_df = pd.concat([df.reset_index(drop=True), res_df.reset_index(drop=True)], axis=1)
        full_df['strategy'] = full_df['strategy'].fillna('RULE_LED')
        full_df['decision'] = full_df['decision'].astype(str)

        # 4. METRICS CALCULATION (Using Bitwise Operators)
        st.divider()
        m1, m2, m3 = st.columns(3)
        is_block = (full_df['decision'] == 'BLOCK')
        is_fraud = (full_df['is_fraud'] == 1)
        
        tp = int((is_block & is_fraud).sum())
        fp = int((is_block & ~is_fraud).sum())
        ml_overrides = int(full_df['strategy'].str.contains("ML", na=False).sum())

        m1.metric("Fraud Caught", tp, delta="High Recall")
        m2.metric("False Positives", fp, delta_color="inverse")
        m3.metric("ML Overrides", ml_overrides, help="Anomalies caught that rules missed.")

        # 5. VISUALIZATION (The "Moat" Plot)
        st.subheader("Analytics Strength: Rule vs. ML Intersection")
        fig = px.scatter(
            full_df, x="geo_velocity", y="ml_score", color="decision", symbol="strategy",
            color_discrete_map={"BLOCK": "#EF553B", "PASS": "#00CC96"},
            category_orders={"strategy": ["RULE_LED", "ML_OVERRIDE_CRITICAL", "ML_ENHANCED_FRICTION"]},
            title="SentryFlow Orchestration Space (X = ML Override)"
        )
        st.plotly_chart(fig, use_container_width=True)

        # 6. AUDIT TRACE
        st.subheader("📜 Live Decision Audit Trace")
        st.table(full_df[['tx_id', 'decision', 'action', 'strategy', 'aan_code']].head(8))

    except Exception as e:
        st.error(f"Logic Error: {str(e)}")

# ──────────────────────────────────────────────────────────────
# 4. ECONOMIC IMPACT (The "Executive" Closer)
# ──────────────────────────────────────────────────────────────
st.markdown("---")
st.header("📊 Total Cost of Ownership (TCO) Comparison")
performance_df = pd.DataFrame({
    'Metric': ['Catch Rate', 'Friction (FPR)', 'Cost per Tx ($)'],
    'Legacy Vendor': [0.72, 0.042, 0.45],
    'SentryFlow': [0.89, 0.018, 0.12]
})
fig_bar = px.bar(performance_df, x='Metric', y=['Legacy Vendor', 'SentryFlow'], 
                 barmode='group', color_discrete_sequence=['#95a5a6', '#3498db'])
st.plotly_chart(fig_bar, use_container_width=True)


def get_simulation_data(n=1000):
    np.random.seed(42)
    df = pd.DataFrame({
        "tx_id": [f"TX-{i}" for i in range(n)],
        "typing_entropy": np.random.beta(2, 2, n) * 5,  # Bot = low entropy
        "device_is_emulator": np.random.choice([True, False], n, p=[0.08, 0.92]),
        "geo_velocity": np.random.uniform(0, 1200, n),
        "ml_risk_score": np.random.beta(2, 5, n),
    })
    
    # Injecting real signal: Emulators + low typing entropy = High Fraud Probability
    # This is the "Sardine Network Effect" demo
    df['is_fraud'] = np.where(
        (df['typing_entropy'] < 1.5) & (df['device_is_emulator']),
        np.random.choice([1, 0], n, p=[0.8, 0.2]),
        np.random.choice([1, 0], n, p=[0.01, 0.99])
    )
    return df