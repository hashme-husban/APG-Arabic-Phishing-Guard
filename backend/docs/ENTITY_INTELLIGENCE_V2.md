# APG Entity Intelligence v2

## Overview

Entity Intelligence v2 is the Jordan-first layer for identifying which
organization a message claims to represent, whether the URL belongs to that
organization, whether the sender name aligns with the claim, and whether the
message asks for data the claimed entity should never request through SMS,
WhatsApp, chat, or untrusted links.

Phase 5.1 added an evaluation pack and registry quality gate. Phase 5.2 added
matching-precision fixes. Phase 5.3 closed forbidden-request gaps. Phase 5.4
added duplicate official domain policy. Phase 5.5 bridges URL brand
intelligence to the entity registry while keeping legacy `_KNOWN_BRANDS`
compatibility. No scoring thresholds, `policy_engine.py` rules, sandbox logic,
Behavioral Intelligence v2 logic, or registry data were changed.

**Phase 5 status: COMPLETE.** Phase 5.6 is the final closure gate: it verifies
all entity, behavioral, promo false-positive, and dynamic sandbox regression
packs together and documents remaining work as future scope rather than a Phase
5 blocker.

## Phase 5 Closure Summary

| Phase | Result |
|-------|--------|
| 5.1 Entity evaluator and registry quality gate | Complete |
| 5.2 Boundary-aware alias matching and exact-only sender matching | Complete |
| 5.3 Forbidden-request hardening | Complete |
| 5.4 Duplicate official domain policy | Complete |
| 5.5 Registry-backed URL brand bridge | Complete |
| 5.6 Closure gate and documentation alignment | Complete |

Final quality gate:

| Gate | Result |
|------|--------|
| Entity evaluator | 612/612 PASS |
| Alias substring regression | 10/10 PASS |
| Sender spoofing | 10/10 PASS |
| Sender precision | 4/4 PASS |
| Forbidden request cases | 12/12 PASS |
| Safe awareness cases | 12/12 PASS |
| Duplicate domain policy | implemented, 10/10 PASS |
| Registry URL brand bridge | implemented, 20/20 PASS |
| Healthcare batch 1 (10 entities) | 60/60 PASS |
| Education/university batch 1 (10 entities) | 60/60 PASS |
| Government batch 1 (8 entities) | 48/48 PASS |
| Delivery/logistics batch 1 (6 entities) | 36/36 PASS |
| Ecommerce batch 1 (5 entities) | 30/30 PASS |
| Payment network batch 1 (2 entities) | 12/12 PASS |
| Payment gateway batch 1 (3 entities) | 18/18 PASS |
| E-wallet batch 1 (1 entity) | 6/6 PASS |
| Ride-hailing batch 1 (2 entities) | 12/12 PASS |
| Phase 7.5 high-priority closure (19 entities) | 114/114 PASS |
| Phase 7.6 medium/lower-priority closure (17 entities) | 102/102 PASS |
| Unmapped forbidden requests | none |
| Phase 5 status | COMPLETE |

Final regression table:

| Regression pack | Result |
|-----------------|--------|
| Behavioral Intelligence v2 | 128/128 PASS |
| Promo / discount false-positive pack | 12/12 PASS |
| Dynamic URL sandbox evaluation | 39/39 PASS |

## Current Architecture

| File | Role |
|------|------|
| `app/data/entities/jo_entities.json` | Jordan-first entity registry |
| `app/services/entity_registry.py` | Loads aliases, official domains, and official sender names |
| `app/services/risk_engine/entity_extractor.py` | Contains `ClaimedEntityExtractor`; extracts sender/domain/text entity claims |
| `app/services/risk_engine/entity_policy.py` | Emits forbidden-request, sender/domain conflict, and official-domain alignment evidence |
| `app/services/risk_engine/sender_intelligence.py` | Assesses generic sender trust; does not directly trust registry sender names |
| `app/services/risk_engine/url_intelligence.py` | Preserves `_KNOWN_BRANDS` and adds registry-backed URL brand detection |
| `app/services/risk_engine/service.py` | Runs entity extraction and entity policy before final policy decision |
| `scripts/evaluate_entity_intelligence_v2.py` | Registry audit and 612-case entity evaluation |

There is no separate `risk_engine/claimed_entity.py` or
`risk_engine/entity_registry.py` file. The claimed-entity extractor is in
`risk_engine/entity_extractor.py`, and the registry singleton is in
`app/services/entity_registry.py`.

## Registry Statistics

Current registry baseline (Phase 7.5 — High-Priority Registry Coverage Closure):

| Metric | Value |
|--------|------:|
| Entities | 166 |
| Countries | JO: 112, GLOBAL: 41, MENA: 13 |
| Aliases | 884 |
| Official domains | 191 |
| Official sender names | 325 |
| Forbidden request entries | 1067 |
| Allowed message type entries | 997 |

Entity type counts:

| Type | Count |
|------|------:|
| bank | 15 |
| government | 25 |
| ecommerce | 15 |
| payment_gateway | 10 |
| utilities | 10 |
| social_platform | 10 |
| education_university | 20 |
| healthcare | 15 |
| delivery_logistics | 12 |
| e_wallet | 8 |
| streaming_subscription | 8 |
| technology | 3 |
| telecom | 5 |
| payment_network | 5 |
| ride_hailing | 5 |

Phase 7.5 added 19 verified high-priority entities. Phase 7.6 added 17
verified medium/lower-priority entities across ecommerce, payment network,
e-wallet, ride-hailing, telecom/ISP, social platform, streaming/subscription,
and utilities. All current registry coverage targets are now met.

## Evidence IDs

Entity policy currently emits:

| Evidence ID | Purpose |
|-------------|---------|
| `entity_policy_forbidden_{entity_id}` | Claimed entity is associated with a forbidden sensitive request |
| `entity_conflict_sender_domain` | Sender entity and official URL domain entity disagree |
| `entity_conflict_sender_text` | Sender entity and text alias entity disagree |
| `entity_official_domain_alignment` | Claimed entity and official URL domain align without URL risk flags |

URL brand evidence remains separate and is backed by
`url_intelligence._KNOWN_BRANDS` plus the Phase 5.5 registry-backed bridge.

## Matching Precision

Phase 5.2 replaces broad substring fallback matching with boundary-aware text
alias matching and exact-only sender matching.

Alias matching now works in this order:

1. Exact normalized alias match.
2. Boundary-aware text match only.
3. No reverse substring matching, so short input is not matched just because it
   appears inside a longer alias.
4. Short aliases require supporting context when they appear inside longer text.

Boundary-aware matching treats Arabic letters and ASCII alphanumeric characters
as token characters. This prevents aliases from matching inside larger words:

| Text | Result |
|------|--------|
| `رسالة من زين` | Zain can match |
| `لعملائنا المميزين` | Zain must not match |
| `my CAB account` | CAB can match |
| `abcabxyz` | CAB must not match |
| `MOH` | Ministry of Health can match |
| `randommohtext` | MOH must not match |

Ambiguous common-word aliases such as `سند`, `أية`, and `اية` require direct
entity context, such as appearing at the start of a claim or after terms like
`تطبيق`, `شركة`, `خدمة`, or `استخدام`.

Sender matching is stricter than text matching:

- exact normalized official sender names still match
- suffix/prefix spoofing such as `ZAIN-FAKE`, `ArabBankSecure`,
  `CAB-LOGIN`, and `PSD-Verify` no longer creates an official sender match
- similar senders may still be caught by URL/text risk signals, but they are
  not treated as official sender alignment

## Duplicate Domain Policy

Phase 5.4 treats shared official domains as valid when they represent related
entities, such as a parent organization and a wallet/service brand, or
government departments sharing a parent domain.

The registry keeps the legacy `find_entity_by_domain()` first-match API for
compatibility and adds `find_entities_by_domain()` for multi-candidate lookup.
The extractor now carries `domain_entities` and `domain_entity_ids` alongside
the existing single `domain_entity`.

Policy:

1. A claimed or sender entity aligns when its entity ID is among the official
   domain candidates.
2. Sender/domain conflict is emitted only when the sender entity is not among
   the domain candidates.
3. Ambiguity from a shared official domain does not create dangerous evidence
   by itself.
4. Existing evidence IDs remain unchanged:
   `entity_conflict_sender_domain` and `entity_official_domain_alignment`.

Current shared official domain groups:

| Domain | Entities |
|--------|----------|
| `jo.zain.com` | `zain_jordan`, `zain_cash` |
| `jopacc.com` | `jopacc`, `cliq_jordan` |
| `jordanpost.com.jo` | `jordan_post`, `myjobox` |
| `mepspay.com` | `meps`, `meps_national_wallet` |
| `myjobox.jo` | `jordan_post`, `myjobox` |
| `orange.jo` | `orange_jordan`, `orange_money_jordan` |
| `psd.gov.jo` | `public_security_directorate_jo`, `civil_defense_directorate_jo` |

## Registry URL Brand Bridge

Phase 5.5 keeps the legacy `_KNOWN_BRANDS` and `_BRAND_ALIASES` tables as the
first URL-brand source, then falls back to registry-backed candidates from
`jo_entities.json`.

Bridge behavior:

1. Legacy `_KNOWN_BRANDS` detections keep existing behavior and evidence IDs.
2. Registry entities with official domains are available to URL brand checks.
3. Host/path/text claims use registry alias matching, including the short-alias
   protections from Phase 5.2.
4. Official registry domains, including duplicate-domain candidate groups, do
   not create brand mismatch evidence for related entities.
5. Fake lookalike domains that claim registry entities still emit existing URL
   evidence IDs such as `url_brand_impersonation`,
   `url_brand_phishing_combo`, and `url_claimed_brand_domain_mismatch`.
6. Message-text-only registry claims are conservative: generic text mentions
   need action/security/payment context before URL-brand evidence is emitted.
   This prevents safe promo text such as "شاهد التفاصيل" from being treated as
   the Shahid brand.

Current bridge metrics:

| Metric | Value |
|--------|------:|
| Legacy `_KNOWN_BRANDS` count | 17 |
| Registry brand candidates available to URL detection | 83 |
| Registry entities not covered by legacy known-brand domains | 69 |
| URL brand bridge cases | 20/20 PASS |

## Registry Quality Gate

`scripts/evaluate_entity_intelligence_v2.py` prints:

- entity counts by country and type
- alias, sender, domain, forbidden-request, and allowed-message-type quality
- duplicate domains and duplicate aliases
- substring and normalization collision risks
- unmapped forbidden requests
- registry vs URL brand coverage gaps
- runtime gaps for `allowed_message_types`

Current baseline findings:

| Finding | Count / Value |
|---------|---------------|
| Duplicate aliases across entities | 0 |
| Duplicate official domains across entities | 8 |
| Duplicate official domain policy | implemented |
| Registry URL brand bridge | implemented |
| Short/common alias risk count | 31 |
| Alias substring risks | 240 |
| Alias normalization collisions | 168 |
| Sender overmatch risks | 34 |
| Unmapped forbidden requests | none |
| Registry entities not covered by `_KNOWN_BRANDS` domains | 134 |

## Evaluation Pack

The evaluator (Phase 5.5 + Phase 7.2 + Phase 7.3 + Phase 7.4 + Phase 7.5 + Phase 7.6)
contains 612 synthetic defensive cases:

| Family | Cases |
|--------|------:|
| Official alignment | 14 |
| Mismatch / impersonation | 12 |
| Forbidden request | 12 |
| Safe awareness | 12 |
| Alias substring regression | 10 |
| Sender spoofing | 10 |
| Registry vs URL brand consistency | 10 |
| Sender precision | 4 |
| Duplicate domain policy | 10 |
| Registry URL brand bridge | 20 |
| Healthcare batch 1 (official_alignment) | 10 |
| Healthcare batch 1 (mismatch_impersonation) | 10 |
| Healthcare batch 1 (forbidden_request) | 10 |
| Healthcare batch 1 (safe_awareness) | 10 |
| Healthcare batch 1 (alias_substring) | 10 |
| Healthcare batch 1 (sender_spoofing) | 10 |
| Education batch 1 (official_alignment) | 10 |
| Education batch 1 (mismatch_impersonation) | 10 |
| Education batch 1 (forbidden_request) | 10 |
| Education batch 1 (safe_awareness) | 10 |
| Education batch 1 (alias_substring) | 10 |
| Education batch 1 (sender_spoofing) | 10 |
| Government batch 1 (official_alignment) | 8 |
| Government batch 1 (mismatch_impersonation) | 8 |
| Government batch 1 (forbidden_request) | 8 |
| Government batch 1 (safe_awareness) | 8 |
| Government batch 1 (alias_substring) | 8 |
| Government batch 1 (sender_spoofing) | 8 |
| Delivery/logistics batch 1 (official_alignment) | 6 |
| Delivery/logistics batch 1 (mismatch_impersonation) | 6 |
| Delivery/logistics batch 1 (forbidden_request) | 6 |
| Delivery/logistics batch 1 (safe_awareness) | 6 |
| Delivery/logistics batch 1 (alias_substring) | 6 |
| Delivery/logistics batch 1 (sender_spoofing) | 6 |
| Ecommerce batch 1 (official_alignment) | 5 |
| Ecommerce batch 1 (mismatch_impersonation) | 5 |
| Ecommerce batch 1 (forbidden_request) | 5 |
| Ecommerce batch 1 (safe_awareness) | 5 |
| Ecommerce batch 1 (alias_substring) | 5 |
| Ecommerce batch 1 (sender_spoofing) | 5 |
| Payment network batch 1 (official_alignment) | 2 |
| Payment network batch 1 (mismatch_impersonation) | 2 |
| Payment network batch 1 (forbidden_request) | 2 |
| Payment network batch 1 (safe_awareness) | 2 |
| Payment network batch 1 (alias_substring) | 2 |
| Payment network batch 1 (sender_spoofing) | 2 |
| Payment gateway batch 1 (official_alignment) | 3 |
| Payment gateway batch 1 (mismatch_impersonation) | 3 |
| Payment gateway batch 1 (forbidden_request) | 3 |
| Payment gateway batch 1 (safe_awareness) | 3 |
| Payment gateway batch 1 (alias_substring) | 3 |
| Payment gateway batch 1 (sender_spoofing) | 3 |
| E-wallet batch 1 (official_alignment) | 1 |
| E-wallet batch 1 (mismatch_impersonation) | 1 |
| E-wallet batch 1 (forbidden_request) | 1 |
| E-wallet batch 1 (safe_awareness) | 1 |
| E-wallet batch 1 (alias_substring) | 1 |
| E-wallet batch 1 (sender_spoofing) | 1 |
| Ride-hailing batch 1 (official_alignment) | 2 |
| Ride-hailing batch 1 (mismatch_impersonation) | 2 |
| Ride-hailing batch 1 (forbidden_request) | 2 |
| Ride-hailing batch 1 (safe_awareness) | 2 |
| Ride-hailing batch 1 (alias_substring) | 2 |
| Ride-hailing batch 1 (sender_spoofing) | 2 |
| Phase 7.5 official alignment | 19 |
| Phase 7.5 mismatch / impersonation | 19 |
| Phase 7.5 forbidden request | 19 |
| Phase 7.5 safe awareness | 19 |
| Phase 7.5 alias non-overmatch | 19 |
| Phase 7.5 sender spoofing | 19 |
| Phase 7.6 official alignment | 17 |
| Phase 7.6 mismatch / impersonation | 17 |
| Phase 7.6 forbidden request | 17 |
| Phase 7.6 safe awareness | 17 |
| Phase 7.6 alias non-overmatch | 17 |
| Phase 7.6 sender spoofing | 17 |

Pass criteria:

- Safe official alignment cases must not become dangerous.
- Safe awareness messages must not become dangerous.
- Forbidden sensitive request cases must be suspicious or dangerous.
- Mismatch and impersonation cases must be caution, suspicious, or dangerous
  according to the case expectation.
- Alias substring regression cases must not produce the wrong claimed entity.
- Sender spoofing cases must not be treated as official sender alignment.
- Exact official sender cases must continue to match.
- Shared official domains must align with related entities without false
  sender/domain conflict.
- Unrelated sender/domain mismatches must still produce conflict evidence.
- Registry entities missing from legacy `_KNOWN_BRANDS` must still be detected
  on fake login/update/payment domains.

---

## Registry Expansion Roadmap

The registry is ready for product-grade expansion. Future batches must follow
the framework defined in `docs/REGISTRY_EXPANSION_GUIDE.md`.

### Principles

- **Expansion is test-driven.** Every new entity record requires at minimum
  six evaluation cases: official domain safe, fake domain impersonation,
  forbidden request, awareness lookalike, alias substring regression, and
  sender spoofing. No registry batch is accepted without passing the full
  evaluation suite.
- **Verification is mandatory.** Official domains and sender names must be
  sourced from the entity's official website, a regulator listing, an official
  government directory, or an official app-store developer page. Blogs, news
  articles, and SEO directories are not acceptable sources.
- **`allowed_message_types` remains deferred.** The field is stored per entity
  but is not yet wired into the scoring engine for fine-grained suppression.
  Wiring it up is future work — it does not block expansion.
- **Audit before merge.** Run `audit_entity_registry_expansion.py` against
  every batch before merging. The script catches missing required fields,
  duplicate IDs, domain hygiene issues, and coverage gaps.

### Expansion Priorities

The categories with the largest coverage gaps relative to product-grade targets:

| Priority | Category | Current | Target |
|----------|----------|--------:|-------:|
| High | `government` | 25 | 25+ |
| High | `healthcare` | 15 | 15+ |
| High | `education_university` | 20 | 20+ |
| High | `delivery_logistics` | 12 | 12+ |
| Medium | `ecommerce` | 15 | 15+ |
| Medium | `payment_gateway` | 10 | 10+ |
| Medium | `payment_network` | 5 | 5+ |
| Medium | `e_wallet` | 8 | 8+ |
| Lower | `telecom` | 5 | 5+ |
| Lower | `ride_hailing` | 5 | 5+ |
| Lower | `social_platform` | 10 | 10+ |
| Lower | `streaming_subscription` | 8 | 8+ |
| Lower | `utilities` | 10 | 10+ |

Phase 7.5 closed the high-priority healthcare, education/university,
government, and delivery/logistics gaps. Phase 7.6 closed the current
medium/lower-priority ecommerce, payment network, e-wallet, ride-hailing,
telecom, social platform, streaming/subscription, and utilities targets.

See `docs/REGISTRY_EXPANSION_GUIDE.md` for full verification requirements,
alias/domain/sender policies, forbidden-request mappings, and the batch
acceptance checklist.
- Safe promo and substring lookalikes must not become brand impersonation.
- Phase 3 and Phase 4 regression packs must still pass.

Current Phase 7.6 baseline:

| Result | Count |
|--------|------:|
| Entity cases total | 612 |
| Passed | 612 |
| Failed | 0 |
| Alias substring regression | 10/10 PASS |
| Sender spoofing | 10/10 PASS |
| Sender precision | 4/4 PASS |
| Duplicate domain policy | 10/10 PASS |
| Registry URL brand bridge | 20/20 PASS |
| Healthcare batch 1 | 60/60 PASS |
| Education batch 1 | 60/60 PASS |
| Government batch 1 | 48/48 PASS |
| Delivery/logistics batch 1 | 36/36 PASS |
| Ecommerce batch 1 | 30/30 PASS |
| Payment network batch 1 | 12/12 PASS |
| Payment gateway batch 1 | 18/18 PASS |
| E-wallet batch 1 | 6/6 PASS |
| Ride-hailing batch 1 | 12/12 PASS |
| Phase 7.5 high-priority closure | 114/114 PASS |
| Phase 7.6 medium/lower-priority closure | 102/102 PASS |
| Phase 5 quality gate | `PHASE_5_STATUS: COMPLETE` |
| Behavioral v2 regression | PASS |
| Promo false-positive regression | PASS |
| Dynamic sandbox regression | PASS |
| Total cases across all packs | 791 |
| FINAL_VALIDATION_STATUS | PASS |

Phase 5 and Phase 7 registry quality gates are complete for the current
coverage targets. Remaining future work is telemetry-led expansion and runtime
policy decisions, not target-count closure.

## How To Run

```bash
cd backend
python scripts/evaluate_entity_intelligence_v2.py
python scripts/evaluate_behavioral_v2.py
python scripts/evaluate_behavioral_false_positives.py
python scripts/evaluate_dynamic_url_sandbox.py
```

Syntax check:

```bash
cd backend
python -m py_compile app/services/risk_engine/url_intelligence.py app/services/entity_registry.py scripts/evaluate_entity_intelligence_v2.py
```

## Known Gaps

1. `allowed_message_types` needs a runtime use decision before it can provide
   safe-context benefit. This is intentionally deferred because using it as a
   risk reducer too early could hide phishing messages that mimic legitimate
   service notices.
2. Current high-, medium-, and lower-priority registry coverage targets are
   closed for this phase. Future registry expansion should continue only with
   verified domains and six-case evaluator coverage per entity.
3. Phase 7.6 uses conservative ASCII aliases for its new entities where
   Arabic-localized aliases could not be safely preserved during editing. Add
   localized aliases later only with encoding-safe tooling and evaluator
   coverage.
4. `_KNOWN_BRANDS` remains smaller by design for backwards compatibility; the
   registry bridge covers runtime detection, but later cleanup can generate or
   report legacy/static coverage automatically.

## Future Work

1. Decide how `allowed_message_types` should be used without creating false
   negatives.
2. Add future registry entities only when telemetry or product scope justifies
   them, with defensive evaluator cases (minimum 6 cases per entity).
3. Optionally generate or audit legacy `_KNOWN_BRANDS` from registry data while
   preserving backward compatibility.
