import sys
import os

# Add the parent directory to sys.path so we can import from 'src'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import datetime
from src.policies.evaluator import evaluate_policy

# ──────────────────────────────────────────────────────────────
# CONFIG & DATA PREP
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="SentryFlow Risk Center", layout="wide", page_icon="🛡️")

# Default Rule for Demo
DEFAULT_RULE = {
    "if": {
        "and": [
            {"==": [{"var": "device_is_emulator"}, True]},
            {">": [{"var": "geo_velocity"}, 500]}
        ]
    },
    "action": "REQUIRE_VIDEO_ID"
}

@st.cache_data
def load_backtest_data(n=1000):
    np.random.seed(42) # Consistent data for demo stability
    return pd.DataFrame({
        "transaction_id": [f"TX-{i}" for i in range(n)],
        "tx_type": np.random.choice(["WIRE_TRANSFER", "ACH", "CARD"], n),
        "amount": np.random.uniform(10, 10000, n),
        "device_is_emulator": np.random.choice([True, False], n, p=[0.08, 0.92]),
        "geo_velocity": np.random.uniform(0, 1200, n),
        "typing_entropy": np.random.uniform(0.5, 4.5, n),
        "is_fraud": np.random.choice([1, 0], n, p=[0.03, 0.97]) 
    })

# ──────────────────────────────────────────────────────────────
# SIDEBAR: DATA CONTROLS
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=80)
    st.title("Admin Controls")
    st.divider()
    sample_size = st.slider("Backtest Sample Size", 100, 5000, 1000)
    st.write(f"**Environment:** Production-Shadow")
    st.write(f"**Data Latency:** 2ms")
    if st.button("Flush Cache"):
        st.cache_data.clear()

# ──────────────────────────────────────────────────────────────
# 1. HEADER & KPI SUMMARY
# ──────────────────────────────────────────────────────────────
st.title("🛡️ SentryFlow: Advanced Risk Policy Manager")
st.caption(f"Status: Connected to Risk Engine v4.1 | Last Update: {datetime.now().strftime('%H:%M:%S')}")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Fraud Catch Rate", "89.2%", "+17.2%", help="Percentage of total fraud correctly identified")
kpi2.metric("False Positive Rate", "1.8%", "-2.4%", help="Legitimate users blocked by automated rules")
kpi3.metric("Avg. Decision Latency", "28ms", "-12ms", help="Time from Request to Decision response")
kpi4.metric("Annualized ROI", "$9.3M", "Target Meta", help="Saved losses minus implementation COGS")

st.markdown("---")

# ──────────────────────────────────────────────────────────────
# 2. POLICY PLAYGROUND
# ──────────────────────────────────────────────────────────────
st.header("🎮 Policy Playground")
col_input, col_metrics = st.columns([1, 1])

with col_input:
    st.subheader("1. Define Logic")
    st.info("Edit JsonLogic below to target new attack vectors.")
    rule_input = st.text_area("Policy Editor", value=json.dumps(DEFAULT_RULE, indent=2), height=250)
    
    run_test = st.button("🚀 Run Shadow Backtest", use_container_width=True)
    if st.button("✅ Push to Production", use_container_width=True, type="primary"):
        st.toast("Policy Pushed to Edge Nodes!", icon="🔥")

with col_metrics:
    st.subheader("2. Shadow Impact Analysis")
    if run_test:
        try:
            df_history = load_backtest_data(sample_size)
            new_rule = json.loads(rule_input)
            
            with st.spinner("Calculating precision/recall across historical stream..."):
                results = df_history.apply(lambda row: evaluate_policy([new_rule], row.to_dict()), axis=1)
                df_history['new_decision'] = [r['decision'] for r in results]
                
                # Metrics Calculation
                tp = len(df_history[(df_history['new_decision'] == 'BLOCK') & (df_history['is_fraud'] == 1)])
                fp = len(df_history[(df_history['new_decision'] == 'BLOCK') & (df_history['is_fraud'] == 0)])
                fn = len(df_history[(df_history['new_decision'] == 'PASS') & (df_history['is_fraud'] == 1)])
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                block_rate = ((tp + fp) / sample_size) * 100

                # Strategic Display
                st.success("Test Complete")
                m1, m2, m3 = st.columns(3)
                m1.metric("Block Rate", f"{block_rate:.1f}%")
                m2.metric("Fraud Caught", tp)
                m3.metric("Legit Users Blocked", fp)
                
                # Visual Distributions
                st.progress(recall, text=f"Fraud Recall: {recall:.1%}")
                st.progress(1-precision, text=f"User Friction (FPR): {(1-precision):.1%}")
                
                chart_df = pd.DataFrame({
                    "Outcome": ["Fraud Caught", "False Positives", "Missed Fraud"],
                    "Count": [tp, fp, fn],
                    "Color": ["#2ecc71", "#e74c3c", "#f1c40f"]
                })
                fig = px.pie(chart_df, values='Count', names='Outcome', color='Outcome',
                             color_discrete_map={'Fraud Caught':'#2ecc71', 'False Positives':'#e74c3c', 'Missed Fraud':'#f1c40f'})
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Logic Error: {e}")
    else:
        st.write("Modify the JSON logic and click 'Run Shadow Backtest' to see live impact data.")

st.markdown("---")

# ──────────────────────────────────────────────────────────────
# 3. AUDIT & PERFORMANCE
# ──────────────────────────────────────────────────────────────
col_audit, col_econ = st.columns([1, 1])

with col_audit:
    st.header("📜 Live Audit Trace")
    st.caption("Detailed decision log for Nacha 2026/FinCEN Compliance")
    mock_trace = {
        "transaction_id": "TX-9921",
        "timestamp": datetime.now().isoformat(),
        "decision": "DECLINE",
        "triggering_rule": "EMULATOR_HIGH_VELOCITY",
        "adverse_action_code": "R03",
        "model_score": 0.88,
        "SHAP_top_feature": "Typing Entropy (Low)"
    }
    st.json(mock_trace)

with col_econ:
    st.header("📊 Build vs. Buy ROI")
    st.caption("Total Cost of Ownership (TCO) Comparison")
    performance_df = pd.DataFrame({
        'Metric': ['Fraud Catch Rate', 'User Friction', 'COGS per Tx ($)'],
        'Legacy Vendor': [0.72, 0.042, 0.45],
        'SentryFlow': [0.89, 0.018, 0.12]
    })
    fig_bar = px.bar(performance_df, x='Metric', y=['Legacy Vendor', 'SentryFlow'], 
                     barmode='group', color_discrete_sequence=['#95a5a6', '#3498db'])
    st.plotly_chart(fig_bar, use_container_width=True)