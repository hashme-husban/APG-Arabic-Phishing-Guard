# APG Registry Expansion Guide

## 1. Registry Quality Goal

The APG entity registry is not simply a list of organization names. It is a
**verified organization intelligence layer** — a structured, auditable dataset
that tells the risk engine:

- What names and aliases an organization uses in Arabic and English
- What domains are officially operated by that organization
- What sender names it uses in SMS/WhatsApp/notifications
- What types of messages it legitimately sends
- What sensitive data it should **never** request through chat or SMS
- What risk context operators should be aware of for that organization

A registry entry with incorrect domains, over-broad aliases, or missing
forbidden-request mappings can cause false positives (safe messages flagged as
dangerous) or false negatives (phishing messages not caught). Every addition
must be treated as a security-sensitive change.

---

## 2. Required Fields

Every entity record in `jo_entities.json` must contain all of the following
fields. Records missing any required field will be rejected by the audit
script.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Unique snake_case identifier, no spaces. E.g. `arab_bank`. |
| `name` | `string` | Official English name of the organization. |
| `primary_arabic_name` | `string` | Primary Arabic name as officially used. |
| `aliases` | `array[string]` | All recognized name variants (see Alias Policy). |
| `entity_type` | `string` | Canonical type (see Entity Category Roadmap). |
| `country` | `string` | `JO`, `MENA`, or `GLOBAL`. |
| `official_domains` | `array[string]` | Verified official domains (see Domain Policy). |
| `official_sender_names` | `array[string]` | Official SMS/notification sender IDs (see Sender Policy). |
| `allowed_message_types` | `array[string]` | Message types this entity legitimately sends. |
| `forbidden_requests` | `array[string]` | Sensitive data this entity should never request. |
| `risk_notes` | `array[string]` | Human-readable risk context for reviewers. |

---

## 3. Recommended Future Metadata

The following optional fields are **not yet implemented** in the registry
schema or the service code. They are recommended for a future data-quality
pass and should not require production code changes:

| Field | Values / Format | Purpose |
|-------|----------------|---------|
| `verification_sources` | `array[string]` — URLs | Links to the official source where the domain/sender was verified. |
| `source_type` | `official_website` \| `regulator` \| `government_directory` \| `app_store` \| `official_social_link` | How the verification was performed. |
| `last_verified` | `YYYY-MM-DD` | When the entry was last reviewed against live sources. |
| `verification_confidence` | `high` \| `medium` \| `low` | Confidence in the current data. Entries added from secondary sources should start at `medium`. |
| `review_status` | `verified` \| `pending_review` \| `needs_update` | Workflow state for registry maintenance. |
| `risk_level` | `high` \| `medium` \| `low` | How frequently this entity is impersonated (based on observed telemetry). |
| `alias_risk_notes` | `object` — alias → note | Per-alias notes for aliases that carry impersonation risk (e.g., short aliases that could collide). |

---

## 4. Entity Category Roadmap

Expansion priority order (A = highest priority):

| Priority | Category (`entity_type`) | Rationale |
|----------|--------------------------|-----------|
| A | `bank` | Banks are the #1 impersonation target. Current: 15. Target: 15+ (current coverage already adequate; fill gaps in smaller banks). |
| A | `government` | Government impersonation is rising. Current: 25. Target: 25+ (target met; expand only with verified public-service entities and evaluator cases). |
| B | `telecom` | Telecom OTP and account-update scams. Current: 5. Target: 5+ (target met; expand only with verified providers and evaluator cases). |
| B | `e_wallet` | Wallet freeze/reactivation fraud. Current: 8. Target: 8+ (target met; expand only with verified wallet services). |
| B | `payment_gateway` | Payment phishing. Current: 10. Target: 10+ (target met). |
| B | `payment_network` | Card scheme impersonation. Current: 5. Target: 5+ (target met). |
| C | `delivery_logistics` | Delivery fee fraud is the fastest-growing attack category. Current: 12. Target: 12+ (target met; continue only with verified courier services operating in Jordan). |
| C | `ecommerce` | E-commerce phishing. Current: 15. Target: 15+ (target met; expand only with verified platforms). |
| D | `healthcare` | Hospital/pharmacy impersonation. Current: 15. Target: 15+ (target met; future additions should focus on verified hospitals, labs, pharmacies, and healthcare portals). |
| D | `education_university` | University credential phishing. Current: 20. Target: 20+ (target met; future additions should focus on verified universities and technical institutions). |
| E | `utilities` | Utility bill fraud. Current: 10. Target: 10+ (target met; expand only with verified utility/service entities). |
| E | `ride_hailing` | Ride-hailing account takeover. Current: 5. Target: 5+ (target met). |
| F | `social_platform` | Social account hijacking. Current: 10. Target: 10+ (target met). |
| F | `streaming_subscription` | Subscription fraud. Current: 8. Target: 8+ (target met). |
| G | Charities / NGOs | Donation fraud, especially around Ramadan. Add only if phishing cases confirmed. |

---

## 5. Verification Source Policy

### Accepted sources

| Source type | How to use |
|-------------|-----------|
| **Official entity website** | Navigate to the entity's own website. Use the domain shown in the browser address bar. Prefer the canonical form without `www` if both resolve. |
| **Regulator listing** | Use the Central Bank of Jordan (CBJ), Telecommunications Regulatory Commission (TRC), or equivalent regulator's official published list. |
| **Government directory** | Use official Jordan e-Government portal or Ministry directories. |
| **Official app store page** | Use the developer domain listed on the Google Play or Apple App Store listing. |
| **Official social page linked from website** | A social media URL is acceptable **only** if it is linked from the entity's official website footer or "Contact Us" page. |

### Rejected sources

The following are **never** acceptable as domain verification sources:

- Random news articles or blog posts mentioning an entity's domain
- Unverified social accounts (not linked from official website)
- SEO/business directories (e.g., Yellowpages, Yelp, Google Maps)
- User-submitted or crowd-sourced domain databases
- WHOIS data alone (domain ownership can be falsified)
- Redirect/tracking links (unless the organization explicitly uses them for official communications and the target domain is verified)

---

## 6. Alias Policy

### What to include

| Alias type | Include? | Notes |
|-----------|:--------:|-------|
| Exact official English name | ✓ | Always |
| Exact official Arabic name | ✓ | Always |
| Common Arabic spelling variants | ✓ | Hamza variants, ه/ة swap, ي/ى swap |
| Common English spelling/abbreviation variants | ✓ | E.g., "ArabBank", "Arab-Bank" |
| Official app/service names | ✓ | E.g., "CliQ", "SANAD" |
| Short aliases (1–3 chars) | ⚠ | Only if unavoidable; must be flagged as high-risk |
| Common-word Arabic aliases | ⚠ | Require context — see below |
| Generic words (e.g., "بنك", "حكومة") | ✗ | Never — too broad |

### Short alias rules

Short aliases (fewer than 4 characters) must:
1. Have no common-word collision risk with standard Arabic text.
2. Have a `risk_notes` entry explaining why the short alias is needed.
3. Have at least one evaluation test case specifically for the alias.
4. Pass the alias-substring regression pack before acceptance.

### Common-word alias rules

Arabic aliases that coincide with common vocabulary words (e.g., `زين` meaning
"beautiful/decorative" as well as the Zain telecom brand) are flagged by the
audit script. Before adding such an alias:
1. Verify the alias is genuinely used in official communications.
2. Check whether the entity registry's boundary-aware matching is sufficient
   (it almost always is — `\b` word boundaries prevent substring matches).
3. Document the collision risk in `risk_notes`.
4. Add a regression test for the false-positive case (message containing
   the collision word but not the brand).

---

## 7. Domain Policy

### Normalization rules

When adding official domains:
- Remove `https://`, `http://`, `www.` prefixes.
- Remove trailing paths, query strings, ports.
- Preserve meaningful subdomains (e.g., `online.arabbank.jo`, `my.stc.com.sa`).
- Use lowercase only.
- Do not add `www.arabbank.jo` if `arabbank.jo` already resolves (avoid
  duplicates — the registry service handles subdomain matching automatically).

### What NOT to add

| Type | Example | Reason |
|------|---------|--------|
| Login portal paths | `arabbank.jo/online/login` | Path is not part of the domain record |
| Payment redirect domains | `pay.pspdomain.io/arabbank` | Tracking/PSP domains are not official entity domains |
| Marketing campaign URLs | `promo-arabbank.campaign.io` | Transient, not official |
| CDN/static asset domains | `static.arabbank.io` | Not used in communications |
| Unverified look-alike domains | `arabbank.net` | Must be verified before adding |

### Shared (duplicate) official domains

When two or more related entities share an official domain (e.g., a telecom
operator and its mobile wallet subsidiary both use the same corporate domain),
the domain should be added to **both** entity records. The registry service's
`find_entities_by_domain()` returns all matching entities, and the risk engine
evaluates the full candidate list.

Document shared domain groups in `risk_notes` for each affected entity.

---

## 8. Sender-Name Policy

Official sender names are the alphanumeric IDs that appear as the "From" field
in SMS messages (e.g., `ARABBANK`, `ZAIN`, `JO-POST`).

### Rules

| Rule | Detail |
|------|--------|
| **Exact match only** | Sender matching in the registry service is exact (after normalization). Do not add spoofed or slightly different variants as official senders — that is the attack pattern being detected. |
| **Uppercase forms** | Add the form the operator actually registers with the SMS gateway. This is commonly uppercase (e.g., `ARABBANK`, `ORANGE JO`). |
| **No fake variants** | Do not add `ARAB-BANK`, `Arab Bank`, or `ArabBankJO` unless the entity officially uses that exact sender ID. Fake-looking variants remain untrusted — that is intentional. |
| **Short sender names** | Sender names shorter than 4 characters require extra caution: common words may collide. Document in `risk_notes` and add a sender-precision evaluation test case. |
| **Alphanumeric only** | Sender names are typically restricted to 11 characters, alphanumeric, for GSM compliance. Verify the exact registered sender ID from official sources. |

---

## 9. Forbidden-Request Policy

Forbidden requests define what sensitive data a given entity should **never**
request through SMS, WhatsApp, or untrusted links. When a message claims to be
from entity X and asks for a forbidden item, a critical block evidence item is
generated.

### Recommended forbidden requests per entity type

| Entity type | Minimum required forbidden requests |
|-------------|-------------------------------------|
| `bank` | `password`, `otp_code`, `card_pin`, `card_number`, `cvv`, `iban`, `online_banking_password` |
| `telecom` | `otp_code`, `password`, `card_pin` |
| `e_wallet` | `otp_code`, `wallet_pin`, `wallet_password`, `card_number`, `cvv` |
| `payment_gateway` | `otp_code`, `card_number`, `cvv`, `card_pin`, `password` |
| `payment_network` | `card_number`, `cvv`, `card_pin` |
| `government` | `password`, `otp_code`, `card_number`, `cvv`, `sanad_password` |
| `delivery_logistics` | `card_number`, `cvv`, `otp_code` |
| `ecommerce` | `card_number`, `cvv`, `otp_code`, `password` |
| `healthcare` | `password`, `otp_code`, `card_number`, `cvv` |
| `education_university` | `password`, `otp_code`, `recovery_code` |
| `social_platform` | `otp_code`, `password`, `recovery_code`, `two_factor_backup_code` |
| `streaming_subscription` | `otp_code`, `password`, `card_number`, `cvv` |
| `ride_hailing` | `otp_code`, `password`, `card_number`, `cvv` |
| `utilities` | `otp_code`, `password`, `card_number`, `cvv` |

All values must match the canonical set used in `entity_policy.py`. `sim_swap_code` is reserved for future telecom hardening but should not be added to registry entries until runtime mapping is implemented.

---

## 10. Evaluation Requirement

Every registry expansion batch **must** include a corresponding evaluation
addition in `scripts/evaluate_entity_intelligence_v2.py`. No batch is
accepted without test coverage.

### Minimum required test cases per new entity

| Test type | Description |
|-----------|-------------|
| **Official domain safe case** | Message linking to the entity's official domain — must classify as safe. |
| **Fake domain impersonation case** | Message using a near-miss or phishing domain — must classify as dangerous/suspicious. |
| **Forbidden request case** | Message claiming to be from the entity and requesting a forbidden item — must classify as dangerous. |
| **Safe awareness lookalike** | Message warning about the entity being impersonated — must NOT be flagged as dangerous. |
| **Alias substring regression** | Message containing a word that includes the entity's alias as a substring — must NOT trigger the entity's detection. |
| **Sender spoofing case** | Message with a spoofed sender name — must remain suspicious/dangerous. |

If the new entity shares an official domain with an existing entity, also add:

| Test type | Description |
|-----------|-------------|
| **Duplicate domain case** | Two messages — one for each entity sharing the domain — must both classify correctly. |

---

## 11. Batch Acceptance Rule

A registry expansion batch is accepted and merged only when **all** of the
following evaluation packs pass without regressions:

| Pack | Script | Required result |
|------|--------|----------------|
| Entity Intelligence v2 | `evaluate_entity_intelligence_v2.py` | 100% PASS (including all new cases) |
| Behavioral Intelligence v2 | `evaluate_behavioral_v2.py` | 100% PASS (unchanged) |
| Promo False-Positive Pack | `evaluate_behavioral_false_positives.py` | 100% PASS (unchanged) |
| Dynamic URL Sandbox Pack | `evaluate_dynamic_url_sandbox.py` | 100% PASS (unchanged) |
| Registry Expansion Audit | `audit_entity_registry_expansion.py` | No schema errors, no missing required fields, no duplicate IDs |
| Final Validation | `run_final_validation.py` | `FINAL_VALIDATION_STATUS: PASS` |

Run the full suite with:

```bash
cd backend
python scripts/run_final_validation.py
python scripts/audit_entity_registry_expansion.py
```

---

## Quick Checklist for a New Entity Entry

Before submitting a new entity record, verify each item:

- [ ] `id` is unique and uses snake_case
- [ ] `official_domains` verified from official source (not from a blog or news article)
- [ ] `official_sender_names` verified from an official communications sample or SMS gateway documentation
- [ ] No domain includes a protocol (`https://`), path, or query string
- [ ] No alias is a generic Arabic word without context
- [ ] Short aliases (< 4 chars) have a `risk_notes` entry
- [ ] `forbidden_requests` covers at least the minimum set for the entity type
- [ ] At least 6 evaluation test cases added (official domain, fake domain, forbidden request, awareness lookalike, alias substring, sender spoofing)
- [ ] `audit_entity_registry_expansion.py` runs with no schema errors
- [ ] `run_final_validation.py` returns `FINAL_VALIDATION_STATUS: PASS`
