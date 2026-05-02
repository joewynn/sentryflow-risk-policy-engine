#!/usr/bin/env python
"""
Analyze precision-recall curve and find optimal threshold for target recall @ FPR < 2%.
Run after a backtest pipeline execution to extract and analyze ML scores.
"""
import os
import sys
import pickle
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, roc_curve
from pathlib import Path

PYTHONPATH = Path(__file__).parent
sys.path.insert(0, str(PYTHONPATH))

# Load the test set and ML scores from the most recent pipeline run
def find_latest_metaflow_run():
    """Locate the most recent Metaflow run artifacts."""
    metaflow_dir = Path(".metaflow") / "SentryFlowBacktestFlow"
    if not metaflow_dir.exists():
        return None

    runs = sorted([d for d in metaflow_dir.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)
    return runs[0] if runs else None

def extract_scores_from_pipeline():
    """
    Extract y_true and ml_scores from a fresh pipeline run.
    This is a simple extraction script — in practice you'd instrument the pipeline.
    For now, we'll rerun the pipeline and capture the data.
    """
    import warnings
    os.environ["PYTHONPATH"] = str(PYTHONPATH)
    os.chdir(PYTHONPATH)

    # Import pipeline modules
    from pipelines.backtest_flow import SentryFlowBacktestFlow, _engineer_dibb_features
    from src.models.train import train_ensemble, FEATURE_COLS
    from src.policies.evaluator import batch_orchestrate
    import pandas as pd
    import numpy as np

    # 1. Load and prepare data (same as pipeline)
    tx_path = "data/train_transaction.csv"
    id_path = "data/train_identity.csv"

    tx = pd.read_csv(tx_path)
    id_ = pd.read_csv(id_path)
    df = tx.merge(id_, on="TransactionID", how="left")

    df = _engineer_dibb_features(df)
    required_cols = FEATURE_COLS + ["TransactionDT", "isFraud"]
    df = df[required_cols].rename(columns={"isFraud": "is_fraud"})
    df = df.dropna(subset=FEATURE_COLS)
    df = df.sort_values("TransactionDT").reset_index(drop=True)

    # 2. Train/test split
    X = df[FEATURE_COLS]
    y = df["is_fraud"]
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # 3. Train models
    xgb_model, iso_forest, _ = train_ensemble(X_train, y_train)

    # 4. Score test set
    ml_scores = xgb_model.predict_proba(X_test)[:, 1]

    return y_test.values, ml_scores

def analyze_thresholds(y_true, ml_scores):
    """Analyze precision-recall-FPR tradeoffs across thresholds."""
    precisions, recalls, thresholds = precision_recall_curve(y_true, ml_scores)

    print("=" * 80)
    print("PRECISION-RECALL ANALYSIS FOR THRESHOLD CALIBRATION")
    print("=" * 80)
    print()

    # Also compute FPR
    fprs, tprs, _ = roc_curve(y_true, ml_scores)

    results = []
    for threshold in np.arange(0.3, 1.0, 0.05):
        binary_pred = (ml_scores >= threshold).astype(int)
        tp = ((binary_pred == 1) & (y_true == 1)).sum()
        fp = ((binary_pred == 1) & (y_true == 0)).sum()
        fn = ((binary_pred == 0) & (y_true == 1)).sum()
        tn = ((binary_pred == 0) & (y_true == 0)).sum()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

        results.append({
            'threshold': threshold,
            'recall': recall,
            'precision': precision,
            'fpr': fpr,
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'tn': tn,
        })

        fpr_marker = "✓ PASS" if fpr < 0.02 else "✗ FAIL"
        recall_marker = "→ TARGET" if recall >= 0.80 else ""

        print(f"Threshold {threshold:.2f}: Recall={recall:6.2%} | Precision={precision:6.2%} | "
              f"FPR={fpr:6.2%} {fpr_marker:8s} | TP={tp:6d} FP={fp:6d} {recall_marker}")

    print()
    print("=" * 80)

    # Find best threshold for 80% recall while keeping FPR < 2%
    candidates = [r for r in results if r['recall'] >= 0.80 and r['fpr'] < 0.02]
    if candidates:
        best = max(candidates, key=lambda x: x['recall'])  # highest recall in the valid range
        print(f"✓ RECOMMENDED: ML_CRITICAL_THRESHOLD = {best['threshold']:.2f}")
        print(f"  Recall: {best['recall']:.2%} | Precision: {best['precision']:.2%} | FPR: {best['fpr']:.2%}")
        print(f"  TP={best['tp']:,} FP={best['fp']:,} FN={best['fn']:,}")
    else:
        # Can't hit 80% recall @ FPR < 2%, find the best we can do
        by_fpr = [r for r in results if r['fpr'] < 0.02]
        if by_fpr:
            best = max(by_fpr, key=lambda x: x['recall'])
            print(f"⚠ WARNING: Cannot achieve 80% recall @ FPR < 2%")
            print(f"  Best achievable: threshold={best['threshold']:.2f}, recall={best['recall']:.2%}, FPR={best['fpr']:.2%}")
        else:
            print("✗ No threshold found that keeps FPR < 2%. Check model discrimination.")

    print()
    return results

if __name__ == "__main__":
    print("Extracting ML scores from dataset...")
    try:
        y_true, ml_scores = extract_scores_from_pipeline()
        print(f"Loaded {len(y_true):,} test samples, {y_true.sum():,} frauds ({y_true.mean():.2%} fraud rate)")
        print()
        results = analyze_thresholds(y_true, ml_scores)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
