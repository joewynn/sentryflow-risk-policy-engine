import pandas as pd
import pytest
from datetime import timezone
from src.labels.ingestor import ingest_confirmed_fraud_labels


def _make_transactions(n=5):
    return pd.DataFrame({
        "transaction_id": [f"TX-{i}" for i in range(n)],
        "amount": [100.0] * n,
    })


def _make_fraud_labels(tx_ids, days_ago):
    """Create confirmed fraud labels with timestamps `days_ago` days in the past."""
    ts = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_ago)
    return pd.DataFrame({
        "transaction_id": tx_ids,
        "is_confirmed_fraud": [True] * len(tx_ids),
        "timestamp": [ts] * len(tx_ids),
    })


def test_matured_labels_are_included():
    """Labels older than 60 days must be merged into the transaction dataframe."""
    df = _make_transactions()
    fraud = _make_fraud_labels(["TX-0", "TX-1"], days_ago=65)
    result = ingest_confirmed_fraud_labels(df, fraud)
    assert result.loc[result["transaction_id"] == "TX-0", "is_confirmed_fraud"].iloc[0] == True
    assert result.loc[result["transaction_id"] == "TX-1", "is_confirmed_fraud"].iloc[0] == True


def test_immature_labels_are_excluded():
    """Labels created 30 days ago (maturity_date in the future) must NOT be merged."""
    df = _make_transactions()
    fraud = _make_fraud_labels(["TX-0"], days_ago=30)
    result = ingest_confirmed_fraud_labels(df, fraud)
    assert result.loc[result["transaction_id"] == "TX-0", "is_confirmed_fraud"].iloc[0] == False


def test_unlabeled_transactions_default_to_false():
    """Transactions with no matching fraud label should have is_confirmed_fraud = False."""
    df = _make_transactions()
    fraud = _make_fraud_labels(["TX-99"], days_ago=70)  # TX-99 not in df
    result = ingest_confirmed_fraud_labels(df, fraud)
    assert (result["is_confirmed_fraud"] == False).all()


def test_mixed_maturity():
    """Only matured labels are included; unmatured are excluded from the same batch."""
    df = _make_transactions(3)
    matured = _make_fraud_labels(["TX-0"], days_ago=61)
    unmatured = _make_fraud_labels(["TX-1"], days_ago=30)
    combined = pd.concat([matured, unmatured], ignore_index=True)

    result = ingest_confirmed_fraud_labels(df, combined)
    assert result.loc[result["transaction_id"] == "TX-0", "is_confirmed_fraud"].iloc[0] == True
    assert result.loc[result["transaction_id"] == "TX-1", "is_confirmed_fraud"].iloc[0] == False


def test_custom_maturity_days():
    """Custom maturity window (e.g. 30 days) should be respected."""
    df = _make_transactions()
    fraud = _make_fraud_labels(["TX-0"], days_ago=35)
    result = ingest_confirmed_fraud_labels(df, fraud, maturity_days=30)
    assert result.loc[result["transaction_id"] == "TX-0", "is_confirmed_fraud"].iloc[0] == True


def test_custom_as_of_date():
    """as_of_date parameter controls the evaluation point for maturity."""
    df = _make_transactions()
    # Label timestamp is 2020-01-01; maturity_date = 2020-03-01
    ts = pd.Timestamp("2020-01-01", tz="UTC")
    fraud = pd.DataFrame({
        "transaction_id": ["TX-0"],
        "is_confirmed_fraud": [True],
        "timestamp": [ts],
    })
    # Evaluated as of 2020-01-15: maturity not yet reached
    early = pd.Timestamp("2020-01-15", tz="UTC")
    result_early = ingest_confirmed_fraud_labels(df, fraud, as_of_date=early)
    assert result_early.loc[result_early["transaction_id"] == "TX-0", "is_confirmed_fraud"].iloc[0] == False

    # Evaluated as of 2020-04-01: maturity reached
    late = pd.Timestamp("2020-04-01", tz="UTC")
    result_late = ingest_confirmed_fraud_labels(df, fraud, as_of_date=late)
    assert result_late.loc[result_late["transaction_id"] == "TX-0", "is_confirmed_fraud"].iloc[0] == True
