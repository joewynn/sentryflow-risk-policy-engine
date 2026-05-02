import os
import warnings
from metaflow import FlowSpec, step, Parameter, current, project
import pandas as pd
import numpy as np
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
)
import json
from src.models.train import train_ensemble, FEATURE_COLS
from src.policies.evaluator import evaluate_policy, batch_orchestrate


def _engineer_dibb_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map IEEE-CIS columns → DIBB feature schema used by the API and models.

    This function is the single source of truth for feature derivation.
    It mirrors the logic in research/eda_ieee_fraud.ipynb (Cell 7-8).
    Any change here must be reflected in the notebook and vice versa.

    Real data MI scores (from IEEE-CIS EDA):
    - amount: 0.0279 (STRONG)
    - typing_entropy: 0.0148 (GOOD)
    - card_count: 0.0078 (USEFUL)
    - geo_velocity: 0.0065 (WEAK but ok)
    - days_since_last_tx: 0.0058 (WEAK but ok)
    - device_is_emulator: 0.0001 (VERY WEAK — kept for backward compat)
    """
    df = df.copy()

    # amount — direct mapping
    df["amount"] = df["TransactionAmt"]

    # device_is_emulator — mobile device + suspicious browser string → bot/emulator proxy
    # NOTE: Very weak discriminator in real data (MI=0.0001), but kept for API backward compat
    if "DeviceType" in df.columns and "id_31" in df.columns:
        is_mobile = df["DeviceType"] == "mobile"
        is_suspicious_browser = df["id_31"].str.lower().str.contains(
            "mobile browser|webview|unknown", na=False
        )
        df["device_is_emulator"] = (is_mobile & is_suspicious_browser).astype(int)
    elif "DeviceType" in df.columns:
        df["device_is_emulator"] = (df["DeviceType"] == "mobile").astype(int)
    else:
        warnings.warn("DeviceType not found — device_is_emulator set to 0")
        df["device_is_emulator"] = 0

    # geo_velocity — dist1 (billing/shipping distance, miles) / D1 (days since last tx)
    # Higher ratio = farther distance in shorter time = more suspicious
    # MI=0.0065; inverse signal (fraud mean=82, legit mean=109)
    if "dist1" in df.columns and "D1" in df.columns:
        df["geo_velocity"] = (
            df["dist1"].fillna(0) / df["D1"].clip(lower=1 / 24).fillna(1)
        ).clip(upper=5000)
    elif "dist1" in df.columns:
        df["geo_velocity"] = df["dist1"].fillna(0).clip(upper=5000)
    else:
        warnings.warn("dist1 not found — geo_velocity set to 0")
        df["geo_velocity"] = 0.0

    # typing_entropy — C1 (# cards on billing address) normalized to [0, 6]
    # More associated cards = higher anomaly risk. MI=0.0148 (good signal)
    # Fraud mean=1.63 (normalized), legit mean=0.92
    if "C1" in df.columns:
        df["typing_entropy"] = (df["C1"].clip(upper=20) / 20 * 6).fillna(3.0)
    else:
        warnings.warn("C1 not found — typing_entropy set to 3.0 (neutral)")
        df["typing_entropy"] = 3.0

    # card_count — C1 raw (number of cards on billing address)
    # MI=0.0078; fraud mean=35.5, legit mean=13.3
    # Stronger signal than normalized version for tree-based models
    if "C1" in df.columns:
        df["card_count"] = df["C1"].fillna(0).clip(upper=50)
    else:
        warnings.warn("C1 not found — card_count set to 0")
        df["card_count"] = 0.0

    # days_since_last_tx — D1 (days since last transaction on card)
    # MI=0.0058; INVERSE signal: fraud mean=38 days, legit mean=96 days
    # Lower D1 = more recent activity = riskier. Model learns inverse relationship.
    if "D1" in df.columns:
        df["days_since_last_tx"] = df["D1"].fillna(df["D1"].median()).clip(upper=365)
    else:
        warnings.warn("D1 not found — days_since_last_tx set to 30 (neutral)")
        df["days_since_last_tx"] = 30.0

    return df


@project(name="sentryflow")
class SentryFlowBacktestFlow(FlowSpec):
    """
    SentryFlow Production Pipeline:
    Ingest → temporal train/test split → train ensemble → shadow backtest on held-out test set.
    All metrics are computed on the held-out set to prevent data leakage.
    """

    sample_size = Parameter('sample_size', default=5000, help="Number of transactions to simulate (synthetic fallback only).")

    @step
    def start(self):
        """1. Ingest: load IEEE-CIS data if available, else generate synthetic fallback."""
        print(f"Starting SentryFlow Pipeline: {current.run_id}")

        tx_path = "data/train_transaction.csv"
        id_path = "data/train_identity.csv"

        if os.path.exists(tx_path):
            print("Loading IEEE-CIS Fraud Detection dataset...")
            tx = pd.read_csv(tx_path)
            id_ = pd.read_csv(id_path) if os.path.exists(id_path) else pd.DataFrame()

            if not id_.empty:
                df = tx.merge(id_, on="TransactionID", how="left")
                print(f"  Loaded {len(tx):,} transactions, {len(id_):,} identity rows")
                print(f"  Identity match rate: {len(id_) / len(tx):.1%}")
            else:
                df = tx
                warnings.warn("train_identity.csv not found — identity features unavailable")

            df = _engineer_dibb_features(df)
            required_cols = FEATURE_COLS + ["TransactionDT", "isFraud"]
            df = df[required_cols].rename(columns={"isFraud": "is_fraud"})
            df = df.dropna(subset=FEATURE_COLS)
            df["transaction_id"] = df.index.astype(str)
            df["tx_type"] = "CARD"

            # Sort by TransactionDT before splitting — required for temporal validity
            df = df.sort_values("TransactionDT").reset_index(drop=True)
            self.data = df
            self.policy_version = "v2026.05.ieee"
            print(f"  Final dataset: {len(df):,} rows. Fraud rate: {df['is_fraud'].mean():.3%}")
        else:
            warnings.warn(
                "IEEE-CIS data not found at data/train_transaction.csv. "
                "Falling back to synthetic DIBB generator. "
                "Run 'make setup' to download real data."
            )
            np.random.seed(42)
            self.data = pd.DataFrame({
                "transaction_id": range(self.sample_size),
                "tx_type": np.random.choice(["WIRE_TRANSFER", "ACH", "CARD"], self.sample_size),
                "amount": np.random.uniform(10, 10000, self.sample_size),
                "device_is_emulator": np.random.choice([True, False], self.sample_size, p=[0.08, 0.92]),
                "geo_velocity": np.random.uniform(0, 1200, self.sample_size),
                "typing_entropy": np.random.uniform(0.5, 4.5, self.sample_size),
                "is_fraud": np.random.choice([1, 0], self.sample_size, p=[0.03, 0.97]),
                "TransactionDT": range(self.sample_size),
            })
            self.policy_version = "v2026.05.synthetic"

        self.next(self.train_ensemble_step)

    @step
    def train_ensemble_step(self):
        """2. Train: temporal 80/20 split, then fit XGB + IsoForest on training portion only."""
        print("Training Risk Ensemble on 80% of data (temporal split)...")

        X = self.data[FEATURE_COLS]
        y = self.data["is_fraud"]

        # Temporal split: first 80% for training, last 20% for holdout evaluation
        # Data is already sorted by TransactionDT in the start step
        split_idx = int(len(self.data) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        self.X_test = X_test
        self.y_test = y_test
        self.test_indices = X_test.index.tolist()

        self.xgb_model, self.iso_forest = train_ensemble(X_train, y_train)
        print(f"Trained on {len(X_train):,} samples, evaluating on {len(X_test):,} held-out samples.")
        self.next(self.backtest)

    @step
    def backtest(self):
        """3. Backtest: run ensemble orchestration on held-out test set only."""
        print("Executing Shadow Backtest on held-out test set...")

        candidate_rule = {
            "if": {"and": [
                {"==": [{"var": "device_is_emulator"}, True]},
                {">": [{"var": "geo_velocity"}, 500]}
            ]},
            "action": "REQUIRE_VIDEO_ID"
        }

        test_data = self.data.loc[self.test_indices]

        # Rule evaluation on test rows
        rule_results = test_data.apply(
            lambda r: evaluate_policy([candidate_rule], r.to_dict()), axis=1
        )
        # Extract only the columns needed for orchestration (skip nested 'audit' dict)
        rule_df = pd.DataFrame({
            'decision': rule_results.apply(lambda x: x['decision']),
            'action': rule_results.apply(lambda x: x['action']),
            'adverse_action_code': rule_results.apply(lambda x: x['adverse_action_code']),
        })

        # ML scores on test rows
        ml_scores = pd.Series(
            self.xgb_model.predict_proba(self.X_test)[:, 1],
            index=self.X_test.index,
        )

        # Ensemble orchestration (same logic as API + dashboard)
        orchestrated = batch_orchestrate(rule_df, ml_scores)

        test_data = test_data.copy()
        test_data['strategy'] = orchestrated['strategy'].values
        test_data['final_decision'] = orchestrated['decision'].values
        self.test_data = test_data

        # --- Correct metric computation ---
        y_true = self.y_test.values
        y_pred = (orchestrated['decision'] == 'BLOCK').astype(int).values
        ml_scores_arr = ml_scores.values

        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

        self.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        self.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        self.fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0  # FPR = FP / (FP + TN)
        self.f1 = float(f1_score(y_true, y_pred, zero_division=0))
        self.auprc = float(average_precision_score(y_true, ml_scores_arr))
        self.auroc = float(roc_auc_score(y_true, ml_scores_arr))

        strategy_counts = orchestrated['strategy'].value_counts().to_dict()
        self.ml_override_count = strategy_counts.get('ML_OVERRIDE_CRITICAL', 0)
        self.ml_friction_count = strategy_counts.get('ML_ENHANCED_FRICTION', 0)

        # --- Isolation Forest evaluation ---
        iso_preds = self.iso_forest.predict(self.X_test)  # -1=anomaly, 1=normal
        iso_binary = (iso_preds == -1).astype(int)
        self.iso_recall = float(recall_score(y_true, iso_binary, zero_division=0))
        self.iso_precision = float(precision_score(y_true, iso_binary, zero_division=0))

        print(
            f"XGB Ensemble  → Precision: {self.precision:.2%} | Recall: {self.recall:.2%} | "
            f"FPR: {self.fpr:.2%} | F1: {self.f1:.3f} | AUPRC: {self.auprc:.3f} | AUROC: {self.auroc:.3f}"
        )
        print(
            f"Isolation Forest → Recall: {self.iso_recall:.2%} | Precision: {self.iso_precision:.2%}"
        )
        print(
            f"Strategy Breakdown → ML_OVERRIDE: {self.ml_override_count} | "
            f"ML_FRICTION: {self.ml_friction_count} | RULE_LED: {strategy_counts.get('RULE_LED', 0)}"
        )

        self.next(self.approval_gate)

    @step
    def approval_gate(self):
        """4. Governance: four-eyes check — FPR must be < 2% for promotion."""
        self.is_approved = self.fpr < 0.02

        if self.is_approved:
            print(f"Policy passed governance (FPR={self.fpr:.2%} < 2%). Ready for promotion.")
        else:
            print(f"Policy failed governance (FPR={self.fpr:.2%} >= 2%). Review required.")
            print("Tune ML_CRITICAL_THRESHOLD / ML_FRICTION_THRESHOLD in src/policies/evaluator.py")

        self.next(self.end)

    @step
    def end(self):
        """5. Audit log finalized."""
        print(f"SentryFlow Pipeline Complete. Run ID: {current.run_id}")
        print(json.dumps({
            "run_id": current.run_id,
            "policy_version": self.policy_version,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "fpr": round(self.fpr, 4),
            "f1": round(self.f1, 4),
            "auprc": round(self.auprc, 4),
            "auroc": round(self.auroc, 4),
            "iso_recall": round(self.iso_recall, 4),
            "ml_override_count": int(self.ml_override_count),
            "approved": bool(self.is_approved),
        }, indent=2))


if __name__ == '__main__':
    SentryFlowBacktestFlow()
