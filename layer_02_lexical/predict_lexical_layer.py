import re
import joblib
from pathlib import Path

BUNDLE_PATH = Path("./lexical_layer_model/lexical_model_bundle.joblib")

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

def lexical_predict(text: str):
    clean = preprocess_text(text)
    X = vectorizer.transform([clean])
    score = clf.predict_proba(X)[:, 1][0]
    label = "phishing" if score >= threshold else "legit"
    return {
        "clean_text": clean,
        "lexical_score": round(float(score * 100), 2),
        "threshold": round(float(threshold), 2),
        "label": label
    }

if __name__ == "__main__":
    msg = input("Enter message: ")
    print(lexical_predict(msg))
