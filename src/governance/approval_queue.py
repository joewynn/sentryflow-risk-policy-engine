import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

QUEUE_PATH = Path("data/policy_queue")
QUEUE_PATH.mkdir(parents=True, exist_ok=True)

def submit_for_approval(policy: dict, user_id: str):
    timestamp = datetime.now(timezone.utc).isoformat()
    # Unique ID based on content + time
    ticket_id = hashlib.sha256(f"{json.dumps(policy)}{timestamp}".encode()).hexdigest()[:12]
    
    payload = {
        "ticket_id": ticket_id,
        "policy": policy,
        "status": "PENDING",
        "submitted_by": user_id,
        "submitted_at": timestamp
    }
    
    with open(QUEUE_PATH / f"{ticket_id}.json", "w") as f:
        json.dump(payload, f, indent=4)
    return ticket_id