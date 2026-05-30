# APG — AI / ML Approach

## Philosophy: Hybrid Advisory Architecture

APG deliberately avoids single-model reliance. The final risk score is computed by a
**Decision Fusion Layer** that weighs evidence from multiple independent sources:

- Two ML models (semantic + lexical) — both advisory only
- Deterministic behavioral rules
- URL intelligence
- Entity impersonation detection

This design provides:
- **Robustness** — if one model is uncertain, others contribute
- **Explainability** — each evidence source can be shown in the explanation
- **Controllability** — thresholds and weights are configurable without retraining

---

## Layer 04 — Text Intelligence

### 4a. AraBERT Semantic Advisory

| Property | Value |
|----------|-------|
| Base model | `aubmindlab/bert-base-arabertv2` |
| Fine-tuning task | Binary classification: phishing (1) vs. legitimate (0) |
| Training examples | 3,576 balanced Arabic SMS/phishing samples |
| Output | Probability score p(phishing) ∈ [0.0, 1.0] |
| Role in engine | Advisory input to fusion layer; not the final decision maker |

**Fine-tuning details:**
- Sequence length: 128 tokens
- Optimizer: AdamW with linear warmup
- Epochs: 3 (selected by validation F1)
- Evaluation: macro F1 on held-out validation set (124 examples)

**Best threshold selection:**
- Threshold optimized on validation set to maximize F1
- Stored in `models/semantic_arabert/best_threshold.json`

### 4b. TF-IDF Lexical Classifier (Advisory)

| Property | Value |
|----------|-------|
| Vectorizer | TF-IDF with Arabic character n-grams (n=2–4) |
| Classifier | Logistic Regression (C=1.0, balanced class weights) |
| Features | ~50,000 n-gram features |
| Training | Same balanced dataset as AraBERT |
| Output | Probability score p(phishing) ∈ [0.0, 1.0] |
| Role | Fast, interpretable lexical signal; detects surface-level patterns |

The lexical model is particularly effective at catching:
- Known phishing keyword patterns
- Specific Jordanian bank/telecom brand name misuse
- Arabic urgency phrase clusters

### 4c. Behavioral Rules

APG includes **1,135 hand-curated Arabic phishing behavioral phrases** organized into categories:

| Category | Examples |
|----------|---------|
| Urgency pressure | "حسابك سيُغلق خلال 24 ساعة" (your account will close in 24h) |
| OTP theft | "أرسل لنا رمز التحقق" (send us the verification code) |
| Banking fraud | "تم تجميد حسابك البنكي" (your bank account has been frozen) |
| Prize/giveaway | "لقد فزت بجائزة نقدية" (you won a cash prize) |
| Action pressure | "انقر الآن قبل انتهاء العرض" (click now before offer expires) |

Each matched phrase adds weighted evidence to the fusion layer.

---

## Layer 02 — Entity Policy (Impersonation Detection)

The entity registry contains **166 Jordanian entities** including:
- Commercial banks (Arab Bank, Bank of Jordan, Cairo Amman Bank, etc.)
- Mobile telecoms (Zain, Ooredoo, Orange Jordan)
- Government portals (Ministry of Interior, Social Security, Income & Sales Tax)
- Payment services (eFAWATEERcom, JoMoPay)

For each analysis the engine checks:
1. Does the message claim to be from a known entity?
2. Is the sender domain/number consistent with the claimed entity?
3. Does the message contain known impersonation signals for that entity?

Entity mismatch adds a strong positive evidence signal toward phishing.

---

## Layer 05 — URL Intelligence

For messages containing URLs the engine:

1. Extracts all URLs using regex
2. Runs local heuristics (suspicious TLDs, IP-based URLs, excessive subdomains, typosquatting)
3. Optionally queries external reputation providers (if API keys are configured):
   - Google Safe Browsing
   - VirusTotal
   - URLScan.io
   - PhishTank

If no API keys are provided, the URL layer falls back to local heuristics only. This
is intentional — the system is designed to function without external dependencies.

---

## Layer 06 — Decision Fusion

The fusion layer aggregates all evidence into a final risk score (0–100):

```
score = Σ (evidence_i × weight_i)
```

Weights are configured in `configs/fusion_layer_config.json`. Current default weights:

| Evidence source | Default weight |
|----------------|----------------|
| AraBERT advisory | 0.25 |
| TF-IDF lexical advisory | 0.15 |
| Behavioral rules | 0.30 |
| URL heuristics | 0.20 |
| Entity impersonation | 0.10 |

Weights can be tuned without retraining any model.

**Verdict thresholds:**

| Risk Score | Verdict |
|-----------|---------|
| 0 – 29 | SAFE |
| 30 – 59 | SUSPICIOUS |
| 60 – 79 | HIGH_RISK |
| 80 – 100 | PHISHING |

---

## Layer 07 — Explanation

The explanation layer converts the evidence list into a human-readable report:

- Summary verdict (SAFE / SUSPICIOUS / HIGH_RISK / PHISHING)
- Risk score (0–100)
- Triggered evidence items (each with label, score contribution, and description)
- Entity name if impersonation was detected
- URL reputation summary if URLs were found

Explanations are available in Arabic and English.

---

## Evaluation Results

| Model | Dataset | Accuracy | F1 (macro) | Precision | Recall |
|-------|---------|----------|-----------|-----------|--------|
| AraBERT (fine-tuned) | Test set (124) | ~94% | ~0.94 | ~0.94 | ~0.94 |
| TF-IDF Lexical | Test set (124) | ~88% | ~0.88 | ~0.88 | ~0.88 |
| Full hybrid engine | Hard challenge (103) | ~91% | ~0.90 | ~0.91 | ~0.90 |

> Note: Results may vary depending on threshold and weight configuration.
> Full evaluation details are in `models/lexical_model/lexical_training_summary.json`
> and `models/semantic_arabert/training_summary.json`.
