# Threat Models

SentryFlow is designed to detect four AI-augmented fraud categories that legacy rule-based systems cannot address alone.

---

## 1. AI-Augmented Social Engineering

**The threat:** Fraudsters use LLM-driven voice or text clones to coach legitimate users into authorizing fraudulent wire transfers ("pig butchering," romance scams). The user is real and consents — but the intent is fraudulent.

**Detection signal:** `typing_entropy` (DIBB). Even when the account holder is genuine, being coached over the phone changes their typing behavior: hesitation pauses, copy-pasting amounts from a script, unnatural key-spacing. Entropy drops below 1.0–2.0.

**Policy rule:**
```json
{
  "if": {
    "and": [
      {"<": [{"var": "typing_entropy"}, 1.5]},
      {">": [{"var": "amount"}, 5000]}
    ]
  },
  "action": "REQUIRE_VIDEO_ID"
}
```
Implemented in `data/active_policy.json`. REQUIRE_VIDEO_ID breaks the fraudster's rapport with the victim before the wire is authorized.

---

## 2. Generative Synthetic Identity (GSI)

**The threat:** Fraudsters use AI to generate synthetic identity documents and deepfake faces that pass traditional KYC. These accounts have no prior history but appear "clean" to legacy credit and identity vendors.

**Detection signal:** Isolation Forest (unsupervised ML). GSI accounts often originate from the same generative model or device cluster. Even when individual transactions look normal, the Isolation Forest identifies them as statistical outliers in the feature space.

**Ensemble path:** When the Isolation Forest flags a transaction as anomalous and the XGBoost score exceeds `ML_CRITICAL_THRESHOLD = 0.92`, `batch_orchestrate()` takes the `ML_OVERRIDE_CRITICAL` path and returns `REQUIRE_VIDEO_ID`.

Note: The Isolation Forest score is currently evaluated in `pipelines/backtest_flow.py` but not yet fused into the real-time API fast path. XGBoost alone drives the `ML_OVERRIDE_CRITICAL` threshold in production.

---

## 3. Automated Account Takeover (ATO)

**The threat:** High-velocity botnets use leaked credential lists and mobile emulators to test accounts at scale, then drain balances.

**Detection signals:** `device_is_emulator` + `geo_velocity`. Emulators running credential-stuffing scripts generate physically impossible velocities as each "device" logs in from a different IP address.

**Policy rule (default):**
```json
{
  "if": {
    "and": [
      {"==": [{"var": "device_is_emulator"}, true]},
      {">": [{"var": "geo_velocity"}, 500]}
    ]
  },
  "action": "REQUIRE_VIDEO_ID"
}
```
Implemented in `data/active_policy.json` and verified by `tests/test_orchestration.py::test_emulator_with_high_velocity_triggers_block`.

---

## 4. Regulatory "Failure to Prevent" Exposure

**The threat:** Under Nacha 2026 rules, a neobank that cannot demonstrate proactive monitoring for "false pretenses" faces 100% liability for losses plus federal fines. Legacy black-box vendors cannot produce the audit trail required.

**Defense mechanism:** Every SentryFlow decision includes a SHA256 `policy_signature` over the exact rule JSON active at request time, plus a Nacha Adverse Action Code. This creates a "Defensible Intelligence" packet that can be presented to regulators verbatim.

See [Nacha 2026 Compliance](../compliance/nacha.md) for the full audit trail schema.
