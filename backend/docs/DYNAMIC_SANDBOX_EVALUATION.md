# APG Dynamic URL Sandbox — Evaluation Guide

## Overview

The dynamic URL sandbox runs a Playwright browser session against a message's
primary URL and returns behavioural signals (login forms, password fields,
domain changes, delayed redirects, etc.). These signals supplement the static
text and URL-reputation analysis.

This guide covers how the sandbox fits into the scoring pipeline, why scoring
is separately gated, and how to run the regression evaluation pack. Phase 3.3
adds borderline cases that make the conservative gate behavior visible without
using real phishing URLs or changing production scoring logic.

---

## Operating Modes

| Mode | Env vars | Sandbox runs | Score affected |
|------|----------|--------------|----------------|
| **Disabled** | `DYNAMIC_URL_ANALYSIS_ENABLED=false` | No | No |
| **Shadow** | `DYNAMIC_URL_ANALYSIS_ENABLED=true` | Yes | No |
| **Scoring** | Both flags `=true` | Yes | Evidence may be admitted if the gate passes; the final score can still remain unchanged because of existing caps/floors |

Shadow mode is the safe default for production rollout: the sandbox observes
and logs but never changes `risk_score` or `classification`. Operators can
verify false-positive rates before enabling scoring.

---

## Why Scoring Is Feature-Flagged

Sandbox signals carry higher uncertainty than static text analysis:

- A login form on a page is normal for many legitimate services.
- DNS failures or Playwright timeouts produce no evidence (not penalised).
- Redirect chains are common for CDN-served pages.

Scoring is therefore disabled by default (`DYNAMIC_URL_ANALYSIS_SCORE_ENABLED=false`)
and enabled only after the conservative gate confirms multiple risk signals
co-occur together.

---

## Conservative Gate — Pass Conditions

The gate (`_should_score_dynamic_url_evidence()`) allows sandbox evidence into
scoring only when at least one **strong combination** is present:

| # | Combination | Required co-signals |
|---|-------------|---------------------|
| 1 | Password field | Brand impersonation, suspicious/malicious URL, domain change, ≥2 suspicious external requests, or account/credential context |
| 2 | OTP field | OTP-request intent, account context, brand impersonation, or domain change |
| 4 | Delayed redirect or sensitive form after delay | Domain change, brand impersonation, or suspicious URL |
| 5 | Domain changed + login form | Brand impersonation or account/credential context |

Safe message intents (`advertisement`, `promotional`, `transactional`,
`service_notice`, `otp_code`, `security_advice`) suppress scoring unless
a **sensitive field** (password or OTP) co-occurs with a **hard mismatch**
(domain change, brand impersonation, or suspicious/malicious URL reputation).

---

## Evidence Caps

Even when the gate allows, sandbox evidence contribution is bounded:

| Limit | Value |
|-------|-------|
| Max evidence items selected | 3 |
| Max individual item delta | 28 pts (enforced by `dynamic_result_to_evidence`) |
| Max total sandbox delta | 45 pts |

All sandbox evidence has `category = "suspicious_context"` — it cannot trigger
definite block rules on its own.

---

## Debug Output Fields

`debug.dynamic_url_analysis` is always present. Completed and failed sandbox
runs include:

| Field | Meaning |
|-------|---------|
| `score_impact` | `none_shadow_mode` / `conservative_scoring_enabled` / `scoring_enabled_no_evidence` / `scoring_blocked_by_gate` |
| `scoring_gate` | `{allowed: bool, reason: string}` — set when `SCORE_ENABLED=true` |
| `scored_evidence_summary` | `{count, total_delta, ids}` — items actually added to scoring |
| `ready_for_scoring` | `true` when completed, no error, and evidence_preview is non-empty |
| `sandbox_summary` | Human-readable risk indicator summary |
| `evidence_preview` | Full list of what *would* be scored — always present for admin visibility |
| `error_category` | Normalised error type when sandbox fails |

Disabled and no-URL states use a minimal debug shape:

| State | Fields |
|-------|--------|
| Disabled | `enabled`, `mode`, `executed`, `score_impact`, `ready_for_scoring` |
| Enabled but no URL | `enabled`, `mode`, `executed`, `reason`, `score_impact`, `ready_for_scoring` |

---

## Running the Evaluation Script

```bash
cd backend

# Standard run (all 39 cases, 3 modes each)
python scripts/evaluate_dynamic_url_sandbox.py

# Show only failing cases
python scripts/evaluate_dynamic_url_sandbox.py --failures-only

# Show which evidence IDs were scored
python scripts/evaluate_dynamic_url_sandbox.py --verbose

# Export JSON results
python scripts/evaluate_dynamic_url_sandbox.py --json reports/sandbox_eval.json
```

No environment variables need to be set — the script monkeypatches the module
flags internally and resets them on exit.

The current pack contains:

| Group | Count | Purpose |
|-------|------:|---------|
| Baseline regression | 27 | Phase 3.1/3.2 safe, suspicious, dangerous, and Zain alias regression coverage |
| Phase 3.3 borderline | 12 | Weak static cases with mocked password/OTP/login/redirect/external-request sandbox findings |
| Total | 39 | Full mocked evaluation suite |

---

## Output Table Columns

```
ID  CAT        LABEL                             DIS      SHA      SCO      ΔSCO  GATE  REASON  IMPACT                         R
```

| Column | Description |
|--------|-------------|
| `DIS` | `score/class` in disabled mode (e.g. `42/W`) |
| `SHA` | `score/class` in shadow mode — should equal `DIS` |
| `SCO` | `score/class` in scoring mode |
| `ΔSCO` | `SCO.score − DIS.score` |
| `GATE` | `Y` if scoring gate allowed evidence, `N` if blocked |
| `REASON` | `scoring_gate.reason` from mode-2 debug output |
| `IMPACT` | `score_impact` value from mode-2 debug output |
| `R` | `PASS` or `FAIL` |

Class abbreviations: `S` = safe, `W` = suspicious/warn, `D` = dangerous.

---

## Pass Criteria

| Rule | Check |
|------|-------|
| P1 | `shadow_score == disabled_score` |
| P2 | `shadow_class == disabled_class` |
| P3 | Gate blocked → `scoring_score == disabled_score` |
| P4 | SAFE category → `scoring_class != dangerous` |
| P5 | `scoring_score ≤ 100` |
| P6 | `disabled/shadow score_impact == "none_shadow_mode"` |
| P7 | Case-specific expected gate outcome, where declared |
| P8 | Expected no-delta cases remain unchanged |
| P9 | Expected visible-delta cases increase in scoring mode |
| P10 | Scoring mode never lowers the disabled-mode score |

---

## Phase 3.3 Borderline Coverage

Phase 3.3 adds these mocked borderline categories:

| Case | Scenario | Expected gate behavior |
|------|----------|------------------------|
| 28 | Weak text + password field + final domain changed | Allowed |
| 29 | URL-only Zain impersonation + password field | Allowed; static URL analysis already reaches dangerous for this exact surface |
| 30 | Weak account wording + OTP field | Allowed via OTP/account context |
| 31 | Delivery tracking wording + delayed redirect + domain changed | Allowed by delayed behavior with mismatch |
| 32 | Government/service weak wording + password field + domain changed | Allowed; visible score delta |
| 33 | Plain login page no context | Blocked |
| 34 | Safe promo + login page | Blocked |
| 35 | Safe security advice + login page, no sensitive fields | Blocked |
| 36 | OTP theft weak text + OTP field + domain changed | Allowed; score may be capped by static URL signals |
| 37 | External requests + login form only | Blocked by conservative design |
| 38 | Low-static password/domain-control case | Allowed; visible score delta |
| 39 | Low-static OTP/domain-control case | Allowed; visible score delta |

The script prints a short Phase 3.3 summary with:

- total borderline cases added
- cases where sandbox created a visible final-score delta
- cases where the gate blocked correctly
- borderline failures

---

## False Positive Protections

1. **Clean URL verdict** suppresses most sandbox evidence via `clean_suppressed` guard in `dynamic_result_to_evidence`.
2. **Trusted domain** suppresses login/password evidence (login forms are expected on known sites).
3. **Safe intent** (awareness, OTP delivery, promo) blocks all evidence unless sensitive field + hard mismatch.
4. **Evidence cap** (max 3 items, total ≤ 45 pts) prevents sandbox from dominating a score.
5. **`suspicious_context` only** — sandbox evidence cannot set `dangerous_intent`; the policy engine's definite-block rules require that category.
6. **Gate blocked = no change** — if no combination passes, score is identical to disabled mode.

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DYNAMIC_URL_ANALYSIS_ENABLED` | `false` | Enable sandbox execution |
| `DYNAMIC_URL_ANALYSIS_SCORE_ENABLED` | `false` | Allow sandbox evidence to affect score |
| `DYNAMIC_URL_ANALYSIS_TIMEOUT_SECONDS` | `10` | Playwright browser timeout |
| `DYNAMIC_URL_ANALYSIS_OBSERVATION_MS` | `1500` | Delayed-behaviour observation window |
| `DYNAMIC_URL_ANALYSIS_TIME_SIMULATION_ENABLED` | `false` | Override Date.now() in page |
| `DYNAMIC_URL_ANALYSIS_SIMULATED_MINUTES` | `0` | Minutes to advance simulated clock |

To enable full scoring in production:
```
DYNAMIC_URL_ANALYSIS_ENABLED=true
DYNAMIC_URL_ANALYSIS_SCORE_ENABLED=true
```
