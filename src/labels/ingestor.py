import pandas as pd
from datetime import datetime, timedelta

def ingest_confirmed_fraud_labels(df: pd.DataFrame, confirmed_fraud: pd.DataFrame) -> pd.DataFrame:
    """
    Simulate 30-90 day chargeback lag.
    In production: async Kafka/Snowflake ingestion + 60-day maturity window retrain.
    """
    # Merge on transaction_id after maturity window
    confirmed_fraud["maturity_date"] = confirmed_fraud["timestamp"] + timedelta(days=60)
    df = df.merge(confirmed_fraud[["transaction_id", "is_confirmed_fraud"]], 
                  on="transaction_id", how="left")
    df["is_confirmed_fraud"] = df["is_confirmed_fraud"].fillna(False)
    return df