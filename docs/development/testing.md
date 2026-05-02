# Running Tests

## Prerequisites

Tests require the virtualenv with all dependencies installed:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python3 -r requirements.txt pytest httpx
```

---

## Run all tests

```bash
.venv/bin/python -m pytest tests/ -v
```

All 31 tests should pass. Expected output ends with:

```
31 passed in X.XXs
```

---

## Run a specific test file

```bash
.venv/bin/python -m pytest tests/test_orchestration.py -v
.venv/bin/python -m pytest tests/test_governance.py -v
.venv/bin/python -m pytest tests/test_label_ingestor.py -v
.venv/bin/python -m pytest tests/test_api.py -v
```

---

## Run a single test

```bash
.venv/bin/python -m pytest tests/test_orchestration.py::test_ml_override_critical_beats_pass -v
```

---

## Test coverage by file

### `tests/test_orchestration.py`

Core ensemble logic — the most critical tests:

| Test | What it verifies |
|---|---|
| `test_ml_override_critical_beats_pass` | ML score > 0.92 + rule PASS → REQUIRE_VIDEO_ID, strategy `ML_OVERRIDE_CRITICAL` |
| `test_ml_friction_beats_pass` | ML score 0.75–0.92 + rule PASS → REQUIRE_MFA, strategy `ML_ENHANCED_FRICTION` |
| `test_rule_led_block_ignores_ml` | Rule BLOCK with any ML score → rule action, strategy `RULE_LED` |
| `test_approve_when_both_pass` | ML < 0.75 + rule PASS → APPROVE |
| `test_batch_multiple_rows` | Vectorized orchestration returns correct action for each row |
| `test_fpr_formula` | FPR = FP/(FP+TN), not 1-precision (regression test for the formula fix) |
| `test_evaluate_policy_severity_conflict` | When two rules fire, highest severity wins |
| `test_emulator_with_high_velocity_triggers_block` | Default policy rule exercises json_logic_compat |

### `tests/test_label_ingestor.py`

Label maturity window enforcement:

| Test | What it verifies |
|---|---|
| `test_maturity_window_excludes_future` | Chargebacks past the as_of_date maturity window are excluded |
| `test_maturity_window_includes_past` | Chargebacks within the window are included |
| `test_as_of_date_default` | Default as_of_date uses today |
| `test_empty_fraud_frame` | No chargebacks → all transactions unlabeled |
| `test_no_confirmed_fraud_after_maturity` | All chargebacks in future → no labels applied |
| `test_maturity_days_param` | Custom maturity_days parameter changes the cutoff |

### `tests/test_governance.py`

Full approval lifecycle:

| Test | What it verifies |
|---|---|
| `test_submit_creates_pending_ticket` | Ticket is written with PENDING status |
| `test_approve_sets_approved` | Status → APPROVED, approver recorded |
| `test_reject_sets_rejected` | Status → REJECTED, reason recorded |
| `test_double_approve_raises` | Second approve raises ValueError |
| `test_double_reject_raises` | Second reject raises ValueError |
| `test_approve_rejected_raises` | Approving an already-rejected ticket raises ValueError |
| `test_list_pending_filters` | list_pending() returns only PENDING tickets |
| `test_get_ticket_not_found` | FileNotFoundError for unknown ticket_id |
| `test_ticket_schema_fields` | All required fields present in ticket JSON |

### `tests/test_api.py`

HTTP API behavior:

| Test | What it verifies |
|---|---|
| `test_missing_required_field` | HTTP 422 for missing `transaction_id` |
| `test_amount_zero_rejected` | HTTP 422 for `amount = 0` |
| `test_negative_amount_rejected` | HTTP 422 for `amount < 0` |
| `test_geo_velocity_out_of_range` | HTTP 422 for `geo_velocity > 5000` |
| `test_typing_entropy_out_of_range` | HTTP 422 for `typing_entropy > 6.0` |
| `test_block_response_schema` | BLOCK response has all required fields |
| `test_approve_response_schema` | PASS response has correct structure |
| `test_strategy_field_present` | `strategy` field is always present in response |
