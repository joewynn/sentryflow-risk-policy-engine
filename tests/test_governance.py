import json
import pytest
from pathlib import Path
from src.governance.approval_queue import (
    submit_for_approval, approve_policy, reject_policy, list_pending, get_ticket
)

SAMPLE_POLICY = {"if": {"==": [{"var": "device_is_emulator"}, True]}, "action": "DECLINE"}


def test_submit_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    ticket_id = submit_for_approval(SAMPLE_POLICY, "test_user")
    assert (tmp_path / f"{ticket_id}.json").exists()


def test_submit_returns_unique_ids(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    id1 = submit_for_approval(SAMPLE_POLICY, "user_a")
    id2 = submit_for_approval(SAMPLE_POLICY, "user_b")
    assert id1 != id2


def test_submitted_ticket_is_pending(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    ticket_id = submit_for_approval(SAMPLE_POLICY, "test_user")
    ticket = get_ticket(ticket_id)
    assert ticket["status"] == "PENDING"
    assert ticket["approver"] is None


def test_approve_transitions_to_approved(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    ticket_id = submit_for_approval(SAMPLE_POLICY, "test_user")
    result = approve_policy(ticket_id, "senior_admin")
    assert result["status"] == "APPROVED"
    assert result["approver"] == "senior_admin"
    assert result["approved_at"] is not None


def test_reject_transitions_to_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    ticket_id = submit_for_approval(SAMPLE_POLICY, "test_user")
    result = reject_policy(ticket_id, "senior_admin", "FPR threshold not met")
    assert result["status"] == "REJECTED"
    assert result["rejection_reason"] == "FPR threshold not met"


def test_approve_non_pending_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    ticket_id = submit_for_approval(SAMPLE_POLICY, "test_user")
    approve_policy(ticket_id, "admin_1")
    with pytest.raises(ValueError, match="not PENDING"):
        approve_policy(ticket_id, "admin_2")


def test_list_pending_excludes_approved(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    t1 = submit_for_approval(SAMPLE_POLICY, "user_1")
    t2 = submit_for_approval(SAMPLE_POLICY, "user_2")
    approve_policy(t1, "admin")
    pending = list_pending()
    pending_ids = [t["ticket_id"] for t in pending]
    assert t1 not in pending_ids
    assert t2 in pending_ids


def test_list_pending_excludes_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    t1 = submit_for_approval(SAMPLE_POLICY, "user_1")
    reject_policy(t1, "admin", "failed")
    assert list_pending() == []


def test_get_ticket_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("src.governance.approval_queue.QUEUE_PATH", tmp_path)
    with pytest.raises(FileNotFoundError):
        get_ticket("nonexistent_ticket")
