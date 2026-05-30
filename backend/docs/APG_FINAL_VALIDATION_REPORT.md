# APG Final Validation Report

**System:** APG — Arabic Phishing Guard  
**Validation date:** 2026-05-25  
**Last updated:** 2026-05-25 (Phase 7.5 — High-Priority Registry Coverage Closure)  
**Status:** `FINAL_VALIDATION_STATUS: PASS`

---

## 1. Executive Summary

APG is a layered Arabic phishing and smishing detection system designed for the
Jordanian and broader Arab market. It classifies Arabic-language messages as
safe, suspicious, or dangerous using five coordinated layers:

| Layer | Role |
|-------|------|
| **Behavioral Intelligence** | Detects attack-family phrase combinations (account takeover, OTP theft, payment scams, wallet freeze, delivery fraud, fake government, bank KYC, social hijacking, prize scams) |
| **Entity Intelligence** | Identifies claimed organizations via an entity registry (aliases, official domains, official senders, forbidden requests) |
| **URL Intelligence** | Evaluates domain reputation, brand impersonation, structural anomalies, and path keywords |
| **Dynamic URL Sandbox** | Optional Playwright-based live page inspection for login forms, password fields, OTP fields, and delayed redirects |
| **Policy-based Scoring** | A priority-ordered rule engine translating evidence into a final risk score with explainable output |

Each layer produces structured `Evidence` items. The policy engine aggregates
them, applies definite-block rules and calibrated caps, and returns a
`PolicyDecision` with `risk_score`, `classification`, `policy_trace`,
`score_breakdown`, and `matched_signals` — making every decision auditable.

---

## 2. Completed Engineering Phases

### Phase 3 — Dynamic URL Sandbox

Introduced an optional Playwright-based sandbox invoked after URL intelligence.
The sandbox runs in two operating modes (shadow and scoring) controlled by
environment flags:

- **Shadow mode** (`DYNAMIC_URL_ANALYSIS_ENABLED=true`): sandbox executes and
  populates `debug.dynamic_url_analysis.evidence_preview` but never changes the
  risk score or classification.
- **Conservative scoring mode** (`DYNAMIC_URL_ANALYSIS_SCORE_ENABLED=true`):
  sandbox evidence may enter the main evidence list only when a strict signal
  combination gate passes (password field + risk signal, OTP field + context,
  delayed redirect + hard mismatch, or domain-changed login + context). Evidence
  is capped at 3 items and a maximum total delta of 45 points.

Phase 3.2 fixed a static false positive: the Arabic brand name `زين` (Zain
telecom) was matching as a substring inside `المميزين` ("distinguished/premium
customers") in promotional messages. A single-line word-boundary regex fix
(`\b` in `_brand_alias_in_text`) eliminated the false impersonation detection
while preserving real Zain impersonation detection when `زين` appears as a
standalone word.

### Phase 4 — Behavioral Intelligence v2

Restructured the behavioral phrase dictionary into named attack families and
replaced the free phrase list with controlled combination detection. Each
evidence item fires only when its trigger combination (account-state term +
action term + optional urgency) is present. Safe guardrail terms and safe
service patterns suppress firing when the message is clearly informational or
educational.

Expansion covered 12 v2 phrase families with dialect and sector variations
across Levantine, Gulf, and North African Arabic, plus Jordanian financial
sector terminology (CLIQ, eFAWATEERcom, USSD, STC Pay, SANAD, etc.).

### Phase 5 — Entity Intelligence v2

Built a structured entity registry (`jo_entities.json`) covering 83
organizations across Jordan, the MENA region, and global platforms. Five
sub-phases hardened the layer:

| Sub-phase | Change |
|-----------|--------|
| 5.1 | Evaluation pack and registry quality gate |
| 5.2 | Boundary-aware alias matching, exact-only sender matching |
| 5.3 | Forbidden-request hardening (15 canonical credential types mapped to entity types) |
| 5.4 | Duplicate official domain policy (7 groups: shared domains resolved to multiple entities) |
| 5.5 | Registry-backed URL brand bridge (extends `url_intelligence.py` brand impersonation to all 83 registry entities without modifying `_KNOWN_BRANDS`) |

### Phase 7.2 — Healthcare + Education Registry Expansion Batch 1

Expanded the entity registry from 83 to 103 entities. Added 10 healthcare
entities (hospitals, cancer centers, and diagnostic labs operating in Jordan)
and 10 education/university entities (major public and private Jordanian
universities). Added 120 new defensive evaluation cases (6 per entity) covering
official domain alignment, fake domain impersonation, forbidden credential
requests, safe awareness messages, alias substring regression, and sender
spoofing.

### Phase 7.3 — Government + Delivery/Logistics Registry Expansion Batch 1

Expanded the entity registry from 103 to 117 entities. Added 8 government
entities (Ministry of Finance, Ministry of Education, Ministry of Labor, TRC,
JFDA, JSC, NITC, JIC) and 6 delivery/logistics entities (FedEx, UPS, Fetchr,
iMile, Shipa, Bosta). Added 84 new defensive evaluation cases (6 per entity)
covering the same 6 case families per entity. Government coverage rose from 14
to 22 entities; delivery/logistics from 5 to 11 entities.

### Phase 7.4 — Ecommerce + Payment + Wallet + Ride-hailing Registry Expansion Batch 1

Expanded the entity registry from 117 to 130 entities. Added 5 ecommerce
entities (AliExpress, Namshi, Max Fashion, Wolt, Temu), 2 payment network
entities (American Express, UnionPay), 3 payment gateway entities (Checkout.com,
Telr, HyperPay), 1 e-wallet entity (Samsung Pay), and 2 ride-hailing entities
(InDrive, Yango). Added 78 new defensive evaluation cases (6 per entity) covering
official domain alignment, fake domain impersonation, forbidden credential
requests, safe awareness messages, alias substring regression, and sender spoofing.
Payment gateway coverage reached target (10/10+); ecommerce rose from 8 to 13,
payment network from 2 to 4, e-wallet from 5 to 6, ride-hailing from 2 to 4.

### Phase 7.5 — High-Priority Registry Coverage Closure

Expanded the entity registry from 130 to 149 entities. Added 5 healthcare
entities, 10 education/university entities, 3 government/public-service
entities, and 1 delivery/logistics entity using verified official domains.
Added 114 new defensive evaluation cases (6 per entity) covering official
domain alignment, fake domain impersonation, forbidden credential requests,
safe awareness messages, alias non-overmatch, and sender spoofing. Healthcare,
education/university, government, and delivery/logistics now meet the current
high-priority coverage targets.

---

## 3. Final Evaluation Results

All evaluation packs were run against the live risk engine on 2026-05-25
with no mock scoring logic, using only mocked URL reputation verdicts and
mocked Playwright sandbox responses where applicable.

| Evaluation Pack | Cases | Result |
|---|---:|---|
| Entity Intelligence v2 (incl. Phase 7.2 + 7.3 + 7.4 + 7.5 + 7.6) | 612 | 612/612 PASS |
| Behavioral Intelligence v2 | 128 | 128/128 PASS |
| Promo False-Positive Pack | 12 | 12/12 PASS |
| Dynamic URL Sandbox Pack | 39 | 39/39 PASS |
| **Total** | **791** | **791/791 PASS** |

```
PHASE_4_STATUS: COMPLETE
PHASE_5_STATUS: COMPLETE
FINAL_VALIDATION_STATUS: PASS
```

---

## 4. Behavioral Intelligence Summary

### Phrase Dictionary

| Statistic | Value |
|-----------|------:|
| Loaded v2-family phrase count | 405 |
| Phrase families | 12 |
| Same-family duplicates | 0 |
| Intentional cross-family duplicates | 4 |
| Families below 20 phrases | 0 |

### Attack Families

| Family | Description |
|--------|-------------|
| `account_takeover_terms_ar` | Account suspension, freeze, verification lures |
| `otp_theft_terms_ar` | Fake OTP delivery and forwarding requests |
| `password_theft_terms_ar` | Password and PIN request patterns |
| `payment_fee_terms_ar` | Fake delivery, customs, and payment fee demands |
| `wallet_freeze_terms_ar` | Digital wallet suspension and reactivation fraud |
| `delivery_customs_terms_ar` | Parcel held, customs clearance, release fee |
| `fake_government_terms_ar` | Government service impersonation, e-document fraud |
| `bank_kyc_update_terms_ar` | Bank KYC, account update, data re-verification |
| `whatsapp_takeover_terms_ar` | WhatsApp/Telegram session hijacking |
| `social_account_terms_ar` | Social media account compromise |
| `prize_lottery_terms_ar` | Lottery win, prize collection, lucky draw |
| `real_estate_rental_terms_ar` | Rental deposit fraud, housing scams |

### Key Design Decisions

- **No phrase-only danger classification.** A behavioral family fires only when
  a trigger combination is present (account-state + action term). A single
  urgency word or account word alone does not elevate the score.
- **Safe guardrail suppression.** When a message contains safety-advice phrases
  ("do not share your OTP", "we will never ask for your password"), behavioral
  evidence is suppressed.
- **Safe service pattern suppression.** Transaction receipts, renewal
  confirmations, and delivery status updates are recognized as safe service
  patterns and do not fire behavioral rules.
- **Dialect coverage.** Levantine, Gulf, Egyptian, and North African Arabic
  variants are represented in all families, as are Jordanian financial sector
  terms specific to CLIQ, eFAWATEERcom, USSD codes, and SANAD.

---

## 5. Entity Intelligence Summary

### Registry Statistics (Phase 7.6 baseline)

| Statistic | Value |
|-----------|------:|
| Total entities | 166 |
| Total aliases | 884 |
| Total official domains | 191 |
| Total official sender names | 325 |
| Total forbidden request entries | 1067 |
| Total allowed message types | 997 |
| Duplicate domain groups | 9 |
| Missing domains | 0 |

### Entity Coverage

| Type | Count |
|------|------:|
| Bank | 15 |
| Government | 25 |
| Healthcare | 15 |
| Education/university | 20 |
| Delivery/logistics | 12 |
| E-commerce | 15 |
| Social platform | 10 |
| Payment gateway | 10 |
| Utilities | 10 |
| E-wallet | 8 |
| Streaming/subscription | 8 |
| Telecom | 5 |
| Technology | 3 |
| Ride-hailing | 5 |
| Payment network | 5 |

### Key Design Decisions

**Boundary-aware alias matching.** Aliases are matched using whole-word
boundary checks (regex `\b` for Arabic Unicode). This prevents short Arabic
brand names from matching as substrings of unrelated words. For example, `زين`
(Zain) no longer matches inside `المميزين` ("premium customers").

**Exact-only sender matching.** Sender names are matched exactly
(after normalization) rather than as substrings, preventing over-broad sender
attribution that could produce false negatives on spoofed senders or false
positives on common words.

**Forbidden-request hardening.** Each entity type maps to a set of credentials
it should never request (passwords, PINs, OTPs, card numbers, CVVs, IBAN, etc.).
When a message claims to be from a known entity and requests a forbidden
credential, a high-severity block evidence item is generated.

**Duplicate official domain policy.** Seven domain groups are shared by
multiple entities (e.g., `orange.jo` is used by both Orange Jordan and Orange
Money Jordan). The registry resolves these to all matching entities so that
safe messages are not misclassified and impersonation checks remain accurate.

**Registry-backed URL brand bridge.** URL intelligence now queries the entity
registry when checking for brand impersonation in URLs. This extends impersonation
detection to all 83 registry entities without requiring them to be added to the
legacy `_KNOWN_BRANDS` list in `url_intelligence.py`.

---

## 6. Dynamic Sandbox Summary

### Operating Modes

| Mode | Env Flags | Sandbox Runs | Score Changed |
|------|-----------|:------------:|:-------------:|
| Disabled | `ENABLED=false` | No | No |
| Shadow | `ENABLED=true` | Yes | No |
| Scoring | Both `=true` | Yes | If gate passes |

### Conservative Gate Conditions

Sandbox evidence enters scoring only when one of these combinations is present:

| # | Combination | Required co-signal |
|---|-------------|-------------------|
| 1 | Password field | Brand impersonation, suspicious/malicious URL, domain change, ≥2 suspicious external requests, or account/credential context |
| 2 | OTP field | OTP-request intent, account context, brand impersonation, or domain change |
| 3 | Delayed redirect or sensitive form after delay | Domain change, brand impersonation, or suspicious URL |
| 4 | Domain changed + login form | Brand impersonation or account/credential context |

### Evidence Caps

| Limit | Value |
|-------|------:|
| Max evidence items selected | 3 |
| Max individual item delta | 28 pts |
| Max total sandbox delta | 45 pts |

Sandbox evidence is always `category = "suspicious_context"` and cannot
trigger definite-block rules on its own. Production default: both flags `false`.

### Evaluation

The 39-case sandbox evaluation pack verified:
- Shadow mode never changes `risk_score` or `classification` (P1, P2)
- Gate-blocked cases produce identical scores to disabled mode (P3)
- SAFE-category cases never become dangerous via sandbox alone (P4)
- Scores never exceed 100 (P5)
- Disabled/shadow score_impact is always `none_shadow_mode` (P6)

---

## 7. False Positive Protections

APG applies multiple independent layers to prevent over-classification of
benign messages:

| Protection | Mechanism |
|------------|-----------|
| **Promotional messages** | `_OFFICIAL_SAFE_CAPS["promotional"] = 30` applies when no dangerous request is present. The `advertisement` intent cap (30) provides an additional backstop via `_INTENT_SAFE_CAPS`. |
| **VT-confirmed clean URLs** | When a URL reputation provider returns "clean" and no sensitive entities, urgency, or brand impersonation are present, score is capped at 25 (safe). |
| **Receipts and service notices** | `payment_receipt`, `service_notification`, `subscription_notice` category caps (25–30) keep transaction and renewal messages in the safe range. |
| **Safe awareness messages** | Messages warning users not to share credentials trigger `intents.awareness` and a cap at 20. |
| **OTP delivery messages** | Messages delivering a one-time code (without requesting it) are capped at 22–25. |
| **Official domains** | Messages linking to trusted official domains (`_is_trusted_domain`) are capped at 30 when no dangerous collection is present. |
| **Shared official domains** | Duplicate-domain policy ensures that a domain shared by multiple legitimate entities (e.g., `orange.jo`) produces the correct entity attribution for all of them. |
| **Short alias substring false positives** | Word-boundary regex matching prevents short Arabic brand names (e.g., `زين`, 3 chars) from matching as suffixes inside longer unrelated Arabic words (e.g., `المميزين`). |
| **Behavioral safe guardrails** | Safe-advice phrases and service-pattern terms suppress behavioral phishing rules when the message is clearly educational or transactional. |
| **Sandbox evidence cap** | Sandbox evidence is bounded to 3 items and ≤ 45 total delta points, preventing it from dominating the score. |
| **`suspicious_context` only** | All sandbox evidence uses `category = "suspicious_context"` and cannot satisfy definite-block rule conditions that require `dangerous_intent`. |

---

## 8. Explainability

Every APG decision is accompanied by structured explainability output:

| Field | Description |
|-------|-------------|
| `risk_score` | Numeric score 0–100 |
| `classification` | `safe` / `suspicious` / `dangerous` |
| `verdict` | `allow` / `caution` / `warn` / `block` |
| `policy_trace` | Ordered list of rule steps applied (CAP, BLOCK, SCORE, FINAL) |
| `score_breakdown` | Base score, floors applied, caps applied, adjustments, and per-signal deltas |
| `matched_signals` | Each evidence item with ID, category, severity, score delta, confidence, and Arabic explanation |
| `evidence` (internal) | Full structured evidence list passed to the policy engine |
| `debug.dynamic_url_analysis` | Sandbox state, scoring gate result, evidence preview, and score impact label |
| `attack_type` | Inferred attack category (credential harvesting, OTP theft, bank account takeover, etc.) |
| `user_action` | Recommended user action in Arabic (do not click link, do not share code, contact bank, etc.) |

This level of explainability supports:
- **Academic validation**: Each classification is reproducible from first
  principles using the policy trace and evidence IDs.
- **User trust**: End users receive an Arabic explanation (`explanation_ar`) for
  why a message was flagged.
- **Operator review**: Ops teams can inspect `policy_trace` and `score_breakdown`
  to verify no false-positive rate drift.
- **Thesis documentation**: All scoring decisions are deterministic and audit-
  trailable, suitable for inclusion in system evaluation appendices.

---

## 9. Remaining Future Work

The following items were intentionally scoped out of Phases 3–5 and are
non-blocking future work:

| Item | Notes |
|------|-------|
| `allowed_message_types` runtime decision | Currently stored per entity but not yet used to suppress false positives at scoring time. Wire-up would allow entity-aware context suppression. |
| Registry categories | Phase 7.6 closes the current high-, medium-, and lower-priority coverage targets. Future additions should still require verified official domains and 6 evaluator cases per entity. |
| Arabic-localized aliases for Phase 7.6 entities | Some Phase 7.6 entities use conservative ASCII aliases only because Arabic literals could not be safely preserved during editing. Add Arabic aliases later only with encoding-safe tooling and evaluator coverage. |
| `_KNOWN_BRANDS` cleanup | `url_intelligence.py` still contains a legacy `_KNOWN_BRANDS` dict. Now that the registry bridge is in place, the legacy dict could be generated from the registry or removed incrementally. |
| Real-world telemetry calibration | All thresholds and evidence deltas are set analytically. Calibration against production message samples (opt-in, anonymized) would allow data-driven threshold tuning. |
| Dynamic sandbox Playwright deployment | The sandbox Playwright integration exists and is tested but is not deployed to production. A phased rollout (shadow mode first, scoring mode after stability confirmation) is recommended. |

---

## 10. Commands To Reproduce

```bash
cd backend

# Individual evaluation packs
python scripts/evaluate_entity_intelligence_v2.py
python scripts/evaluate_behavioral_v2.py
python scripts/evaluate_behavioral_false_positives.py
python scripts/evaluate_dynamic_url_sandbox.py

# All packs in one pass
python scripts/run_final_validation.py
```

Expected output from `run_final_validation.py`:

```
============================================================
  APG — Final Validation Runner
============================================================

  Running: Entity Intelligence v2 ...        PASS (612 passed, 0 failed)
  Running: Behavioral Intelligence v2 ...    PASS (128 passed, 0 failed)
  Running: Promo False-Positive Pack ...     PASS (12 passed, 0 failed)
  Running: Dynamic URL Sandbox ...           PASS (39 passed, 0 failed)
  Running: Registry Expansion Audit ...      PASS (WARN=27)

------------------------------------------------------------
  entity_result                PASS
  behavioral_result            PASS
  promo_fp_result              PASS
  sandbox_result               PASS
  registry_expansion_audit     PASS (WARN=27)  [informational]
------------------------------------------------------------
  total_cases_across_packs     791
  total_passed                 791
  total_failed                 0

  PHASE_5_STATUS               COMPLETE
  PHASE_4_STATUS               COMPLETE

  FINAL_VALIDATION_STATUS:     PASS
============================================================
```
