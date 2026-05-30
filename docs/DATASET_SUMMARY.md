# APG — Dataset Summary

## Overview

APG uses a curated multi-source Arabic phishing and SMS dataset with a focus on the
Jordanian digital context. The dataset combines publicly available Arabic email data,
synthetically generated SMS examples, and manually curated behavioral dictionaries.

---

## Dataset Composition

### Training Splits

| File | Examples | Description |
|------|----------|-------------|
| `arabic_phishing_guard_train_simple.csv` | ~2,900 | Base training set |
| `arabic_phishing_guard_train_augmented_recommended_simple.csv` | 3,576 | Augmented recommended split (primary) |
| `arabic_phishing_guard_focused_addon_balanced_simple.csv` | 368 | Jordan-context focused add-on |
| `arabic_phishing_guard_val_simple.csv` | 124 | Validation set |
| `arabic_phishing_guard_test_simple.csv` | 124 | Held-out test set |

### Challenge Sets

| File | Examples | Description |
|------|----------|-------------|
| `arabic_phishing_guard_hard_challenge_set.csv` | 103 | Hard/adversarial examples |
| `arabic_phishing_guard_layered_challenge_v2.csv` | — | Layered challenge set v2 |

### Dictionaries and Registries

| Resource | Entries | Description |
|----------|---------|-------------|
| Behavioral phrase dictionary | 1,135 | Arabic phishing behavioral phrases |
| Jordan entity registry | 166 | Jordanian banks, telecoms, government portals |

---

## Data Sources

### 1. Original Arabic Email Dataset (Kaggle)

Source: "Arabic Phishing and Legitimate emails — Samples" (Kaggle)

This dataset provides a base of Arabic phishing and legitimate email examples. It was
used as a starting point for preprocessing and augmentation.

**Not redistributed** in this repository — see [data/README.md](../data/README.md).

### 2. Synthetic SMS/Phishing Examples

APG generated synthetic Arabic SMS examples through batch augmentation to:
- Balance class distribution
- Increase coverage of Jordan-specific phishing patterns
- Introduce variety in phrasing and social engineering tactics

Synthetic data files are included in `data/raw/synthetic_datasets/`.

### 3. Manual Curation

The behavioral phrase dictionary and entity registry were manually curated:
- Phrases sourced from observed Arabic phishing patterns and security research
- Entities compiled from the Jordanian financial, telecom, and government sector

---

## Preprocessing Pipeline

Raw data → preprocessing steps:

1. **Text normalization** — Remove diacritics, normalize Arabic letter variants
2. **Deduplication** — Remove duplicate messages
3. **Class balancing** — Undersample/oversample to balance phishing vs. legitimate
4. **Split stratification** — Stratified split by label and source to ensure balanced evaluation
5. **Augmentation** — Paraphrase-based augmentation for underrepresented patterns

---

## Column Schema

All processed CSV files follow a simple two-column schema:

| Column | Type | Description |
|--------|------|-------------|
| `text` | string | Arabic message text |
| `label` | int (0/1) | 0 = legitimate, 1 = phishing |

---

## Privacy and Ethics

- No real user messages or personal identifiers are included
- Synthetic examples are generated from templates
- Original Kaggle data is not redistributed out of respect for the source's terms
- Challenge examples were crafted to probe model weaknesses, not sourced from real attacks

---

## Limitations

- Dataset is weighted toward Jordan-specific entities and colloquial Levantine Arabic
- Coverage of Gulf-dialect phishing is limited
- SMS/notification format is primary; email threading patterns are less represented
- Class balance was enforced — real-world distribution of phishing to legitimate may differ
