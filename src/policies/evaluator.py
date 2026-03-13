import sys, os
import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import datetime, timezone

# PATH FIX
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.policies.evaluator import (
    evaluate_policy, 
    batch_orchestrate, 
    create_policy_signature
)

st.set_page_config(page_title="SentryFlow Risk Center", layout="wide", page_icon="🛡️")

# Simulation Data with DIBB Signals
def get_data(n=1000):
    np.random.seed(42)
    df = pd.DataFrame({
        "tx_id": [f"TX-{i}" for i in range(n)],
        "typing_entropy": np.random.beta(2, 2, n) * 5,
        "device_is_emulator": np.random.choice([True, False], n, p=[0.08, 0.92]),
        "geo_velocity": np.random.uniform(0, 1200, n),
        "ml_risk_score": np.random.beta(2, 5, n),
    })
    # Correlate DIBB: Low entropy + Emulator = High Fraud
    df['is_fraud'] = np.where((df['typing_entropy'] < 1.5) & (df['device_is_emulator']), 1, 0)
    return df

# ──────────────────────────────────────────────────────────────
# UI LAYOUT
# ──────────────────────────────────────────────────────────────
st.title("🛡️ SentryFlow: Risk Control Plane")

col_edit, col_govern = st.columns([2, 1])

with col_edit:
    st.subheader("Policy Editor")
    rule_input = st.text_area("JsonLogic", height=150, value=json.dumps({
        "if": {"and": [{"==": [{"var": "device_is_emulator"}, True]}, {">": [{"var": "geo_velocity"}, 500]}]},
        "action": "REQUIRE_VIDEO_ID"
    }, indent=2))

with col_govern:
    st.subheader("🏛️ Governance")
    try:
        current_rule = json.loads(rule_input)
        sig = create_policy_signature(current_rule, "v2026.03")
        st.caption(f"**Policy Signature:** `{sig[:16]}`")
    except: st.error("Invalid JSON")
    
    if st.button("Submit for 4-Eyes Review", use_container_width=True):
        st.success("Policy queued.")

# ──────────────────────────────────────────────────────────────
# THE BACKTEST EXECUTION (USING BATCH_ORCHESTRATE)
# ──────────────────────────────────────────────────────────────
if st.button("🚀 Run Vectorized Ensemble Backtest", type="primary", use_container_width=True):
    df = get_data(2000)
    
    # 1. Step 1: Run Rules (Vectorized-friendly apply)
    rule_results = df.apply(lambda r: evaluate_policy([current_rule], r.to_dict()), axis=1)
    rule_df = pd.DataFrame(list(rule_results))
    
    # 2. Step 2: Use the wired BATCH_ORCHESTRATE for speed
    final_df = batch_orchestrate(rule_df, df['ml_risk_score'])
    full_df = pd.concat([df, final_df], axis=1)

    # 3. Metrics
    m1, m2, m3 = st.columns(3)
    tp = int(((full_df['decision'] == 'BLOCK') & (full_df['is_fraud'] == 1)).sum())
    fp = int(((full_df['decision'] == 'BLOCK') & (full_df['is_fraud'] == 0)).sum())
    m1.metric("Fraud Caught", tp)
    m2.metric("False Positives", fp, delta_color="inverse")
    m3.metric("ML Overrides", int(full_df['strategy'].str.contains("ML").sum()))

    # 4. The Moat Visualization
    st.subheader("Analytics Moat: Rule vs. ML Intersection")
    fig = px.scatter(full_df, x="geo_velocity", y="ml_risk_score", color="decision", symbol="strategy",
                     category_orders={"strategy": ["RULE_LED", "ML_OVERRIDE_CRITICAL", "ML_ENHANCED_FRICTION"]},
                     color_discrete_map={"BLOCK": "#EF553B", "PASS": "#00CC96"})
    st.plotly_chart(fig, use_container_width=True)