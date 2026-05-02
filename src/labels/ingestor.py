import pandas as pd


def ingest_confirmed_fraud_labels(
    df: pd.DataFrame,
    confirmed_fraud: pd.DataFrame,
    as_of_date=None,
    maturity_days: int = 60,
) -> pd.DataFrame:
    """
    Merges confirmed fraud labels after a maturity window to simulate chargeback lag.
    Only labels that have aged past maturity_days are included — prevents future label leakage.
    In production: async Kafka/Snowflake ingestion triggers this merge on a scheduled cadence.
    """
    if as_of_date is None:
        as_of_date = pd.Timestamp.now(tz="UTC")
    confirmed_fraud = confirmed_fraud.copy()
    confirmed_fraud["maturity_date"] = (
        pd.to_datetime(confirmed_fraud["timestamp"], utc=True)
        + pd.Timedelta(days=maturity_days)
    )
    # Critical: only merge labels whose maturity window has passed relative to as_of_date
    matured = confirmed_fraud[confirmed_fraud["maturity_date"] <= as_of_date]
    df = df.merge(matured[["transaction_id", "is_confirmed_fraud"]], on="transaction_id", how="left")
    df["is_confirmed_fraud"] = df["is_confirmed_fraud"].fillna(False)
    return df
