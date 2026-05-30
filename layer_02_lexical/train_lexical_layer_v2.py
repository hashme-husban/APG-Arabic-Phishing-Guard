import os
import re
import json
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from sklearn.pipeline import FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV

parser = argparse.ArgumentParser()
parser.add_argument("--train_file", default="arabic_phishing_guard_train_augmented_recommended_simple.csv")
parser.add_argument("--focused_addon_file", default="arabic_phishing_guard_focused_addon_balanced_simple.csv")
parser.add_argument("--val_file", default="arabic_phishing_guard_val_simple.csv")
parser.add_argument("--test_file", default="arabic_phishing_guard_test_simple.csv")
parser.add_argument("--hard_file", default="arabic_phishing_guard_hard_challenge_set.csv")
parser.add_argument("--output_dir", default="lexical_layer_model_v2")
parser.add_argument("--model_type", choices=["logistic", "svm"], default="logistic")
parser.add_argument("--use_focused_addon", action="store_true")
args = parser.parse_args()

OUT = Path(args.output_dir)
OUT.mkdir(parents=True, exist_ok=True)

ARABIC_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
TATWEEL = "\u0640"

def normalize_arabic(text: str) -> str:
    text = str(text).strip()
    text = text.replace(TATWEEL, "")
    text = re.sub(ARABIC_DIACRITICS, "", text)
    text = re.sub(r"[إأآا]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("ؤ", "و").replace("ئ", "ي")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def preprocess_text(text: str) -> str:
    text = str(text)
    text = re.sub(r"(https?://\S+|www\.\S+)", " <URL> ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", " <EMAIL> ", text)
    text = re.sub(r"\b(?:\+?\d[\d\-\s]{7,}\d)\b", " <PHONE> ", text)
    text = re.sub(r"(otp|رمز|كود|code)\s*[:\-]?\s*\d{4,8}", " <OTP> ", text, flags=re.IGNORECASE)
    text = re.sub(r"[^\w\s\u0600-\u06FF<>]", " ", text)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = text.lower()
    text = normalize_arabic(text)
    return text

def load_csv(path, keep_extra_cols=None):
    keep_extra_cols = keep_extra_cols or []
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "text" not in df.columns or "label" not in df.columns:
        raise ValueError(f"{path} must contain text and label columns")

    cols = ["text", "label"] + [c for c in keep_extra_cols if c in df.columns]
    df = df[cols].copy()

    df["text"] = df["text"].astype(str).apply(preprocess_text)
    df["label"] = df["label"].astype(str)
    df = df[df["label"].isin(["legit", "phishing"])].copy()
    df = df[df["text"].str.len() > 0].copy()

    # dedupe by text+label but keep first metadata row
    df = df.drop_duplicates(subset=["text", "label"]).reset_index(drop=True)
    return df

train_df = load_csv(args.train_file)
if args.use_focused_addon:
    addon_df = load_csv(args.focused_addon_file)
    train_df = pd.concat([train_df, addon_df], ignore_index=True)
    train_df = train_df.drop_duplicates(subset=["text", "label"]).reset_index(drop=True)

val_df = load_csv(args.val_file)
test_df = load_csv(args.test_file)
hard_df = load_csv(args.hard_file, keep_extra_cols=["challenge_type", "why_it_is_hard"])

vectorizer = FeatureUnion([
    ("word_tfidf", TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        max_features=50000,
        sublinear_tf=True
    )),
    ("char_tfidf", TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        max_features=120000,
        sublinear_tf=True
    ))
])

X_train = vectorizer.fit_transform(train_df["text"])
X_val   = vectorizer.transform(val_df["text"])
X_test  = vectorizer.transform(test_df["text"])
X_hard  = vectorizer.transform(hard_df["text"])

y_train = train_df["label"].map({"legit": 0, "phishing": 1}).values
y_val   = val_df["label"].map({"legit": 0, "phishing": 1}).values
y_test  = test_df["label"].map({"legit": 0, "phishing": 1}).values
y_hard  = hard_df["label"].map({"legit": 0, "phishing": 1}).values

def build_model(model_type):
    if model_type == "logistic":
        return LogisticRegression(C=4.0, class_weight="balanced", max_iter=4000, solver="liblinear")
    base = LinearSVC(C=1.5, class_weight="balanced")
    return CalibratedClassifierCV(base, method="sigmoid", cv=5)

clf = build_model(args.model_type)
clf.fit(X_train, y_train)

if not hasattr(clf, "predict_proba"):
    raise RuntimeError("Chosen model does not expose predict_proba")

val_scores = clf.predict_proba(X_val)[:, 1]
best_threshold = 0.5
best_f1 = -1.0
threshold_rows = []

for t in np.arange(0.30, 0.81, 0.05):
    preds = (val_scores >= t).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(y_val, preds, average="binary", zero_division=0)
    threshold_rows.append({
        "threshold": round(float(t), 2),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
    })
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = float(t)

def evaluate_dataset(name, X, y, df, threshold):
    scores = clf.predict_proba(X)[:, 1]
    preds = (scores >= threshold).astype(int)

    acc = accuracy_score(y, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(y, preds, average="binary", zero_division=0)
    cm = confusion_matrix(y, preds)

    out = {
        "accuracy": round(float(acc), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "confusion_matrix": cm.tolist()
    }

    pred_df = df.copy()
    pred_df["score"] = scores
    pred_df["pred"] = np.where(preds == 1, "phishing", "legit")
    pred_df["correct"] = (preds == y)
    pred_df.to_csv(OUT / f"{name}_predictions.csv", index=False, encoding="utf-8-sig")
    return out, pred_df

test_metrics, test_pred_df = evaluate_dataset("test", X_test, y_test, test_df, best_threshold)
hard_metrics, hard_pred_df = evaluate_dataset("hard", X_hard, y_hard, hard_df, best_threshold)

hard_breakdown = None
if "challenge_type" in hard_pred_df.columns:
    hard_breakdown = (
        hard_pred_df.groupby("challenge_type")["correct"]
        .mean()
        .sort_values()
        .round(4)
        .to_dict()
    )

bundle = {
    "vectorizer": vectorizer,
    "classifier": clf,
    "threshold": best_threshold,
    "model_type": args.model_type,
    "label_map": {"legit": 0, "phishing": 1},
}
joblib.dump(bundle, OUT / "lexical_model_bundle.joblib")

with open(OUT / "lexical_thresholds.json", "w", encoding="utf-8") as f:
    json.dump({"best_threshold": best_threshold, "validation_grid": threshold_rows}, f, ensure_ascii=False, indent=2)

summary = {
    "model_type": args.model_type,
    "used_focused_addon": args.use_focused_addon,
    "train_rows": int(len(train_df)),
    "val_rows": int(len(val_df)),
    "test_rows": int(len(test_df)),
    "hard_rows": int(len(hard_df)),
    "best_threshold": best_threshold,
    "best_val_f1": round(float(best_f1), 4),
    "test_metrics": test_metrics,
    "hard_metrics": hard_metrics,
    "hard_breakdown": hard_breakdown,
}
with open(OUT / "lexical_training_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print("\n===== LEXICAL LAYER SUMMARY =====")
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(f"\nSaved to: {OUT}")
