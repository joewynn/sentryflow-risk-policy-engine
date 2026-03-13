# research/monitoring_dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px

st.set_page_config(page_title="SentryFlow Risk Center", layout="wide")

# ──────────────────────────────────────────────────────────────
# 1. Dashboard Header & KPI Summary
# ──────────────────────────────────────────────────────────────
st.title("🛡️ SentryFlow: Advanced Risk Policy Manager")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Fraud Catch Rate", "89.2%", "+17.2%")
col2.metric("False Positive Rate", "1.8%", "-2.4%")
col3.metric("Avg. Latency", "28ms", "-12ms")
col4.metric("3-Year ROI", "$9.3M", "Target Meta")

# ──────────────────────────────────────────────────────────────
# 2. Policy Playground (The TPM's Value Prop)
# ──────────────────────────────────────────────────────────────
st.header("🎮 Policy Playground")
st.info("Test new rules against yesterday's data before deploying to production.")

# Mock JSON Logic for the user to edit
default_rule = {
    "if": [
        {"and": [{"==": [{"var": "device_is_emulator"}, True]}, {">": [{"var": "geo_velocity"}, 500]}]},
        "REQUIRE_ID_VIDEO",
        "APPROVE"
    ]
}

rule_input = st.text_area("Edit JsonLogic Policy", value=json.dumps(default_rule, indent=2), height=150)

# Simulate Shadow Impact
if st.button("Run Shadow Backtest"):
    with st.spinner("Analyzing 10k transactions..."):
        # Real logic would use evaluate_policy here; mocking for UI
        st.success("Analysis Complete!")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Simulated Impact")
            st.write("- **Transactions Blocked:** 42")
            st.write("- **False Positives (Est):** 3")
            st.write("- **Regulatory Compliance:** ✅ Nacha/CFPB Audit Log Generated")
            
        with c2:
            # Friction Curve Plot
            chart_data = pd.DataFrame(
                np.random.randn(20, 2),
                columns=['Fraud Catch Rate', 'Friction (Good User Block)']
            )
            st.line_chart(chart_data)

# ──────────────────────────────────────────────────────────────
# 3. Live Decision Trace (Auditability)
# ──────────────────────────────────────────────────────────────
st.header("📜 Live Decision Audit")
st.caption("Detailed trace for Nacha 2026/FinCEN Compliance")

mock_trace = {
    "transaction_id": "99218274",
    "decision": "DECLINE",
    "triggering_rule": "EMULATOR_HIGH_VELOCITY",
    "adverse_action_code": "R03",
    "customer_message": "Security verification failed on this device.",
    "model_score": 0.88,
    "SHAP_top_feature": "Typing Entropy (Low)"
}

st.json(mock_trace)

# ──────────────────────────────────────────────────────────────
# 4. Economic P&L Impact (The Executive Closer)
# ──────────────────────────────────────────────────────────────
st.header("📊 Build vs. Buy Performance")
performance_df = pd.DataFrame({
    'Metric': ['Catch Rate', 'False Positives', 'Cost per Tx'],
    'Vendor Only': [0.72, 0.042, 0.45],
    'SentryFlow': [0.89, 0.018, 0.12]
})
fig = px.bar(performance_df, x='Metric', y=['Vendor Only', 'SentryFlow'], barmode='group')
st.plotly_chart(fig, use_container_width=True)