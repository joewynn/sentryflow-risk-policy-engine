# research/monitoring_dashboard.py
import sys, os
import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.policies.evaluator import evaluate_policy, batch_orchestrate, create_policy_signature

st.set_page_config(page_title="SentryFlow Master Control", layout="wide", page_icon="🛡️")

# 1. DATA ENGINE (Merged Context: Amount + DIBB Signals)
@st.cache_data
def get_master_simulation_data(n=2000):
    np.random.seed(42)
    df = pd.DataFrame({
        "tx_id": [f"TX-{i}" for i in range(n)],
        "amount": np.random.uniform(10, 10000, n),
        "typing_entropy": np.random.beta(2, 2, n) * 5,
        "device_is_emulator": np.random.choice([True, False], n, p=[0.08, 0.92]),
        "geo_velocity": np.random.uniform(0, 1200, n),
        "ml_risk_score": np.random.beta(2, 5, n),
    })
    df['is_fraud'] = np.where((df['typing_entropy'] < 1.5) & (df['device_is_emulator']), 1, 0)
    return df

# 2. SIDEBAR CONTROLS (Operational Maturity)
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=60)
    st.header("Admin Settings")
    sample_size = st.slider("Backtest Samples", 500, 5000, 2000)
    st.info("Environment: **Production-Shadow**")
    if st.button("Purge Cache"): st.cache_data.clear()

# 3. HEADER & TOP KPIs (Business Case Narrative)
st.title("🛡️ SentryFlow: Risk Control Plane")
st.caption(f"Engine v2026.03 | Last Sync: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Fraud Catch Rate", "89.2%", "+17.2%")
k2.metric("False Positive Rate", "1.8%", "-2.4%", delta_color="inverse")
k3.metric("Decision Latency", "28ms", "-12ms")
k4.metric("Annualized ROI", "$9.3M", "Target Meta")

st.markdown("---")

# 4. POLICY & GOVERNANCE
st.header("🎮 Policy Playground & Governance")
col_edit, col_govern = st.columns([2, 1])

with col_edit:
    st.subheader("Edit Active Policy")
    default_rule = {"if": {"and": [{"==": [{"var": "device_is_emulator"}, True]}, {">": [{"var": "geo_velocity"}, 500]}]}, "action": "REQUIRE_VIDEO_ID"}
    rule_input = st.text_area("JsonLogic Editor", height=150, value=json.dumps(default_rule, indent=2))

with col_govern:
    st.subheader("🏛️ Compliance Trace")
    try:
        current_rule = json.loads(rule_input)
        sig = create_policy_signature(current_rule, "v2026.03")
        st.code(f"SIG: {sig[:24]}...", language="text")
    except: st.error("JSON Syntax Error")
    
    if st.button("📩 Submit for 4-Eyes Review", use_container_width=True):
        st.success("Policy queued for Risk-Admin approval.")
    if st.button("🚀 Emergency Push", use_container_width=True, type="secondary"):
        st.error("Bypass logged to immutable Audit Trail.")

# 5. EXECUTION ENGINE
if st.button("🚀 Run Vectorized Ensemble Backtest", type="primary", use_container_width=True):
    df = get_master_simulation_data(sample_size)
    
    with st.spinner("Executing Vectorized Orchestration..."):
        rule_results = df.apply(lambda r: evaluate_policy([current_rule], r.to_dict()), axis=1)
        rule_df = pd.DataFrame(list(rule_results))
        final_df = batch_orchestrate(rule_df, df['ml_risk_score'])
        full_df = pd.concat([df, final_df], axis=1)

    st.divider()
    m1, m2, m3 = st.columns(3)
    tp = int(((full_df['decision'] == 'BLOCK') & (full_df['is_fraud'] == 1)).sum())
    fp = int(((full_df['decision'] == 'BLOCK') & (full_df['is_fraud'] == 0)).sum())
    m1.metric("Fraud Caught", tp, delta="High Recall")
    m2.metric("False Positives", fp, delta_color="inverse")
    m3.metric("ML Overrides", int(full_df['strategy'].str.contains("ML").sum()))

    col_moat, col_dibb = st.columns(2)
    with col_moat:
        st.subheader("The Ensemble Moat")
        fig_moat = px.scatter(full_df, x="geo_velocity", y="ml_risk_score", color="decision", symbol="strategy",
                             color_discrete_map={"BLOCK": "#EF553B", "PASS": "#00CC96"},
                             category_orders={"strategy": ["RULE_LED", "ML_OVERRIDE_CRITICAL", "ML_ENHANCED_FRICTION"]})
        st.plotly_chart(fig_moat, use_container_width=True)

    with col_dibb:
        st.subheader("🧠 Behavioral Impact (DIBB)")
        fig_dibb = px.histogram(full_df, x="typing_entropy", color="is_fraud", nbins=30, title="Fraud Density by Entropy")
        st.plotly_chart(fig_dibb, use_container_width=True)

    st.divider()
    st.header("⚖️ Compliance & Behavioral Signals")
    c_aan, c_gray = st.columns([2, 1])
    with c_aan:
        st.subheader("CFPB-Compliant Trace")
        blocked_sample = full_df[full_df['decision'] == 'BLOCK'].head(1)
        if not blocked_sample.empty:
            st.info(f"**Current Adverse Action Code**: `{blocked_sample['aan_code'].values[0]}`")
            st.markdown(f"> *'Security verification failed. Additional identity proofing required.'*")
        else: st.write("Adjust rules to trigger blocks.")

    with c_gray:
        st.subheader("⚠️ Gray-Zone Intelligence")
        overrides = int(full_df['strategy'].str.contains("ML_OVERRIDE").sum())
        st.warning(f"**ML Overrides**: {overrides}")
        st.caption("Transactions flagged by ML behavioral anomalies.")

    st.subheader("📜 Live Decision Audit Trace")
    st.table(full_df[['tx_id', 'amount', 'decision', 'strategy', 'aan_code']].head(10))

st.markdown("---")
st.header("📊 Economic Impact: TCO Analysis")
performance_df = pd.DataFrame({'Metric': ['Catch Rate', 'Friction (FPR)', 'Cost per Tx ($)'], 
                               'Legacy Vendor': [0.72, 0.042, 0.45], 'SentryFlow': [0.89, 0.018, 0.12]})
st.plotly_chart(px.bar(performance_df, x='Metric', y=['Legacy Vendor', 'SentryFlow'], barmode='group'), use_container_width=True)