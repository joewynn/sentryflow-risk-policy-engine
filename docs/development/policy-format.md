# Active Policy Format

Policies are stored as a JSON array in `data/active_policy.json`. Each element is a rule object with an `if` condition and an `action`.

---

## Rule structure

```json
{
  "if": <JsonLogic expression>,
  "action": "<ACTION_CONSTANT>"
}
```

The file is an array of such objects:

```json
[
  { "if": <condition1>, "action": "REQUIRE_VIDEO_ID" },
  { "if": <condition2>, "action": "REQUIRE_MFA" }
]
```

---

## Default policy

The shipping default at `data/active_policy.json`:

```json
[
  {
    "if": {
      "and": [
        {"==": [{"var": "device_is_emulator"}, true]},
        {">": [{"var": "geo_velocity"}, 500]}
      ]
    },
    "action": "REQUIRE_VIDEO_ID"
  },
  {
    "if": {"<": [{"var": "typing_entropy"}, 1.0]},
    "action": "REQUIRE_MFA"
  }
]
```

---

## JsonLogic operator examples

### Variable access

```json
{"var": "amount"}
{"var": "geo_velocity"}
{"var": "device_is_emulator"}
{"var": "typing_entropy"}
```

### Comparisons

```json
{"==": [{"var": "device_is_emulator"}, true]}
{"!=": [{"var": "tx_type"}, "INTERNAL_TRANSFER"]}
{">": [{"var": "geo_velocity"}, 500]}
{">=": [{"var": "amount"}, 10000]}
{"<": [{"var": "typing_entropy"}, 1.0]}
{"<=": [{"var": "amount"}, 100]}
```

### Logical combinators

```json
{
  "and": [
    {"==": [{"var": "device_is_emulator"}, true]},
    {">": [{"var": "geo_velocity"}, 500]}
  ]
}
```

```json
{
  "or": [
    {">": [{"var": "amount"}, 50000]},
    {"==": [{"var": "device_is_emulator"}, true]}
  ]
}
```

```json
{
  "!": [{"var": "device_is_emulator"}]
}
```

### Nested logic

```json
{
  "and": [
    {">": [{"var": "amount"}, 5000]},
    {
      "or": [
        {"<": [{"var": "typing_entropy"}, 1.5]},
        {"==": [{"var": "device_is_emulator"}, true]}
      ]
    }
  ]
}
```

---

## Conflict resolution

When multiple rules fire, the highest-severity action wins. No special ordering of rules in the array is required.

| Rule 1 action | Rule 2 action | Winner |
|---|---|---|
| REQUIRE_MFA (3) | REQUIRE_VIDEO_ID (4) | REQUIRE_VIDEO_ID |
| DECLINE (5) | REQUIRE_MFA (3) | DECLINE |
| APPROVE (1) | DELAY_4H (2) | DELAY_4H |

---

## Deploying a policy change

**Without governance review (dev/test only):**

Edit `data/active_policy.json` directly. Changes take effect on the next API request — no restart needed.

**With governance review (production):**

1. Edit the policy in the dashboard Policy Playground
2. Click "Submit for 4-Eyes Review"
3. Wait for a Senior Risk Admin to approve in the Approval Inbox
4. Promote the approved ticket to `data/active_policy.json`

See [Governance & 4-Eyes](../compliance/governance.md) for the full approval workflow.

---

## Authoring tips

- Reference only real-time fields: `amount`, `geo_velocity`, `typing_entropy`, `device_is_emulator`. Rules referencing undefined fields are skipped with a warning at runtime.
- Always backtest a new rule before production: use the Shadow Backtest in the dashboard (5000 simulated transactions) and verify FPR stays below 2%.
- Use `REQUIRE_MFA` before `REQUIRE_VIDEO_ID` as a graduated escalation — add a second rule with the same condition plus a higher threshold if you want stricter escalation.
