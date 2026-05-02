import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

VALID_PAYLOAD = {
    "transaction_id": "TX-TEST-001",
    "tx_type": "WIRE_TRANSFER",
    "amount": 5000.0,
    "device_is_emulator": True,
    "geo_velocity": 800.0,
    "typing_entropy": 1.1,
}


def test_risk_check_returns_200():
    response = client.post("/v1/risk-check", json=VALID_PAYLOAD)
    assert response.status_code == 200


def test_risk_check_response_has_strategy():
    response = client.post("/v1/risk-check", json=VALID_PAYLOAD)
    body = response.json()
    assert "strategy" in body
    assert body["strategy"] in ("ML_OVERRIDE_CRITICAL", "ML_ENHANCED_FRICTION", "RULE_LED")


def test_risk_check_response_has_decision():
    response = client.post("/v1/risk-check", json=VALID_PAYLOAD)
    body = response.json()
    assert body["decision"] in ("BLOCK", "PASS")


def test_risk_check_response_has_metadata():
    response = client.post("/v1/risk-check", json=VALID_PAYLOAD)
    body = response.json()
    assert "metadata" in body
    assert "audit_id" in body["metadata"]
    assert "policy_version" in body["metadata"]


def test_risk_check_missing_required_field_returns_422():
    """Endpoint must reject payloads missing required fields."""
    response = client.post("/v1/risk-check", json={"amount": 100.0})
    assert response.status_code == 422


def test_risk_check_negative_amount_returns_422():
    """Amount must be > 0."""
    payload = {**VALID_PAYLOAD, "amount": -100.0}
    response = client.post("/v1/risk-check", json=payload)
    assert response.status_code == 422


def test_risk_check_geo_velocity_out_of_range_returns_422():
    """geo_velocity must be in [0, 5000]."""
    payload = {**VALID_PAYLOAD, "geo_velocity": 9999.0}
    response = client.post("/v1/risk-check", json=payload)
    assert response.status_code == 422


def test_emulator_with_high_velocity_triggers_block():
    """Rule: emulator=True AND geo_velocity>500 → BLOCK (from active_policy.json default)."""
    payload = {
        "transaction_id": "TX-EMULATOR",
        "tx_type": "WIRE_TRANSFER",
        "amount": 1000.0,
        "device_is_emulator": True,
        "geo_velocity": 800.0,
        "typing_entropy": 3.0,
    }
    response = client.post("/v1/risk-check", json=payload)
    body = response.json()
    assert body["decision"] == "BLOCK"
