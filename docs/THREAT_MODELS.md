# **SentryFlow Defense Strategy**

## **1. Attack Vector: AI-Augmented Social Engineering**

* **The Threat:** Fraudsters use LLM-driven voice/text clones to coach legitimate users into authorizing "Pig Butchering" or romance scam wires. The user is "real," but the intent is fraudulent.
* **SentryFlow Defense:**
* **Signal:** **Typing Entropy (DIBB).** Even if the user is real, their typing patterns change when being coached (hesitation, copy-pasting from a script).
* **Action:** Rule triggers `REQUIRE_VIDEO_ID` if `typing_entropy` falls below a baseline during a high-value wire, breaking the fraudster’s rapport with the victim.

## **2. Attack Vector: Generative Synthetic Identity (GSI)**

* **The Threat:** Fraudsters use AI to generate "perfect" identity documents and deepfake faces that bypass traditional KYC. These identities have no prior history but look "clean" to legacy vendors.
* **SentryFlow Defense:**
* **Signal:** **Isolation Forest (Unsupervised ML).** Since GSI identities often share underlying generative patterns or originate from similar device clusters, the Isolation Forest flags them as "outliers" despite having "clean" credit scores.
* **Action:** `ML_OVERRIDE_CRITICAL` logic escalates these to manual review or 48-hour holds.

## **3. Attack Vector: Automated Account Takeover (ATO)**

* **The Threat:** High-velocity botnets use leaked credentials and emulators to "brute force" logins and drain accounts.
* **SentryFlow Defense:**
* **Signal:** **Geo-Velocity + Device State.** * **Logic:** `{"and": [{"==": [{"var": "device_is_emulator"}, True]}, {">": [{"var": "geo_velocity"}, 500]}]}`.
* **Action:** Immediate `DECLINE` with Nacha `R03` code, blacklisting the device hash across the local network.

## **4. Attack Vector: Regulatory "Failure to Prevent" (Nacha 2026)**

* **The Threat:** Under new 2026 rules, if a neobank cannot prove they had proactive monitoring for "false pretenses," they face 100% liability for the loss + federal fines.
* **SentryFlow Defense:**
* **Mechanism:** **Immutable Audit Trail.**
* **Proof:** Every decision is signed with a `policy_signature`. This allows the legal team to present a "Defensible Intelligence" packet to regulators showing the exact versioned logic used to mitigate the loss.