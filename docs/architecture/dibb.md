# DIBB Signals

DIBB (Device Intelligence + Behavioral Biometrics) are the real-time signals SentryFlow evaluates on every transaction. They are designed to detect AI-augmented fraud patterns that bypass traditional identity checks.

---

## Signal dictionary

| Signal | Type | Range | Description |
|---|---|---|---|
| `amount` | float | > 0.0 | Transaction amount in USD. High-value wires receive heightened scrutiny. |
| `geo_velocity` | float | 0–5000 km/h | Implied speed from consecutive logins at different geographic locations. Values > 500 km/h indicate physically impossible travel — emulator farms or VPN-hopping botnets. |
| `typing_entropy` | float | 0.0–6.0 | Shannon entropy of keystroke inter-arrival timing. Bots and scripted attacks score < 1.0. Humans under social-engineering coaching (being read a script) score 1.0–2.0. Normal human typing is 2.5–4.5. |
| `device_is_emulator` | bool (int) | 0 or 1 | True if the device fingerprint matches known Android/iOS emulator signatures. Used in conjunction with `geo_velocity` to detect ATO botnet activity. |

---

## Fraud signal patterns

### Automated Account Takeover (ATO)

```
device_is_emulator = true  AND  geo_velocity > 500
```

Emulators running credential-stuffing scripts generate physically impossible velocities as each "device" logs in from a different IP. This combination triggers `REQUIRE_VIDEO_ID`.

### Social-Engineering / Pig Butchering

```
typing_entropy < 1.0  AND  amount > 5000
```

When a fraudster coaches a victim over the phone, the victim's typing patterns change — hesitation, copy-pasting amounts from a script, unnatural key-spacing. Low entropy on a high-value transfer is a strong coaching signal.

### Generative Synthetic Identity (GSI)

Detected primarily by the **Isolation Forest** model rather than deterministic rules. GSI accounts often share underlying device fingerprints or behavioral clusters that are statistically unusual — outliers from the normal transaction distribution — even when their identity documents pass KYC.

---

## Consortium signal (simulated)

| Signal | Type | Description |
|---|---|---|
| `consortium_match_count` | int | Number of other client accounts that have previously seen this device or typing pattern (cross-client network signal). |

`consortium_match_count` is simulated in the dashboard's shadow backtest. In a production deployment this would pull from a cross-client device graph (e.g. Sardine's consortium network). Policy rules can reference it once a real integration exists.

---

## Signal availability

| Signal | Real-time API | Batch / Feature Store |
|---|---|---|
| `amount` | Yes | Yes |
| `geo_velocity` | Yes | Yes |
| `typing_entropy` | Yes | Yes |
| `device_is_emulator` | Yes | Yes |
| `consortium_match_count` | Simulated | Would require feature store |
| `velocity_7d` | No (requires aggregation) | Yes |

Rules that reference batch-only signals will log a warning and be skipped at runtime. See [Feature Availability](../development/feature-registry.md).
