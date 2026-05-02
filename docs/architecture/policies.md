# Policy Engine

The policy engine evaluates JsonLogic rules against incoming transaction data and resolves conflicts using a severity ranking.

---

## Rule storage

Rules live in `data/active_policy.json`. The file is loaded on each API request — no restart needed to deploy a new policy.

Format: a JSON array of rule objects.

```json
[
  {
    "if": {"and": [
      {"==": [{"var": "device_is_emulator"}, true]},
      {">": [{"var": "geo_velocity"}, 500]}
    ]},
    "action": "REQUIRE_VIDEO_ID"
  },
  {
    "if": {"<": [{"var": "typing_entropy"}, 1.0]},
    "action": "REQUIRE_MFA"
  }
]
```

Each rule object must have two keys:

| Key | Type | Description |
|---|---|---|
| `if` | JsonLogic expression | Condition evaluated against the request payload |
| `action` | string | One of the five action constants below |

---

## Actions and severity

When multiple rules fire on the same transaction, the highest-severity action wins.

| Action | Severity | Meaning |
|---|---|---|
| `DECLINE` | 5 | Hard block — transaction rejected |
| `REQUIRE_VIDEO_ID` | 4 | High friction — synchronous video identity check |
| `REQUIRE_MFA` | 3 | Medium friction — step-up authentication |
| `DELAY_4H` | 2 | Soft hold — transaction queued for manual review |
| `APPROVE` | 1 | Pass — no additional friction |

If no rules fire, the action defaults to `APPROVE`.

---

## Decision outcome

The `decision` field in the response is derived from the winning action:

| Action | Decision |
|---|---|
| `DECLINE` or `REQUIRE_VIDEO_ID` | `BLOCK` |
| `REQUIRE_MFA`, `DELAY_4H`, or `APPROVE` | `PASS` |

The boundary is SEVERITY_MAP > 3 → BLOCK, implemented in `src/policies/evaluator.py`.

---

## Missing fields

If a rule references a payload field that is not present:

- A `WARNING` is logged: `Missing field in payload during rule evaluation: <field> | rule=<rule>`
- That rule is skipped
- The remaining rules still evaluate normally
- The request never fails due to a missing feature field

This allows adding new signals to policies before they are available in all callers.

---

## Policy signature

Every call to `evaluate_policy()` computes a SHA256 signature over the rule JSON:

```python
hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()[:16]
```

The signature appears in `metadata.policy_version` in every response, enabling exact reconstruction of the rule logic at audit time.

---

## JsonLogic operator reference

The policy engine uses `src/utils/json_logic_compat.py` — a Python 3 reimplementation of the JsonLogic spec.

| Operator | Example |
|---|---|
| Variable lookup | `{"var": "amount"}` |
| Equality | `{"==": [{"var": "device_is_emulator"}, true]}` |
| Greater than | `{">": [{"var": "geo_velocity"}, 500]}` |
| Less than | `{"<": [{"var": "typing_entropy"}, 1.0]}` |
| Logical AND | `{"and": [<expr1>, <expr2>]}` |
| Logical OR | `{"or": [<expr1>, <expr2>]}` |
| Logical NOT | `{"!": [<expr>]}` |

See [Policy Format Guide](../development/policy-format.md) for full authoring examples.
