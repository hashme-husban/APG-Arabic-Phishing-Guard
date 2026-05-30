# APG Dataset Policy

## Overview

APG — Arabic Phishing Guard uses a curated, multi-source Arabic phishing and SMS dataset
focused on the Jordanian digital context. This document describes the dataset composition,
what is included in this repository, and what is excluded and why.

---

## Dataset Summary

| Split / Set                    | Examples | Description |
|-------------------------------|----------|-------------|
| Main training split            | 3,576    | Balanced augmented Arabic phishing/legitimate |
| Focused add-on split           | 368      | Jordan-context hard negatives and edge cases |
| Validation set                 | 124      | Held-out validation for tuning |
| Test set                       | 124      | Final evaluation set (not used during training) |
| Hard challenge set             | 103      | Adversarial/hard-to-classify examples |
| Behavioral phrase entries      | 1,135    | Arabic phishing behavior phrase dictionary |
| Jordan-focused entity registry | 166      | Banks, telecoms, government entities (Jordan) |

The full dataset statistics are documented in [docs/DATASET_SUMMARY.md](../docs/DATASET_SUMMARY.md).

---

## What Is Included in This Repository

- `data/samples/` — A small 20-row safe synthetic sample for illustration and
  quick testing. All examples in this folder are APG-generated synthetic data.
- `data/raw/synthetic_datasets/` — Batch-generated synthetic Arabic SMS/phishing examples
  produced during the APG augmentation pipeline. These are original synthetic outputs.

---

## What Is Excluded and Why

- `data/processed/` — **Not included in public repository.**
  The processed training, validation, and test splits were derived from a combination
  of the original Kaggle source and synthetic augmentation. Because the processed splits
  contain content traceable to the Kaggle dataset, they are excluded pending confirmation
  of redistribution rights.

- `data/challenge_sets/` — **Not included in public repository.**
  Curated adversarial challenge sets may contain content derived from external sources.
  Excluded as a precaution.

- `data/raw/original_datasets/` — **Not included.**
  Original Arabic email data was sourced from the public Kaggle dataset
  **"Arabic Phishing and Legitimate emails — Samples"**. Redistribution rights for
  third-party Kaggle datasets are not always clearly stated, so the raw originals are
  excluded from this public repository.

> Full processed datasets can be provided to qualified researchers upon request
> once redistribution rights are confirmed with the original source.

---

## Data Sources

- **Synthetic data** — Batch-generated Arabic SMS and phishing examples created as part
  of the APG training augmentation pipeline (100% APG-generated; safe for public release).
- **Kaggle source dataset** — "Arabic Phishing and Legitimate emails — Samples" (Kaggle).
  Not redistributed here.
- **Behavioral phrase dictionary** — Manually curated Arabic phishing behavioral phrases
  (urgency signals, impersonation cues, action pressure patterns).
- **Jordan entity registry** — Manually compiled registry of Jordanian banks, telecoms,
  government portals, and payment services for entity impersonation detection.

---

## Privacy and Ethics

- All included data has been reviewed for accidental PII exposure.
- No real user messages, email accounts, or personal identifiers are included.
- Synthetic examples are generated from templates and do not correspond to real individuals.
- This repository does not include challenge examples or test splits that may contain
  content traceable to real-world phishing campaigns.

---

## Reproducibility

To retrain the APG models from scratch:

1. Download the Kaggle dataset: "Arabic Phishing and Legitimate emails — Samples"
2. Place raw CSV files in `data/raw/original_datasets/csv/`
3. Run the preprocessing pipeline in `backend/app/data/`
4. Run `layer_02_lexical/train_lexical_layer.py` to retrain the TF-IDF classifier
5. Fine-tune AraBERT using the scripts in `models/semantic_arabert/`

See [docs/SETUP_GUIDE.md](../docs/SETUP_GUIDE.md) for full setup instructions.
