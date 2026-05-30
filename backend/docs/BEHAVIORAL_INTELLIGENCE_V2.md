# APG Behavioral Intelligence v2

## Overview

Behavioral Intelligence v2 organizes Arabic phishing and smishing behavior into
named phrase families, then scores only controlled combinations. The goal is to
improve coverage for account takeover, OTP theft, payment scams, wallet freeze,
delivery/customs fraud, fake government service messages, bank KYC lures,
WhatsApp/social takeover, and prize scams without making promotional or
awareness text dangerous by itself.

The layer remains additive and policy-driven: it does not change global
thresholds, and it does not weaken credential, OTP, card, or URL protections.

## Phase 4.4 Closure Status

Phase 4 is **COMPLETE**.

Closure quality gate:

- Behavioral v2 evaluation: `128/128` passed
- Promo/discount false-positive pack: `12/12` passed
- Dynamic sandbox regression pack: `39/39` passed
- Same-family duplicate phrases: `0`
- Intentional cross-family duplicate phrases: `4`
- Under-covered v2 families below 20 phrases: `0`
- Loaded v2-family phrase count: `405`

## Files And Functions

| File | Role |
|------|------|
| `app/data/ar_behavioral_phrases.json` | Phrase dictionary and v2 family data |
| `app/services/risk_engine/behavioral_detector.py` | Loads phrase families and emits behavioral evidence |
| `app/services/risk_engine/service.py` | Calls `detect_behavioral_phishing()` after core evidence is built |
| `app/services/risk_engine/policy_engine.py` | Applies existing block rules, caps, and thresholds |
| `scripts/evaluate_behavioral_v2.py` | 128-case v2 dialect/sector quality gate |
| `scripts/evaluate_behavioral_false_positives.py` | Phase 4.1 promo/discount regression pack |

## Dictionary Structure

The current JSON contains 22 top-level keys.

| Key | Count | Loaded by detector |
|-----|------:|--------------------|
| `account_state_terms_ar` | 163 | Yes |
| `action_terms_ar` | 187 | Yes |
| `urgency_terms_ar` | 76 | Yes |
| `safe_guardrail_terms_ar` | 110 | Yes |
| `safe_service_patterns_ar` | 114 | Yes |
| `account_takeover_terms_ar` | 33 | Yes |
| `otp_theft_terms_ar` | 32 | Yes |
| `password_theft_terms_ar` | 29 | Yes |
| `payment_fee_terms_ar` | 32 | Yes |
| `wallet_freeze_terms_ar` | 33 | Yes |
| `delivery_customs_terms_ar` | 32 | Yes |
| `fake_government_terms_ar` | 29 | Yes |
| `bank_kyc_update_terms_ar` | 26 | Yes |
| `whatsapp_takeover_terms_ar` | 23 | Yes |
| `social_account_terms_ar` | 24 | Yes |
| `prize_reward_scam_terms_ar` | 26 | Yes |
| `subscription_suspension_terms_ar` | 25 | Yes |
| `safe_promo_terms_ar` | 20 | Yes |
| `safe_receipt_terms_ar` | 20 | Yes |
| `safe_awareness_terms_ar` | 21 | Yes |
| `dangerous_behavior_examples` | 40 | No, documentation/evaluation examples |
| `safe_lookalike_examples` | 40 | No, documentation/evaluation examples |

Some phrases intentionally overlap between the original broad buckets and the
new family buckets. The runtime loader normalizes all phrases and matches each
family independently, so duplicate content is acceptable when it documents a
specific behavior family.

Phase 4.3 added 180 phrases across v2 family keys. Phase 4.4 removed exact
same-family duplicates and added narrow finishing phrases for previously
under-covered families. The loaded v2-family count is now 405 phrases.

## Duplicate Policy

- Exact duplicates inside the same v2 family are removed during closure cleanup.
- Cross-family duplicates are allowed when one phrase legitimately supports
  separate family reporting, such as OTP theft and WhatsApp takeover.
- The current intentional cross-family overlaps are:
  `كود واتساب`, `انقل رمز الواتساب`, `رسوم إعادة التوصيل`,
  and `ادفع رسوم رمزية`.
- Legacy broad buckets are left intact unless a phrase is clearly unused and
  safe to remove in a future cleanup phase.

## Dialect And Sector Expansion

Phase 4.3 expands coverage with Jordanian, Gulf, Egyptian, MSA, and mixed
Arabic variants. The new phrases target realistic sector-specific lures while
keeping broad words non-dangerous unless they appear in a controlled
combination.

| Dialect tag | Purpose |
|-------------|---------|
| `msa` | Formal/common Arabic variants |
| `jordanian` | Jordanian colloquial forms such as "رح يتوقف", "ابعت", "فوت" |
| `gulf` | Gulf/common service wording |
| `egyptian` | Egyptian forms such as "هيتقفل" and "اكتب كلمة السر" |
| `mixed` | English/Arabic forms such as KYC, Meta Business, CVV, CVC |

| Sector tag | Coverage examples |
|------------|-------------------|
| `bank` | KYC, account update, card/payment collection |
| `telecom` | bundle/account suspension and OTP/login lures |
| `wallet` | Zain Cash, Orange Money, CliQ, held transfers |
| `delivery` | parcel delivery, customs, address update, redelivery fees |
| `government` | support requests, fines, tax, government transaction completion |
| `social` | WhatsApp, Facebook, Instagram, Meta Business takeover |
| `prize` | winner confirmation, symbolic fees, reward collection |
| `subscription` | package renewal, service disconnection, subscription recovery |
| `awareness` | educational anti-phishing messages |
| `promo` | discount/coupon offers without data collection |
| `receipt` | payment, bill, wallet, and delivery confirmations |

## Dangerous Combinations

The v2 family rules are combination-based. Broad family words are not scored
alone.

| Family | Combination Required | Evidence ID |
|--------|----------------------|-------------|
| Account takeover | Account-state family + action marker + URL/link surface | `behavioral_account_takeover_v2` |
| Wallet freeze | Wallet/fund freeze family + action marker + URL/link surface | `behavioral_wallet_freeze_reactivation` |
| Bank KYC/update | Bank/KYC family + action marker + URL/link surface | `behavioral_bank_kyc_update` |
| WhatsApp/social takeover | WhatsApp/social family + credential/OTP/action context | `behavioral_whatsapp_social_takeover` |
| Delivery/customs fee | Delivery/customs family + payment/fee context + URL/link surface | `behavioral_delivery_customs_fee` |
| Fake government | Government/service/fee family + action/payment context + URL/link surface | `behavioral_fake_government_payment` |
| Prize/reward scam | Prize/reward family + action/payment/credential context + URL/link surface | `behavioral_prize_reward_phishing` |
| Subscription suspension | Subscription/service suspension family + action marker + URL/link surface | `behavioral_subscription_suspension` |

Existing core detections still cover direct credential requests:

- `danger_otp_request`
- `danger_password_request`
- `danger_card_request`
- `behavioral_account_takeover_url`
- `behavioral_payment_phishing`

## False-Positive Protections

1. Safe awareness/service reductions are still suppressed only when a real
   dangerous request exists.
2. Promo and discount language remains separated from financial-risk context by
   the Phase 4.1 entity adapter cleanup.
3. Prize, reward, promo, or discount wording alone does not create dangerous
   evidence.
4. Safe receipt and OTP delivery examples are covered in regression tests and
   must not become dangerous.
5. V2 family evidence requires combinations such as action + URL, sensitive
   request, or payment/fee context.

## Evaluation

Run:

```bash
cd backend
python scripts/evaluate_behavioral_v2.py
python scripts/evaluate_behavioral_false_positives.py
python scripts/evaluate_dynamic_url_sandbox.py
```

The v2 evaluation contains 128 synthetic cases:

| Group | Count |
|-------|------:|
| Dangerous/suspicious phishing behavior | 64 |
| Safe lookalikes | 64 |
| Total | 128 |

Columns:

```text
case_id | family | dialect | sector | expected | score | class | intent | category | top_evidence_ids | pass/fail
```

Pass criteria:

- Credential, OTP, card, account, wallet, delivery/customs, government, KYC,
  WhatsApp/social, and prize/reward phishing cases must be suspicious or
  dangerous according to the case expectation.
- Safe promo, safe receipt, safe awareness, and OTP delivery cases must not be
  dangerous.
- New family evidence must not regress the Phase 4.1 promo false-positive pack.
- Phase 3 dynamic URL sandbox evaluation must remain green.

The evaluator also prints a non-failing phrase audit:

- total loaded v2-family phrases
- phrase families with fewer than 20 phrases
- top duplicate phrases
- short-phrase warnings, excluding known acronyms such as OTP, CVV, PIN, KYC,
  and CliQ

It also prints the Phase 4 quality gate footer:

```text
PHASE_4_STATUS: COMPLETE
total_cases
pass_count
fail_count
loaded_v2_phrase_count
undercovered_families
duplicate_summary
dialect_coverage
sector_coverage
regression_status
```

Quality gate commands:

```bash
cd backend
python -m py_compile app/services/risk_engine/behavioral_detector.py scripts/evaluate_behavioral_v2.py
python scripts/evaluate_behavioral_v2.py
python scripts/evaluate_behavioral_false_positives.py
python scripts/evaluate_dynamic_url_sandbox.py
```

## Adding Future Phrases Safely

1. Add phrases only to the most specific v2 family key.
2. Avoid one-word broad phrases unless they are unavoidable sector terms and
   protected by combination logic.
3. Add at least one dangerous/suspicious case for the new phrase family.
4. Add at least one safe lookalike that uses similar vocabulary but no malicious
   request.
5. Run all three regression packs before merging:
   `evaluate_behavioral_v2.py`, `evaluate_behavioral_false_positives.py`, and
   `evaluate_dynamic_url_sandbox.py`.
6. Do not change thresholds or policy rules just to make a new phrase pass.

## Known Limitations

- Dialect coverage is broader after Phase 4.3 but still conservative; more
  telemetry-backed Jordanian, Gulf, Egyptian, Levantine, and North African
  variants should be added with safe lookalikes.
- Some suspicious government, delivery, and prize cases remain caution-level
  unless another strong signal is present. This is deliberate until more
  production telemetry is available.
- The dictionary still contains duplicate phrases across broad buckets and v2
  family buckets. These are useful for family reporting but can be deduplicated
  later if tooling needs a cleaner audit view.
- Safe-family buckets now meet the Phase 4.4 minimum of 20 phrases, but they
  should continue to grow alongside future dangerous phrase additions.
