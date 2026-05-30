import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

BUNDLE_PATH = Path("./lexical_layer_model/lexical_model_bundle.joblib")
HARD_FILE = "arabic_phishing_guard_hard_challenge_set.csv"
OUT_FILE = "lexical_hard_breakdown_report.json"

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
    return normalize_arabic(text)

bundle = joblib.load(BUNDLE_PATH)
vectorizer = bundle["vectorizer"]
clf = bundle["classifier"]
threshold = bundle["threshold"]

df = pd.read_csv(HARD_FILE, encoding="utf-8-sig")
df["text"] = df["text"].astype(str).apply(preprocess_text)
df = df[df["label"].isin(["legit", "phishing"])].copy()

X = vectorizer.transform(df["text"])
y = df["label"].map({"legit": 0, "phishing": 1}).values
scores = clf.predict_proba(X)[:, 1]
preds = (scores >= threshold).astype(int)

acc = accuracy_score(y, preds)
precision, recall, f1, _ = precision_recall_fscore_support(y, preds, average="binary", zero_division=0)
cm = confusion_matrix(y, preds)

df["score"] = scores
df["pred"] = np.where(preds == 1, "phishing", "legit")
df["correct"] = (preds == y)

breakdown = None
if "challenge_type" in df.columns:
    breakdown = (
        df.groupby("challenge_type")["correct"]
        .mean()
        .sort_values()
        .round(4)
        .to_dict()
    )

report = {
    "threshold": threshold,
    "hard_metrics": {
        "accuracy": round(float(acc), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "confusion_matrix": cm.tolist()
    },
    "hard_breakdown": breakdown
}

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

df.to_csv("lexical_hard_predictions_with_breakdown.csv", index=False, encoding="utf-8-sig")

print(json.dumps(report, ensure_ascii=False, indent=2))
print("\nSaved:", OUT_FILE)
