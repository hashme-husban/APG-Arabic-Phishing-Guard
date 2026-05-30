# APG Risk Intelligence Engine v1 — Design Reference

## Overview

The Risk Intelligence Engine v1 (RIE v1) is the primary analysis backend for APG starting with
`APG_ANALYZER_ENGINE=risk_engine_v1`. It replaces the simple text-classifier philosophy of v5
with **evidence-based risk intelligence**: every decision is backed by a set of named Evidence
objects, and a deterministic PolicyEngine decides the final verdict from those objects — not from
a raw ML score alone.

### Key principles

1. **Evidence first** — every claim about a message is an `Evidence` item with a source, a
   severity, a human-readable Arabic description, and a numeric `score_delta`.
2. **Policy decides** — the `PolicyEngine` applies explicit block rules, safe caps, and score
   thresholds in strict priority order. AI model scores are advisory only.
3. **Negation is handled explicitly** — "لا تشارك رمزك" is safe; "أرسل لنا رمزك" is dangerous.
4. **Backward compatible** — the public API still returns the same field names that the Flutter
   app and Web Admin expect; new fields are added alongside.

---

## Architecture

```
text + context
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                 RiskEngineV1Service.analyze_full()              │
│                                                                 │
│  1. normalize(text)           → normalized_text                 │
│  2. EntityExtractorAdapter    → entities + raw signals          │
│  3. ActionDetectorAdapter     → intent_result + context         │
│  4. URLIntelligenceAnalyzer   → url_intel (+ Evidence items)    │
│  5. SenderIntelligenceAnalyzer→ sender_assessment               │
│  6. classify_message()        → message_category                │
│  7. build_all_evidence()      → list[Evidence]                  │
│  8. AIAdvisoryAnalyzer        → ai_assessment (advisory only)   │
│  9. PolicyEngine.decide()     → PolicyDecision                  │
│ 10. explanation_builder       → primary_reason, recommendation  │
│ 11. collect privacy notes     → privacy_notes[]                 │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
  RiskResult  ──→  to_hybrid_result()  ──→  HybridResult (backward compat)
```

All v5 sub-components (normalizer, entity extractor, intent detector, context detector,
URL reputation, sender trust, AI adapter) are wrapped as thin adapters.  The v1 engine
**does not duplicate** their detection logic; it only adds the evidence layer and
policy engine on top.

---

## Package layout

```
backend/app/services/risk_engine/
├── __init__.py               exports RiskEngineV1Service, get_risk_engine_service
├── schemas.py                dataclasses: Evidence, URLIntelligence, SenderAssessment,
│                               AIAssessment, PolicyDecision, RiskResult
├── service.py                RiskEngineV1Service — orchestrates all steps
├── normalizer.py             thin adapter over v5 ArabicNormalizer
├── entity_extractor.py       EntityExtractorAdapter
├── action_detector.py        ActionDetectorAdapter
├── message_classifier.py     classify_message() → MessageCategory
├── url_intelligence.py       URLIntelligenceAnalyzer
├── url_providers.py          provider status helpers
├── sender_intelligence.py    SenderIntelligenceAnalyzer
├── ai_advisory.py            AIAdvisoryAnalyzer
├── evidence_builder.py       build_all_evidence() — assembles Evidence list
├── policy_engine.py          PolicyEngine.decide() — deterministic verdict
├── explanation_builder.py    build_primary_reason() — Arabic explanations
├── compatibility.py          to_hybrid_result(), to_backward_compatible_response()
└── config/
    ├── thresholds.yaml       score thresholds, safe caps, AI advisory thresholds
    ├── risk_policy.yaml      block rules, safe-allow rules, warn indicators
    ├── arabic_patterns.yaml  request verbs, negation words, indicator lists
    ├── trusted_domains.yaml  trusted domain list, suspicious URL patterns
    └── url_providers.yaml    provider configuration, SSRF protection
```

---

## Output model

### RiskResult (internal)

| Field | Type | Description |
|---|---|---|
| `verdict` | `allow \| caution \| warn \| block` | Internal verdict |
| `risk_level` | `none \| low \| medium \| high \| critical` | Risk level |
| `risk_score` | `int 0–100` | Numeric score |
| `confidence` | `float 0–100` | Decision confidence |
| `message_category` | see below | Inferred message category |
| `attack_type` | see below | Attack pattern if applicable |
| `user_action` | see below | Recommended user action |
| `evidence` | `list[Evidence]` | Evidence items driving the decision |
| `url_intelligence` | `URLIntelligence` | URL analysis results |
| `sender_assessment` | `SenderAssessment` | Sender trustworthiness |
| `ai_assessment` | `AIAssessment` | AI model advisory scores |
| `policy_trace` | `PolicyDecision` | Step-by-step policy log |
| `privacy_notes` | `list[str]` | Notes on external data consulted |

### HybridResult (backward compatible)

Original v5 fields are preserved exactly:
`classification`, `risk_score`, `reasons`, `matched_signals`,
`recommendation`, `detected_url`, `masked_text`, `analyzer_version`, `debug`.

New fields added alongside: `verdict`, `risk_level`, `confidence`,
`message_category`, `attack_type`, `user_action`.

### Verdict → classification mapping

| Internal verdict | classification (public) |
|---|---|
| `allow` | `safe` |
| `caution` | `suspicious` |
| `warn` | `suspicious` |
| `block` | `dangerous` |

---

## Message categories

`casual` · `transactional` · `awareness` · `otp_delivery` · `app_verification` ·
`account_notice` · `credential_request` · `link_action` · `brand_impersonation` ·
`phishing` · `unknown`

Classification follows a priority chain (phishing wins over transactional, etc.).

---

## Attack types

`none` · `otp_theft` · `password_theft` · `card_theft` · `bank_account_takeover` ·
`malicious_url` · `brand_impersonation` · `social_engineering` ·
`credential_harvesting` · `unknown`

---

## User actions

| Value | Arabic guidance |
|---|---|
| `no_action_needed` | لا حاجة لأي إجراء |
| `do_not_share_code` | لا تشارك رمز التحقق |
| `do_not_click_link` | لا تضغط على الروابط |
| `verify_from_official_app` | تحقق عبر التطبيق الرسمي |
| `contact_bank_directly` | تواصل مع البنك مباشرة |
| `report_message` | أبلغ عن هذه الرسالة |

---

## Policy engine — decision sequence

```
Phase 1: Block rules (any one match → verdict=block, short-circuit)
  B1  credential_request + otp          → otp_theft
  B2  credential_request + password      → password_theft
  B3  credential_request + card/cvv/pin  → card_theft
  B4  credential_request + account data  → bank_account_takeover
  B5  malicious_url signal               → malicious_url
  B6  ip_url + credential_request        → malicious_url

Phase 2: Safe caps (message_category restricts maximum score)
  awareness                    → cap 20
  otp_delivery                 → cap 25
  transactional                → cap 25
  app_verification             → cap 15
  casual (known contact)       → cap 10

Phase 3: Evidence score (sum of evidence.score_delta, clamped 0–100)
  Adjustments applied after base score:
    known contact              → −8
    unknown sender + financial → +6
    clean URL present          → −5

Phase 4: Verdict from score
  ≥ 76 → block   (dangerous)
  ≥ 55 → warn    (suspicious)
  ≥ 31 → caution (suspicious)
  <  31 → allow   (safe)

Phase 5: AI advisory (applied only when not safe_context and not clear block)
  AraBERT ≥ 65 or lexical ≥ 65 → adds up to +10 to score (advisory cap)
```

---

## URL intelligence

The `URLIntelligenceAnalyzer` wraps the v5 `URLReputationService`.  It extracts all
URLs from the message text, then:

1. **Structural checks** (always run, no network): shortener, IP address, punycode,
   suspicious TLD, brand keyword in path.
2. **Provider checks** (optional, network): Google Safe Browsing, VirusTotal,
   urlscan.io, PhishTank.  Each provider is skipped gracefully if its API key is not
   configured.
3. **Privacy notes** are added to `RiskResult.privacy_notes` whenever a URL is sent
   to an external provider.

### SSRF protection

Before expanding short URLs, the resolved IP is checked against blocked ranges:
`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`,
`::1`, `fc00::/7`.

### Provider configuration (`config/url_providers.yaml`)

```yaml
google_safe_browsing:
  enabled: true
  requires_key: GOOGLE_SAFE_BROWSING_API_KEY
virustotal:
  enabled: true
  requires_key: VIRUSTOTAL_API_KEY
urlscan:
  enabled: true
  requires_key: URLSCAN_API_KEY
phishtank:
  enabled: true
  requires_key: PHISHTANK_API_KEY
```

Missing key → provider silently skipped (not an error).

---

## Negation handling

The engine inherits negation handling from the v5 `IntentDetector._has_local_negation()`
and `ContextDetector`.  A negation word (`لا`, `لن`, `لم`, `لا تشارك`, `لا تعطي`, …)
within 4 tokens of a request verb sets `intent_result.safe_context = True`.

When `safe_context` is True:
- No block rule is triggered for OTP/password requests.
- Evidence builder adds a negative-score evidence item (`score_delta` −6 to −10).
- Policy engine skips AI advisory adjustment.

This ensures "لا تشارك رمز التحقق" scores ≤ 20 (safe).

---

## How to add patterns

Edit `config/arabic_patterns.yaml` for text patterns.  All values are also hard-coded
as Python fallbacks in `evidence_builder.py` so the system works without PyYAML.

```yaml
request_verbs:        # verbs that indicate credential request (Arabic + Latin)
negation_words:       # words that negate the nearest request verb
awareness_indicators: # words that shift category toward "awareness"
otp_delivery_indicators:  # words marking a legitimate OTP delivery message
```

After editing, restart the engine (or call `get_risk_engine_service.cache_clear()`).

---

## How to add test cases

1. Open `tests/fixtures/risk_engine_cases.json`.
2. Append a JSON object following this schema:

```json
{
  "id": "my_cat_NNN",
  "category": "my_category",
  "description": "What this case tests",
  "text": "Arabic message text",
  "source": "sms|whatsapp|email|notification",
  "sender": "SENDERNAME",
  "sender_name": "Friendly name",
  "is_known_contact": false,
  "mock_url_reputation": {
    "is_safe": false,
    "reputation_score": 85,
    "categories": ["phishing"]
  },
  "expected": {
    "classification": "safe|suspicious|dangerous",
    "min_risk_score": 80,
    "max_risk_score": 30,
    "message_category": "otp_delivery",
    "verdict": "block"
  }
}
```

Only `id`, `category`, `text`, and `expected.classification` are required.

---

## Admin explain endpoint

`POST /api/admin/analyzer/explain` (admin token required)

Request body:
```json
{ "text": "...", "source": "sms", "sender": "...", "is_known_contact": false }
```

Response (risk_engine_v1 active):
```json
{
  "original_text": "...",
  "normalized_text": "...",
  "extracted_entities": { ... },
  "detected_actions": { ... },
  "message_category": "phishing",
  "evidence": [ { "id": "...", "description": "...", "score_delta": 35 } ],
  "url_intelligence": { ... },
  "sender_assessment": { ... },
  "ai_assessment": { ... },
  "policy_trace": { "block_rule": "credential_request_otp", "score": 92 },
  "final_internal_result": { ... },
  "backward_compatible_result": { ... }
}
```
