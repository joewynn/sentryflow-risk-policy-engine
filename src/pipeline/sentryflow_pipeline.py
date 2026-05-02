from metaflow import FlowSpec, step, current
import pandas as pd
import numpy as np
import joblib
import os
from pathlib import Path

from src.models.train import train_ensemble, MODEL_DIR
from src.policies.evaluator import evaluate_policy, batch_orchestrate
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
)


class SentryFlowPipeline(FlowSpec):
    """
    Production deployment pipeline: load data → feature engineering → train/val split →
    train ensemble → backtest on held-out set → save model artifact.
    For AWS deployment, swap joblib.dump with SageMaker model registry upload.
    """

    @step
    def start(self):
        """1. Ingest: load IEEE-CIS dataset if available, else use synthetic DIBB data."""
        ieee_path = Path("data/ieee_train.parquet")
        if ieee_path.exists():
            print("Loading IEEE-CIS fraud dataset...")
            self.data = pd.read_parquet(ieee_path)
        else:
            print("WARNING: IEEE dataset not found. Using synthetic DIBB data (run 'make setup' for real data).")
            np.random.seed(42)
            n = 10_000
            self.data = pd.DataFrame({
                "transaction_id": range(n),
                "tx_type": np.random.choice(["WIRE_TRANSFER", "ACH", "CARD"], n),
                "amount": np.random.uniform(10, 10000, n),
                "device_is_emulator": np.random.choice([True, False], n, p=[0.08, 0.92]),
                "geo_velocity": np.random.uniform(0, 1200, n),
                "typing_entropy": np.random.uniform(0.5, 4.5, n),
                "is_fraud": np.random.choice([1, 0], n, p=[0.03, 0.97]),
            })
        self.next(self.feature_eng)

    @step
    def feature_eng(self):
        """2. Feature engineering: ensure DIBB columns present, cast types, drop nulls."""
        dibb_cols = ["device_is_emulator", "geo_velocity", "typing_entropy"]
        for col in dibb_cols:
            if col not in self.data.columns:
                # Simulate DIBB signal with realistic distributions when not present in raw data
                if col == "device_is_emulator":
                    self.data[col] = np.random.choice([True, False], len(self.data), p=[0.08, 0.92])
                elif col == "geo_velocity":
                    self.data[col] = np.random.uniform(0, 1200, len(self.data))
                elif col == "typing_entropy":
                    self.data[col] = np.random.uniform(0.5, 4.5, len(self.data))

        self.feature_cols = ["amount", "geo_velocity", "typing_entropy", "device_is_emulator"]

        # Validate required columns exist
        for col in self.feature_cols + ["is_fraud"]:
            if col not in self.data.columns:
                raise ValueError(f"Required column '{col}' missing from dataset after feature engineering")

        self.data = self.data.dropna(subset=self.feature_cols + ["is_fraud"])
        self.data["device_is_emulator"] = self.data["device_is_emulator"].astype(int)
        print(f"Feature engineering complete. {len(self.data)} rows, fraud rate: {self.data['is_fraud'].mean():.2%}")
        self.next(self.train_model)

    @step
    def train_model(self):
        """3. Train: temporal 80/20 split, fit XGBoost + Isolation Forest on training portion."""
        X = self.data[self.feature_cols]
        y = self.data["is_fraud"]

        split_idx = int(len(self.data) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        self.X_test = X_test
        self.y_test = y_test
        self.test_indices = X_test.index.tolist()

        print(f"Training on {len(X_train)} samples...")
        self.xgb_model, self.iso_forest = train_ensemble(X_train, y_train)
        self.next(self.backtest)

    @step
    def backtest(self):
        """4. Backtest: ensemble orchestration on held-out test set with full metric suite."""
        candidate_rule = {
            "if": {"and": [
                {"==": [{"var": "device_is_emulator"}, True]},
                {">": [{"var": "geo_velocity"}, 500]}
            ]},
            "action": "REQUIRE_VIDEO_ID"
        }

        test_data = self.data.loc[self.test_indices]
        rule_results = test_data.apply(
            lambda r: evaluate_policy([candidate_rule], r.to_dict()), axis=1
        )
        rule_df = pd.DataFrame(list(rule_results))
        ml_scores = pd.Series(
            self.xgb_model.predict_proba(self.X_test)[:, 1],
            index=self.X_test.index,
        )
        orchestrated = batch_orchestrate(rule_df, ml_scores)

        y_true = self.y_test.values
        y_pred = (orchestrated['decision'] == 'BLOCK').astype(int).values

        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        self.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        self.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        self.fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        self.f1 = float(f1_score(y_true, y_pred, zero_division=0))
        self.auprc = float(average_precision_score(y_true, ml_scores.values))
        self.is_approved = self.fpr < 0.02

        print(
            f"Backtest → Precision: {self.precision:.2%} | Recall: {self.recall:.2%} | "
            f"FPR: {self.fpr:.2%} | AUPRC: {self.auprc:.3f} | Approved: {self.is_approved}"
        )
        self.next(self.deploy)

    @step
    def deploy(self):
        """5. Deploy: save model artifact locally. In production, upload to SageMaker Model Registry."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        xgb_path = f"{MODEL_DIR}/xgb_fraud_v2026.joblib"
        iso_path = f"{MODEL_DIR}/iso_anomaly_v2026.joblib"
        joblib.dump(self.xgb_model, xgb_path)
        joblib.dump(self.iso_forest, iso_path)
        print(f"Model artifacts saved: {xgb_path}, {iso_path}")
        print(f"Final metrics — Precision: {self.precision:.2%} | Recall: {self.recall:.2%} | FPR: {self.fpr:.2%}")
        # Production: swap the above with sagemaker.deploy() or model registry upload
        self.next(self.end)

    @step
    def end(self):
        print(f"SentryFlow Pipeline complete. Run: {current.run_id} | Approved: {self.is_approved}")


if __name__ == '__main__':
    SentryFlowPipeline()
