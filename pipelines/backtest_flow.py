from metaflow import FlowSpec, step, Parameter, current, project
import pandas as pd
import numpy as np
import json
from src.models.train import train_ensemble
from src.policies.evaluator import evaluate_policy

@project(name="sentryflow")
class SentryFlowBacktestFlow(FlowSpec):
    """
    SentryFlow Production Pipeline:
    Ingests data, trains the XGB+IsoForest ensemble, and executes a 
    Shadow Backtest against defined JsonLogic policies.
    """
    
    sample_size = Parameter('sample_size', default=5000, help="Number of transactions to simulate.")
    
    @step
    def start(self):
        """1. Ingest and Validate: Simulating the 'Sardine Global Signal' ingestion."""
        print(f"Starting SentryFlow Pipeline: {current.run_id}")
        
        # In a real scenario, this loads from Snowflake/Feature Store
        # Here we generate the DIBB-enhanced dataset
        np.random.seed(42)
        self.data = pd.DataFrame({
            "transaction_id": range(self.sample_size),
            "tx_type": np.random.choice(["WIRE_TRANSFER", "ACH", "CARD"], self.sample_size),
            "amount": np.random.uniform(10, 10000, self.sample_size),
            "device_is_emulator": np.random.choice([True, False], self.sample_size, p=[0.08, 0.92]),
            "geo_velocity": np.random.uniform(0, 1200, self.sample_size),
            "typing_entropy": np.random.uniform(0.5, 4.5, self.sample_size),
            "is_fraud": np.random.choice([1, 0], self.sample_size, p=[0.03, 0.97]) 
        })
        
        # Metadata for auditability
        self.policy_version = "v2026.03.shadow"
        self.next(self.train_ensemble_step)

    @step
    def train_ensemble_step(self):
        """2. Analytics Strength: Training Supervised (XGB) + Unsupervised (IsoForest)."""
        print("Training Risk Ensemble...")
        X = self.data[["amount", "geo_velocity", "typing_entropy", "device_is_emulator"]]
        y = self.data["is_fraud"]
        
        # Using the logic from src/models/train.py
        self.xgb_model, self.iso_forest = train_ensemble(X, y)
        self.next(self.backtest)

    @step
    def backtest(self):
        """3. Governance: Executing the Shadow Mode Backtest with ML Orchestration."""
        from src.policies.evaluator import batch_orchestrate

        print("Executing Shadow Backtest with Ensemble Orchestration...")

        # Define candidate policy
        candidate_rule = {
            "if": {"and": [{"==": [{"var": "device_is_emulator"}, True]}, {">": [{"var": "geo_velocity"}, 500]}]},
            "action": "REQUIRE_VIDEO_ID"
        }

        # Run Rule logic
        rule_results = self.data.apply(lambda r: evaluate_policy([candidate_rule], r.to_dict()), axis=1)
        rule_df = pd.DataFrame(list(rule_results))

        # Run ML scores
        X_features = self.data[["amount", "geo_velocity", "typing_entropy", "device_is_emulator"]]
        ml_scores = self.xgb_model.predict_proba(X_features)[:, 1]

        # THE FIX: Sync orchestration (matches API + Dashboard logic)
        orchestrated = batch_orchestrate(rule_df, pd.Series(ml_scores))

        # Save the Strategy as a searchable artifact
        self.data['strategy'] = orchestrated['strategy']
        self.data['final_decision'] = orchestrated['decision']

        # Metric Calculation on ORCHESTRATED results
        tp = len(self.data[(self.data['final_decision'] == 'BLOCK') & (self.data['is_fraud'] == 1)])
        fp = len(self.data[(self.data['final_decision'] == 'BLOCK') & (self.data['is_fraud'] == 0)])
        fn = len(self.data[(self.data['final_decision'] == 'PASS') & (self.data['is_fraud'] == 1)])

        self.precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        self.recall = tp / (tp + fn) if (tp + fn) > 0 else 0

        print(f"Backtest Results -> Precision: {self.precision:.2%}, Recall: {self.recall:.2%}, FPR: {1-self.precision:.2%}")

        self.next(self.approval_gate)

    @step
    def approval_gate(self):
        """4. Compliance: The 'Four-Eyes' Governance Check."""
        # In Metaflow, we can use a manual trigger or a condition
        # Senior TPM Move: We check if the FPR is within acceptable limits (<2%)
        self.is_approved = (1 - self.precision) < 0.02
        
        if self.is_approved:
            print("✅ Policy Passed Governance Thresholds. Ready for Promotion.")
        else:
            print("❌ Policy Failed Governance (High Friction). Review Required.")
            
        self.next(self.end)

    @step
    def end(self):
        """5. Conclusion: Pipeline Audit Log finalized."""
        print(f"SentryFlow Pipeline Complete. Run ID: {current.run_id}")

if __name__ == '__main__':
    SentryFlowBacktestFlow()