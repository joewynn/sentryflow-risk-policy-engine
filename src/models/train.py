import os
import warnings

import joblib
import numpy as np
import pandas as pd

FEATURE_COLS = [
    # Phase 1: Core DIBB signals (6 features)
    "amount",
    "device_is_emulator",
    "geo_velocity",
    "typing_entropy",
    "card_count",           # C1 — number of cards on billing address (fraud MI=0.008)
    "days_since_last_tx",   # D1 — days since last transaction on card (fraud MI=0.006)
    # Phase 2: Account-level enrichment (9 features) — from Kaggle top-5% solutions
    "uid_tx_count",         # transactions on unique customer ID (card1+addr1+D1)
    "uid_amt_mean",         # average transaction amount per UID
    "uid_amt_std",          # variance in spending per UID (anomaly signal)
    "email_domain_risk",    # binary: risky domain (protonmail, anonymous, etc)
    "email_domain_freq",    # rarity of email domain (rare = higher risk)
    "card1_addr1_freq",     # frequency of card+address combinations (multi-account fraud)
    "tx_hour",              # hour of day (fraud patterns may be time-dependent)
    "is_late_night",        # binary: transaction between 22:00-05:00 (suspicious hours)
    "D2_norm",              # days since 2nd-to-last tx, normalized by D1 (gap patterns)
    # Phase 3: Graph analytics (4 features) — synthetic identity ring detection
    "graph_degree",         # number of shared-attribute connections
    "graph_cc_size",        # connected component size (fraud ring size)
    "graph_shared_email_cnt",  # neighbors via email domain (email ring affinity)
    "graph_shared_addr_cnt",   # neighbors via address (address ring affinity)
]

# Allow Docker containers to bind-mount a persistent volume for the cache.
# Default ".zenml_cache" works locally; in containers set SENTRYFLOW_MODEL_CACHE_DIR
# to a path on an attached volume (e.g. /mnt/model-cache) to survive container restarts.
_CACHE_DIR = os.getenv("SENTRYFLOW_MODEL_CACHE_DIR", ".zenml_cache")
_CACHE_PATH = os.path.join(_CACHE_DIR, "prod_xgb.joblib")


def _engineer_dibb_features_standalone(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map IEEE-CIS columns → 19-feature DIBB schema used by the pipeline and models.
    Promoted from pipelines/backtest_flow.py::_engineer_dibb_features() — identical logic,
    now importable without the Metaflow dependency.

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

    # geo_velocity — dist1 / D1: higher = farther distance in shorter time = more suspicious
    if "dist1" in df.columns and "D1" in df.columns:
        df["geo_velocity"] = (
            df["dist1"].fillna(0) / df["D1"].clip(lower=1 / 24).fillna(1)
        ).clip(upper=5000)
    elif "dist1" in df.columns:
        df["geo_velocity"] = df["dist1"].fillna(0).clip(upper=5000)
    else:
        warnings.warn("dist1 not found — geo_velocity set to 0")
        df["geo_velocity"] = 0.0

    # typing_entropy — C1 normalized to [0, 6]; more cards = higher anomaly risk
    if "C1" in df.columns:
        df["typing_entropy"] = (df["C1"].clip(upper=20) / 20 * 6).fillna(3.0)
    else:
        warnings.warn("C1 not found — typing_entropy set to 3.0 (neutral)")
        df["typing_entropy"] = 3.0

    # card_count — C1 raw (number of cards on billing address)
    if "C1" in df.columns:
        df["card_count"] = df["C1"].fillna(0).clip(upper=50)
    else:
        warnings.warn("C1 not found — card_count set to 0")
        df["card_count"] = 0.0

    # days_since_last_tx — D1; INVERSE signal: lower = riskier
    if "D1" in df.columns:
        df["days_since_last_tx"] = df["D1"].fillna(df["D1"].median()).clip(upper=365)
    else:
        warnings.warn("D1 not found — days_since_last_tx set to 30 (neutral)")
        df["days_since_last_tx"] = 30.0

    # === PHASE 2: ENRICHED FEATURES FROM IEEE-CIS ===

    # UID aggregations — card1 + addr1 + D1 forms a unique customer surrogate
    if "card1" in df.columns and "addr1" in df.columns and "D1" in df.columns:
        df["uid"] = (
            df["card1"].astype(str) + "_" +
            df["addr1"].fillna(-1).astype(str) + "_" +
            df["D1"].fillna(-1).round(0).astype(str)
        )
        df["uid_tx_count"] = df.groupby("uid")["TransactionAmt"].transform("count")
        df["uid_amt_mean"] = df.groupby("uid")["TransactionAmt"].transform("mean")
        df["uid_amt_std"] = df.groupby("uid")["TransactionAmt"].transform("std").fillna(0)
    else:
        df["uid_tx_count"] = 5.0
        df["uid_amt_mean"] = df["TransactionAmt"].median() if "TransactionAmt" in df.columns else 100.0
        df["uid_amt_std"] = 0.0

    # Email domain risk — protonmail, anonymous, guerrillamail have 90%+ fraud rate
    if "P_emaildomain" in df.columns:
        HIGH_RISK_DOMAINS = {"protonmail.com", "anonymous.com", "guerrillamail.com"}
        domain_freq = df["P_emaildomain"].value_counts(normalize=True)
        df["email_domain_risk"] = df["P_emaildomain"].isin(HIGH_RISK_DOMAINS).astype(int)
        df["email_domain_freq"] = df["P_emaildomain"].map(domain_freq).fillna(0.0)
    else:
        df["email_domain_risk"] = 0
        df["email_domain_freq"] = 0.01

    # Card × address interaction frequency — captures multi-account fraud rings
    if "card1" in df.columns and "addr1" in df.columns:
        df["card1_addr1"] = df["card1"].astype(str) + "_" + df["addr1"].fillna(-1).astype(str)
        df["card1_addr1_freq"] = (
            df.groupby("card1_addr1")["TransactionID"].transform("count")
            if "TransactionID" in df.columns else 1.0
        )
    else:
        df["card1_addr1_freq"] = 1.0

    # Temporal signals
    if "TransactionDT" in df.columns:
        df["tx_hour"] = ((df["TransactionDT"] // 3600) % 24).astype(int)
        df["is_late_night"] = ((df["tx_hour"] >= 22) | (df["tx_hour"] <= 5)).astype(int)
    else:
        df["tx_hour"] = 12
        df["is_late_night"] = 0

    # D2_norm — days since second-to-last transaction, normalized by D1
    if "D2" in df.columns and "D1" in df.columns:
        df["D2_norm"] = (df["D2"] - df["D1"]).fillna(0).clip(lower=-365, upper=365)
    else:
        df["D2_norm"] = 0.0

    # Rename target column so downstream steps access df["is_fraud"] uniformly
    if "isFraud" in df.columns:
        df = df.rename(columns={"isFraud": "is_fraud"})

    return df


def load_model_from_zenml(
    model_name: str = "sentryflow_xgb",
    artifact_name: str = "xgb_model",
    cache_path: str = _CACHE_PATH,
):
    """
    Load the Production-staged model from ZenML MCP.

    Tier 1 — ZenML MCP: connects to the server, fetches the Production artifact,
              writes a local cache for outage resilience, and returns the model.
    Tier 2 — Local cache: if ZenML is unreachable and a cache exists from a prior
              successful start, loads that instead with a RuntimeWarning.
    Tier 3 — Hard failure: no MCP + no cache → RuntimeError. The API intentionally
              refuses to start rather than silently issuing fake risk decisions.
    """
    try:
        from zenml.client import Client
        from zenml.enums import ModelStages

        client = Client()
        mv = client.get_model_version(
            model_name_or_id=model_name,
            model_version_name_or_number_or_id=ModelStages.PRODUCTION,
        )
        model = mv.get_artifact(name=artifact_name).load()
        print(f"Loaded {model_name}/{artifact_name} from ZenML MCP (version: {mv.name})")

        os.makedirs(_CACHE_DIR, exist_ok=True)
        joblib.dump(model, cache_path)
        print(f"Model cached locally at {cache_path}")
        return model

    except Exception as exc:
        if os.path.exists(cache_path):
            warnings.warn(
                f"ZenML MCP unreachable ({exc}). Loading last known production model "
                f"from local cache: {cache_path}",
                RuntimeWarning,
                stacklevel=2,
            )
            return joblib.load(cache_path)

        raise RuntimeError(
            f"Cannot load model from ZenML MCP ({exc}) and no local cache exists at "
            f"'{cache_path}'. Run 'make train' to produce a Production model, then restart."
        ) from exc
