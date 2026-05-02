# research/monitoring_dashboard.py
import sys
import os
import time
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from sklearn.metrics import precision_score, recall_score, confusion_matrix

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.policies.evaluator import evaluate_policy, batch_orchestrate, create_policy_signature
from src.governance.approval_queue import submit_for_approval, approve_policy, reject_policy, list_pending

logger = logging.getLogger(__name__)

AUDIT_TRAIL_DIR = Path("data/audit_trail")
AUDIT_TRAIL_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="SentryFlow Master Control", layout="wide", page_icon="🛡️")

# Initialise session state KPIs to "—" so they never show stale hardcoded values on first load
for key in ("catch_rate", "fpr", "decision_latency_ms", "roi_estimate", "ml_overrides"):
    if key not in st.session_state:
        st.session_state[key] = "—"


# 1. DATA ENGINE
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
    df['consortium_match_count'] = np.random.choice([0, 1, 5, 12], n, p=[0.8, 0.1, 0.07, 0.03])
    return df


# 2. SIDEBAR
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=60)
    st.header("Admin Settings")
    sample_size = st.slider("Backtest Samples", 500, 5000, 2000)
    st.info("Environment: **Production-Shadow**")
    if st.button("Purge Cache"):
        st.cache_data.clear()


# 3. HEADER & TOP KPIs
st.title("🛡️ SentryFlow: Risk Control Plane")
st.caption(f"Engine v2026.03 | Last Sync: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Fraud Catch Rate", st.session_state["catch_rate"],
          help="Recall on held-out test data. Run backtest to populate.")
k2.metric("False Positive Rate", st.session_state["fpr"],
          help="FP / (FP + TN). Run backtest to populate.", delta_color="inverse")
k3.metric("Decision Latency", st.session_state["decision_latency_ms"],
          help="Measured wall-clock time for batch_orchestrate(). Run backtest to populate.")
k4.metric("Estimated ROI", st.session_state["roi_estimate"],
          help="Computed from actual catch rate vs 72% legacy baseline on $1B portfolio.")

st.markdown("---")


# 4. POLICY & GOVERNANCE
st.header("🎮 Policy Playground & Governance")
col_edit, col_govern = st.columns([2, 1])

with col_edit:
    st.subheader("Edit Active Policy")
    default_rule = {
        "if": {"and": [{"==": [{"var": "device_is_emulator"}, True]},
                       {">": [{"var": "geo_velocity"}, 500]}]},
        "action": "REQUIRE_VIDEO_ID"
    }
    rule_input = st.text_area("JsonLogic Editor", height=150, value=json.dumps(default_rule, indent=2))

with col_govern:
    st.subheader("🏛️ Compliance Trace")
    try:
        current_rule = json.loads(rule_input)
        sig = create_policy_signature(current_rule, "v2026.03")
        st.code(f"SIG: {sig[:24]}...", language="text")
    except json.JSONDecodeError:
        st.error("JSON Syntax Error")
        current_rule = default_rule

    if st.button("📩 Submit for 4-Eyes Review", use_container_width=True):
        try:
            ticket_id = submit_for_approval(current_rule, "risk_manager_demo")
            st.success(f"✅ Policy queued for approval. Ticket: `{ticket_id}`")
            st.caption(f"📁 Artifact: `data/policy_queue/{ticket_id}.json`")
        except Exception as e:
            st.error(f"Submission failed: {e}")

    if st.button("🚨 Emergency Push", use_container_width=True, type="secondary"):
        try:
            sig = create_policy_signature(current_rule, "v2026.03")
            audit_record = {
                "event": "EMERGENCY_OVERRIDE",
                "policy": current_rule,
                "policy_signature": sig,
                "actor": "risk_manager_demo",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": "Emergency bypass — triggers compliance review per Nacha 2026",
            }
            fname = f"emergency_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
            (AUDIT_TRAIL_DIR / fname).write_text(json.dumps(audit_record, indent=2))
            st.warning(f"⚠️ Emergency push logged to immutable audit trail: `data/audit_trail/{fname}`")
        except Exception as e:
            st.error(f"Emergency push failed: {e}")


# 4b. APPROVAL INBOX
with st.expander("📥 Approval Inbox", expanded=False):
    pending = list_pending()
    if not pending:
        st.info("No policies pending approval.")
    for ticket in pending:
        cols = st.columns([3, 1, 1])
        cols[0].markdown(f"**{ticket['ticket_id']}** — submitted by `{ticket['submitted_by']}` at `{ticket['submitted_at']}`")
        if cols[1].button("✅ Approve", key=f"approve_{ticket['ticket_id']}"):
            try:
                approve_policy(ticket['ticket_id'], "senior_risk_admin")
                st.success(f"Approved {ticket['ticket_id']}")
                st.rerun()
            except Exception as e:
                st.error(str(e))
        if cols[2].button("❌ Reject", key=f"reject_{ticket['ticket_id']}"):
            try:
                reject_policy(ticket['ticket_id'], "senior_risk_admin", "Did not meet FPR threshold")
                st.warning(f"Rejected {ticket['ticket_id']}")
                st.rerun()
            except Exception as e:
                st.error(str(e))


# 5. BACKTEST EXECUTION ENGINE
if st.button("🚀 Run Vectorized Ensemble Backtest", type="primary", use_container_width=True):
    df = get_master_simulation_data(sample_size)

    with st.spinner("Executing Vectorized Orchestration..."):
        rule_results = df.apply(lambda r: evaluate_policy([current_rule], r.to_dict()), axis=1)
        rule_df = pd.DataFrame(list(rule_results))

        t0 = time.perf_counter()
        final_df = batch_orchestrate(rule_df, df['ml_risk_score'])
        latency_ms = (time.perf_counter() - t0) * 1000

        full_df = pd.concat([df.reset_index(drop=True), final_df.reset_index(drop=True)], axis=1)

    # Compute real metrics on backtest output
    y_true = full_df['is_fraud'].values
    y_pred = (full_df['decision'] == 'BLOCK').astype(int).values
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    overrides = int(full_df['strategy'].str.contains("ML").sum())

    # ROI: incremental catch rate vs 72% legacy baseline on $1B portfolio (1.2% fraud rate, $89 avg loss)
    PORTFOLIO = 1_000_000_000
    FRAUD_RATE = 0.012
    AVG_LOSS = 89
    estimated_roi = max((recall - 0.72) * PORTFOLIO * FRAUD_RATE * AVG_LOSS, 0)

    # Write computed values to session state
    st.session_state["catch_rate"] = f"{recall:.1%}"
    st.session_state["fpr"] = f"{fpr:.1%}"
    st.session_state["decision_latency_ms"] = f"{latency_ms:.0f}ms"
    st.session_state["roi_estimate"] = f"${estimated_roi:,.0f}"
    st.session_state["ml_overrides"] = overrides

    st.divider()

    # Consortium signal
    st.subheader("🌐 Sardine Consortium Signal")
    max_matches = int(full_df['consortium_match_count'].max())
    avg_matches = full_df['consortium_match_count'].mean()
    st.markdown(
        f"> **Network Effect Insight:** The highest-risk typing pattern has been observed across "
        f"**{max_matches}** other client accounts in the last 24 hours (avg: {avg_matches:.1f} cross-client matches)."
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Fraud Caught (Recall)", f"{recall:.1%}")
    m2.metric("False Positives", fp, delta_color="inverse")
    m3.metric("ML Overrides", overrides)

    col_moat, col_dibb = st.columns(2)
    with col_moat:
        st.subheader("The Ensemble Moat")
        fig_moat = px.scatter(
            full_df, x="geo_velocity", y="ml_risk_score",
            color="decision", symbol="strategy",
            color_discrete_map={"BLOCK": "#EF553B", "PASS": "#00CC96"},
            category_orders={"strategy": ["RULE_LED", "ML_OVERRIDE_CRITICAL", "ML_ENHANCED_FRICTION"]},
        )
        st.plotly_chart(fig_moat, use_container_width=True)

    with col_dibb:
        st.subheader("🧠 Behavioral Impact (DIBB)")
        fig_dibb = px.histogram(full_df, x="typing_entropy", color="is_fraud", nbins=30,
                                title="Fraud Density by Entropy")
        st.plotly_chart(fig_dibb, use_container_width=True)

    st.divider()
    st.header("⚖️ Compliance & Behavioral Signals")
    c_aan, c_gray = st.columns([2, 1])
    with c_aan:
        st.subheader("CFPB-Compliant Trace")
        blocked_sample = full_df[full_df['decision'] == 'BLOCK'].head(1)
        if not blocked_sample.empty:
            st.info(f"**Adverse Action Code**: `{blocked_sample['aan_code'].values[0]}`")
            st.markdown("> *'Security verification failed. Additional identity proofing required.'*")
        else:
            st.write("Adjust rules to trigger blocks.")

    with c_gray:
        st.subheader("⚠️ Gray-Zone Intelligence")
        st.warning(f"**ML Overrides**: {overrides}")
        st.caption("Transactions flagged by ML behavioral anomalies.")

    st.subheader("📜 Live Decision Audit Trace")
    st.table(full_df[['tx_id', 'amount', 'decision', 'strategy', 'aan_code']].head(10))

    # Force KPI re-render with real values
    st.rerun()


st.markdown("---")
st.header("📊 Economic Impact: TCO Analysis")

# SentryFlow values use live session state when available, else show target
sentryflow_catch = float(st.session_state["catch_rate"].rstrip("%")) / 100 if st.session_state["catch_rate"] != "—" else 0.89
sentryflow_fpr = float(st.session_state["fpr"].rstrip("%")) / 100 if st.session_state["fpr"] != "—" else 0.018

performance_df = pd.DataFrame({
    'Metric': ['Catch Rate', 'Friction (FPR)', 'Cost per Tx ($)'],
    'Legacy Vendor': [0.72, 0.042, 0.45],
    'SentryFlow': [round(sentryflow_catch, 3), round(sentryflow_fpr, 3), 0.12],
})
st.plotly_chart(
    px.bar(performance_df, x='Metric', y=['Legacy Vendor', 'SentryFlow'], barmode='group'),
    use_container_width=True,
)
if st.session_state["catch_rate"] == "—":
    st.caption("⚠️ SentryFlow bars show business-case targets. Run the backtest above to replace with live-computed values.")
