import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

QUEUE_PATH = Path("data/policy_queue")
QUEUE_PATH.mkdir(parents=True, exist_ok=True)


def submit_for_approval(policy: dict, user_id: str) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    ticket_id = hashlib.sha256(f"{json.dumps(policy)}{timestamp}".encode()).hexdigest()[:12]
    payload = {
        "ticket_id": ticket_id,
        "policy": policy,
        "status": "PENDING",
        "submitted_by": user_id,
        "submitted_at": timestamp,
        "approver": None,
        "approved_at": None,
        "rejected_at": None,
        "rejection_reason": None,
    }
    (QUEUE_PATH / f"{ticket_id}.json").write_text(json.dumps(payload, indent=4))
    return ticket_id


def approve_policy(ticket_id: str, approver: str) -> dict:
    ticket = get_ticket(ticket_id)
    if ticket["status"] != "PENDING":
        raise ValueError(f"Ticket {ticket_id} is not PENDING (status: {ticket['status']})")
    ticket["status"] = "APPROVED"
    ticket["approver"] = approver
    ticket["approved_at"] = datetime.now(timezone.utc).isoformat()
    (QUEUE_PATH / f"{ticket_id}.json").write_text(json.dumps(ticket, indent=4))
    return ticket


def reject_policy(ticket_id: str, approver: str, reason: str) -> dict:
    ticket = get_ticket(ticket_id)
    if ticket["status"] != "PENDING":
        raise ValueError(f"Ticket {ticket_id} is not PENDING (status: {ticket['status']})")
    ticket["status"] = "REJECTED"
    ticket["approver"] = approver
    ticket["rejected_at"] = datetime.now(timezone.utc).isoformat()
    ticket["rejection_reason"] = reason
    (QUEUE_PATH / f"{ticket_id}.json").write_text(json.dumps(ticket, indent=4))
    return ticket


def list_pending() -> list:
    tickets = []
    for path in sorted(QUEUE_PATH.glob("*.json")):
        try:
            t = json.loads(path.read_text())
            if t.get("status") == "PENDING":
                tickets.append(t)
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(tickets, key=lambda t: t.get("submitted_at", ""))


def get_ticket(ticket_id: str) -> dict:
    path = QUEUE_PATH / f"{ticket_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Ticket {ticket_id} not found")
    return json.loads(path.read_text())
