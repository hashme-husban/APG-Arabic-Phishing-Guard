# APG Model Artifacts

## Overview

APG uses a **hybrid AI / risk engine** that combines two machine-learning models with a
deterministic rule layer. This document describes the models, their role, and what is
included or excluded from this repository.

---

## Models Used

### 1. AraBERT Semantic Classifier (Advisory Layer)

| Property | Value |
|----------|-------|
| Base model | `aubmindlab/bert-base-arabertv2` |
| Task | Arabic text binary classification (phishing / legitimate) |
| Fine-tuned on | APG Arabic phishing dataset (3,576 training examples) |
| Output | Semantic confidence score (0.0 – 1.0) used as advisory input |
| Role | Provides deep semantic signal; output feeds into fusion layer |

**Checkpoint status:** The full fine-tuned weights (`model.safetensors`, ~516 MB) are
**excluded from this repository** because of GitHub's file size limits and to keep the
repository lightweight for code review.

Configuration metadata (`config.json`, `tokenizer.json`, `best_threshold.json`,
`training_summary.json`) is included so the architecture and training setup are visible.

> To obtain the fine-tuned weights, contact the APG team or re-train using the scripts in
> `models/semantic_arabert/` and the dataset in `data/processed/`.

---

### 2. TF-IDF Lexical Classifier (Advisory Layer)

| Property | Value |
|----------|-------|
| Model type | TF-IDF vectorizer + Logistic Regression (scikit-learn) |
| Bundle file | `models/lexical_model/lexical_model_bundle.joblib` (2.25 MB) |
| Task | Lexical/surface-feature phishing classification |
| Output | Lexical confidence score used as advisory input |
| Role | Fast, interpretable secondary signal; Arabic character n-gram features |

**Status:** The full model bundle is **included** in this repository (2.25 MB — within
GitHub limits). This model can be used to run the lexical advisory layer without the
AraBERT weights.

---

## How Models Are Used

Neither model makes the final verdict alone. Both feed into the **Decision Fusion Layer**
(`layers/layer_06_decision_fusion/`) alongside:

- Behavioral phishing rules
- URL intelligence
- Entity impersonation detection
- Sender verification

The **Output Layer** (`layers/layer_07_explanation/`) produces a final risk score and a
human-readable explanation in Arabic or English.

---

## Files in This Directory

```
models/
├── lexical_model/
│   ├── lexical_model_bundle.joblib      ← included (2.25 MB)
│   ├── lexical_thresholds.json          ← included
│   ├── lexical_training_summary.json    ← included
│   ├── hard_predictions.csv             ← included (evaluation output)
│   └── test_predictions.csv             ← included (evaluation output)
│
└── semantic_arabert/
    ├── final_model/
    │   ├── model.safetensors            ← EXCLUDED (516 MB — too large for GitHub)
    │   ├── config.json                  ← included (architecture config)
    │   └── tokenizer.json               ← included (tokenizer config)
    ├── best_threshold.json              ← included
    └── training_summary.json            ← included
```

---

## Re-training

To fine-tune AraBERT from scratch:

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run fine-tuning (requires GPU recommended, ~2–4 hours on consumer GPU)
python models/semantic_arabert/train_arabert.py \
    --data_dir data/processed \
    --output_dir models/semantic_arabert/final_model

# Evaluate
python models/semantic_arabert/evaluate.py
```

See `docs/AI_APPROACH.md` for full details on the training methodology.
