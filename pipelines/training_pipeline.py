# pipelines/training_pipeline.py
import hashlib
import os
import subprocess
import warnings
from typing import Annotated, Tuple

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from zenml import Model, get_step_context, log_metadata, pipeline, step
from zenml.client import Client
from zenml.enums import ModelStages

from src.models.train import FEATURE_COLS, _engineer_dibb_features_standalone
from src.policies.evaluator import batch_orchestrate, evaluate_policy


# ─────────────────────────────────────────────
# Step 1: Ingest + Feature Engineering
# ─────────────────────────────────────────────
@step
def ingest_and_engineer(
    tx_path: str,
    id_path: str,
) -> Tuple[
    Annotated[pd.DataFrame, "feature_df"],
    Annotated[str, "policy_version"],
]:
    """Load IEEE-CIS dataset and apply 19-feature DIBB engineering pipeline.
    Paths are injected via run_config.yaml — no defaults hardcoded here.
    Accepts s3:// URIs (preferred) or local paths (dev fallback).
    pandas reads S3 natively via s3fs when boto3 credentials are configured.
    """
    def _readable(path: str) -> bool:
        return path.startswith("s3://") or os.path.exists(path)

    if not _readable(tx_path):
        raise FileNotFoundError(
            f"IEEE-CIS data not found at '{tx_path}'. "
            "Ensure your paths in run_config.yaml are correct, or run 'make setup'."
        )

    tx = pd.read_csv(tx_path)
    id_ = pd.read_csv(id_path) if _readable(id_path) else pd.DataFrame()

    if not id_.empty:
        df = tx.merge(id_, on="TransactionID", how="left")
        print(f"  Loaded {len(tx):,} transactions, {len(id_):,} identity rows")
        print(f"  Identity match rate: {len(id_) / len(tx):.1%}")
    else:
        warnings.warn("Identity data missing — identity features unavailable")
        df = tx

    df = _engineer_dibb_features_standalone(df)
    policy_version = "v2026.05.ieee"

    print(f"Ingested {len(df):,} rows. Fraud rate: {df['is_fraud'].mean():.3%}")
    return df, policy_version


# ─────────────────────────────────────────────
# Step 2: Graph Feature Engineering
# ─────────────────────────────────────────────
@step
def build_graph_features(
    feature_df: pd.DataFrame,
) -> Annotated[pd.DataFrame, "graph_enriched_df"]:
    """Compute 4 shared-identity graph features (degree, cc_size, email/addr ring counts)."""
    if "TransactionID" not in feature_df.columns:
        print("Skipping graph features — no TransactionID column.")
        return feature_df

    try:
        from src.features.graph_features import (
            build_shared_identity_graph,
            extract_graph_features,
        )

        G = build_shared_identity_graph(feature_df)
        gf = extract_graph_features(G, feature_df)
        enriched = feature_df.merge(gf.reset_index(), on="TransactionID", how="left")
        print(f"Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
        return enriched
    except Exception as exc:
        print(f"Graph extraction failed ({exc}), using default zero values.")
        feature_df = feature_df.copy()
        feature_df["graph_degree"] = 0
        feature_df["graph_cc_size"] = 1
        feature_df["graph_shared_email_cnt"] = 0
        feature_df["graph_shared_addr_cnt"] = 0
        return feature_df


# ─────────────────────────────────────────────
# Step 3: Train Ensemble
# ─────────────────────────────────────────────
@step
def train_ensemble_step(
    graph_enriched_df: pd.DataFrame,
) -> Tuple[
    Annotated[XGBClassifier, "xgb_model"],
    Annotated[IsolationForest, "iso_forest"],
    Annotated[pd.DataFrame, "X_test"],
    Annotated[pd.Series, "y_test"],
]:
    """Temporal 80/20 split → fit XGBClassifier (focal loss proxy) + IsolationForest.
    Model context (name, version) is inherited from the @pipeline model= argument —
    not hardcoded here, so any model name passed at invocation time applies automatically.
    """
    df = graph_enriched_df.sort_values("TransactionDT").reset_index(drop=True)

    # Drop rows with NaN in any feature column (graph features may be NaN after left merge)
    df = df.dropna(subset=FEATURE_COLS).reset_index(drop=True)

    X = df[FEATURE_COLS]
    y = df["is_fraud"]

    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale_pos_weight = neg / pos if pos > 0 else 100.0
    fraud_rate = pos / (pos + neg) if (pos + neg) > 0 else 0.01
    contamination = min(max(fraud_rate, 0.001), 0.1)

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.15, random_state=42, stratify=y_train
    )

    xgb_model = XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
    )
    xgb_model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    iso_forest = IsolationForest(contamination=contamination, random_state=42)
    iso_forest.fit(X_tr)

    # NOTE: ZenML auto-captures git SHA when linked to GitHub via 'zenml connect --github'.
    # This subprocess call is redundant in that setup but kept as a local dev fallback.
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"]
        ).decode().strip()
    except Exception:
        git_sha = "unknown"

    try:
        data_hash = hashlib.md5(
            pd.util.hash_pandas_object(X_train, index=True).values
        ).hexdigest()[:8]
    except Exception:
        data_hash = "unknown"

    log_metadata(
        metadata={
            "hyperparameters": {
                "n_estimators": 100,
                "max_depth": 6,
                "learning_rate": 0.1,
                "scale_pos_weight": round(scale_pos_weight, 2),
                "contamination": round(contamination, 4),
            },
            "data": {
                "n_train": int(split_idx),
                "n_test": len(X_test),
                "n_features": len(FEATURE_COLS),
                "feature_cols": FEATURE_COLS,
                "data_hash": data_hash,
                "git_sha": git_sha,
                "fraud_rate_train": round(float(y_train.mean()), 4),
            },
        }
    )

    print(f"Trained on {len(X_train):,} samples. Evaluating on {len(X_test):,}.")
    return xgb_model, iso_forest, X_test, y_test


# ─────────────────────────────────────────────
# Step 4: Backtest (Evaluation)
# ─────────────────────────────────────────────
@step
def run_backtest(
    xgb_model: XGBClassifier,
    iso_forest: IsolationForest,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    policy_version: str,
) -> Annotated[dict, "backtest_metrics"]:
    """Run ensemble orchestration on held-out test set and log all metrics to ZenML MCP."""
    candidate_rule = {
        "if": {"and": [
            {"==": [{"var": "device_is_emulator"}, True]},
            {">": [{"var": "geo_velocity"}, 500]},
        ]},
        "action": "REQUIRE_VIDEO_ID",
    }

    rule_results = X_test.apply(
        lambda r: evaluate_policy([candidate_rule], r.to_dict()), axis=1
    )
    rule_df = pd.DataFrame({
        "decision": rule_results.apply(lambda x: x["decision"]),
        "action": rule_results.apply(lambda x: x["action"]),
        "adverse_action_code": rule_results.apply(lambda x: x["adverse_action_code"]),
    })

    ml_scores = pd.Series(xgb_model.predict_proba(X_test)[:, 1], index=X_test.index)
    orchestrated = batch_orchestrate(rule_df, ml_scores)

    y_true = y_test.values
    y_pred = (orchestrated["decision"] == "BLOCK").astype(int).values
    ml_scores_arr = ml_scores.values

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    iso_binary = (iso_forest.predict(X_test) == -1).astype(int)

    metrics = {
        "precision":      float(tp / (tp + fp) if (tp + fp) > 0 else 0.0),
        "recall":         float(tp / (tp + fn) if (tp + fn) > 0 else 0.0),
        "fpr":            float(fp / (fp + tn) if (fp + tn) > 0 else 0.0),
        "f1":             float(f1_score(y_true, y_pred, zero_division=0)),
        "auprc":          float(average_precision_score(y_true, ml_scores_arr)),
        "auroc":          float(roc_auc_score(y_true, ml_scores_arr)),
        "iso_recall":     float(recall_score(y_true, iso_binary, zero_division=0)),
        "iso_precision":  float(precision_score(y_true, iso_binary, zero_division=0)),
        "policy_version": policy_version,
    }

    log_metadata(metadata={"evaluation": metrics})

    print(
        f"XGB  → Precision: {metrics['precision']:.2%} | Recall: {metrics['recall']:.2%} | "
        f"FPR: {metrics['fpr']:.2%} | AUROC: {metrics['auroc']:.3f}"
    )
    print(
        f"IsoF → Recall: {metrics['iso_recall']:.2%} | Precision: {metrics['iso_precision']:.2%}"
    )
    return metrics


# ─────────────────────────────────────────────
# Step 5: Approval Gate + MCP Promotion
# ─────────────────────────────────────────────
@step
def approval_gate(backtest_metrics: dict) -> Annotated[bool, "is_approved"]:
    """
    Governance check: FPR < 2%.
    Reads the active model name dynamically from the pipeline context — not hardcoded —
    so this step works regardless of which model name was configured at invocation.
    On pass, promotes that model version to ModelStages.PRODUCTION in ZenML MCP.
    """
    fpr = backtest_metrics["fpr"]
    is_approved = fpr < 0.02

    # Resolve model name from the pipeline's model context, not a hardcoded string
    model_name = get_step_context().model.name

    if is_approved:
        client = Client()
        mv = client.get_model_version(
            model_name_or_id=model_name,
            model_version_name_or_number_or_id="latest",
        )
        mv.set_stage(stage=ModelStages.PRODUCTION, force=True)
        print(
            f"Governance PASSED (FPR={fpr:.2%} < 2%). "
            f"Model '{model_name}/{mv.name}' promoted to PRODUCTION."
        )
    else:
        print(
            f"Governance FAILED (FPR={fpr:.2%} >= 2%). "
            "Model NOT promoted. Tune ML_CRITICAL_THRESHOLD in src/policies/evaluator.py."
        )

    log_metadata(metadata={"governance": {"approved": is_approved, "fpr": fpr}})
    return is_approved


# ─────────────────────────────────────────────
# Pipeline Assembly
# ─────────────────────────────────────────────
@pipeline(enable_cache=True)
def sentryflow_training_pipeline(tx_path: str, id_path: str) -> None:
    """
    Pipeline accepts no hardcoded defaults — all parameters come from run_config.yaml.
    The model name is also external: passed via with_options(model=...) at invocation time.
    ZenML caches steps whose inputs haven't changed; re-runs only what's necessary.
    """
    feature_df, policy_version = ingest_and_engineer(tx_path=tx_path, id_path=id_path)
    graph_df = build_graph_features(feature_df=feature_df)
    xgb_model, iso_forest, X_test, y_test = train_ensemble_step(graph_enriched_df=graph_df)
    metrics = run_backtest(
        xgb_model=xgb_model,
        iso_forest=iso_forest,
        X_test=X_test,
        y_test=y_test,
        policy_version=policy_version,
    )
    approval_gate(backtest_metrics=metrics)


if __name__ == "__main__":
    # Model name and config are fully external — no source edits needed to switch environments.
    # Dev experiment:  SENTRYFLOW_MODEL_NAME=sentryflow_xgb_dev SENTRYFLOW_RUN_CONFIG=run_config_dev.yaml
    # Prod run:        (defaults below)
    run_model = Model(name=os.getenv("SENTRYFLOW_MODEL_NAME", "sentryflow_xgb"))
    config_path = os.getenv("SENTRYFLOW_RUN_CONFIG", "run_config.yaml")
    sentryflow_training_pipeline.with_options(
        model=run_model,
        config_path=config_path,
    )()
