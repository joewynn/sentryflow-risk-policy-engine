# Governance & 4-Eyes Approval

SentryFlow enforces separation of duties for policy changes: a Risk Manager authors a rule; a Senior Risk Admin approves or rejects it before it can be promoted to production.

---

## Workflow

```
Risk Manager                Senior Risk Admin
     │                             │
     │  Edit rule in dashboard     │
     │  → click "Submit for        │
     │    4-Eyes Review"           │
     │                             │
     │  submit_for_approval()      │
     │  writes ticket to           │
     │  data/policy_queue/         │
     │                             │
     │                      Opens Approval Inbox
     │                      in dashboard
     │                             │
     │                      Clicks Approve or Reject
     │                             │
     │                      approve_policy() or
     │                      reject_policy() updates
     │                      ticket status
     │                             │
     └─────────────────────────────┘
```

An approved ticket updates the file status to `APPROVED`. The admin must then manually promote the policy to `data/active_policy.json` — approval alone does not deploy it.

---

## Implementation

The approval queue is implemented in `src/governance/approval_queue.py`. It is **file-system based** — no database, no message bus. Each ticket is a JSON file in `data/policy_queue/`.

### Submit for approval

```python
from src.governance.approval_queue import submit_for_approval

ticket_id = submit_for_approval(policy=rule_list, user_id="risk_manager_1")
```

Creates `data/policy_queue/{ticket_id}.json` with status `PENDING`.

### Approve

```python
from src.governance.approval_queue import approve_policy

ticket = approve_policy(ticket_id="abc123", approver="senior_admin_2")
```

Updates status to `APPROVED`, records `approver` and `approved_at`. Raises `ValueError` if ticket is not `PENDING`.

### Reject

```python
from src.governance.approval_queue import reject_policy

ticket = reject_policy(
    ticket_id="abc123",
    approver="senior_admin_2",
    reason="FPR exceeded 2% in backtest"
)
```

Updates status to `REJECTED`, records `rejection_reason` and `rejected_at`. Raises `ValueError` if ticket is not `PENDING`.

### List pending

```python
from src.governance.approval_queue import list_pending

tickets = list_pending()  # Returns list sorted by submitted_at
```

---

## Ticket schema

| Field | Type | Description |
|---|---|---|
| `ticket_id` | string | SHA256 hex prefix (12 chars) of policy+timestamp |
| `policy` | list | The JsonLogic rule array submitted for review |
| `status` | string | `PENDING`, `APPROVED`, or `REJECTED` |
| `submitted_by` | string | User ID of the Risk Manager who submitted |
| `submitted_at` | ISO 8601 | UTC timestamp of submission |
| `approver` | string or null | User ID of the admin who acted |
| `approved_at` | ISO 8601 or null | When approved |
| `rejected_at` | ISO 8601 or null | When rejected |
| `rejection_reason` | string or null | Reason provided at rejection |

---

## Constraints

- **Self-approval is not enforced at the code level** — it is a process control. The dashboard Approval Inbox should display only tickets not submitted by the logged-in user.
- **No webhook or notification** — the Senior Admin must check the Approval Inbox in the dashboard.
- **Single action per ticket** — once `APPROVED` or `REJECTED`, further calls raise `ValueError`. Re-submission requires a new ticket.

---

## Emergency override

For time-critical situations (viral fraud outbreak), the dashboard provides an Emergency Push that bypasses the 4-eyes queue:

1. Senior Risk Admin edits a rule in the dashboard
2. Clicks "Emergency Push" instead of "Submit for Review"
3. The policy is written directly to `data/active_policy.json`
4. An audit record is written to `data/audit_trail/emergency_{timestamp}.json`

The audit record includes the full policy content and SHA256 signature for post-mortem compliance review.
