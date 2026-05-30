from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


class LexicalModelAdapter:
    """TF-IDF / vectorizer classifier adapter with graceful fallback."""

    def __init__(
        self,
        bundle_path: Optional[str],
        threshold_path: Optional[str] = None,
    ) -> None:
        self.bundle_path = Path(bundle_path) if bundle_path else None
        self.bundle = None
        self.model_version = self.bundle_path.name if self.bundle_path else "lexical_unavailable"
        self.threshold = 0.5
        self.pipeline = None
        self.vectorizer = None
        self.classifier = None
        self.label_map: Dict[str, Any] = {}
        self.available = False
        self._init_error: Optional[str] = None

        self._joblib = None
        self._np = None

        try:
            import joblib  # type: ignore
            import numpy as np  # type: ignore
            self._joblib = joblib
            self._np = np
        except Exception as exc:  # pragma: no cover - env dependent
            self._init_error = f"Lexical dependencies are unavailable: {exc}"
            return

        if not self.bundle_path or not self.bundle_path.exists():
            self._init_error = f"Lexical bundle not found: {self.bundle_path}"
            return

        try:
            self.bundle = self._joblib.load(self.bundle_path)
            self.threshold = self._load_threshold(threshold_path)
            self._unpack_bundle()
            self.available = True
        except Exception as exc:
            self._init_error = f"Failed to load lexical bundle: {exc}"
            self.available = False

    def _load_threshold(self, threshold_path: Optional[str]) -> float:
        if threshold_path:
            path = Path(threshold_path)
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    return float(data.get("best_threshold", data.get("threshold", 0.5)))
                except Exception:
                    pass

        if isinstance(self.bundle, dict):
            try:
                return float(self.bundle.get("threshold", 0.5))
            except Exception:
                pass

        return 0.5

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def _normalize_label(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower().replace(" ", "_")

    def _resolve_positive_index(self, classes: Optional[List[Any]], num_probs: int) -> int:
        if not classes:
            return 1 if num_probs >= 2 else 0

        normalized = [self._normalize_label(c) for c in classes]
        for i, label in enumerate(normalized):
            if any(k in label for k in ["phishing", "phish", "spam", "fraud", "malicious"]):
                return i
        for i, label in enumerate(normalized):
            if label in {"1", "true", "positive"}:
                return i
        return 1 if num_probs >= 2 else 0

    def _looks_like_pipeline(self, obj: Any) -> bool:
        return hasattr(obj, "predict") and (hasattr(obj, "predict_proba") or hasattr(obj, "decision_function"))

    def _looks_like_vectorizer(self, obj: Any) -> bool:
        return hasattr(obj, "transform")

    def _looks_like_classifier(self, obj: Any) -> bool:
        return hasattr(obj, "predict") and (hasattr(obj, "predict_proba") or hasattr(obj, "decision_function"))

    def _unpack_bundle(self) -> None:
        if self._looks_like_pipeline(self.bundle) and not isinstance(self.bundle, dict):
            self.pipeline = self.bundle
            return

        if isinstance(self.bundle, dict):
            self.label_map = self.bundle.get("label_map", {}) or {}
            direct_vectorizer = self.bundle.get("vectorizer")
            direct_classifier = self.bundle.get("classifier")

            if self._looks_like_vectorizer(direct_vectorizer) and self._looks_like_classifier(direct_classifier):
                self.vectorizer = direct_vectorizer
                self.classifier = direct_classifier
                return

            for key in ["pipeline", "model_pipeline", "model", "estimator"]:
                candidate = self.bundle.get(key)
                if self._looks_like_pipeline(candidate):
                    self.pipeline = candidate
                    return

        raise ValueError(
            "Unsupported lexical bundle structure. Expected pipeline or dict with vectorizer + classifier."
        )

    def _predict_with_estimator(self, estimator: Any, X: Any) -> Dict[str, Any]:
        np = self._np
        if hasattr(estimator, "predict_proba"):
            probs = estimator.predict_proba(X)[0]
            classes = list(getattr(estimator, "classes_", []))
            pos_idx = self._resolve_positive_index(classes, len(probs))
            phishing_prob = float(probs[pos_idx])
            return {"risk_score": phishing_prob, "classes": classes}

        if hasattr(estimator, "decision_function"):
            raw_score = estimator.decision_function(X)
            if isinstance(raw_score, np.ndarray):
                raw_score = float(np.ravel(raw_score)[0])
            phishing_prob = self._sigmoid(float(raw_score))
            return {"risk_score": phishing_prob, "classes": list(getattr(estimator, "classes_", []))}

        raise ValueError("Lexical estimator does not support predict_proba or decision_function.")

    def _neutral_result(self, text: str = "") -> Dict[str, Any]:
        return {
            "model_type": "lexical",
            "model_version": self.model_version,
            "risk_score": 0.5,
            "component_label": "suspicious" if text else "not_enough_text",
            "confidence": 0.0 if not text else 0.12,
            "threshold_used": self.threshold,
            "bundle_format": "unavailable",
            "label_map": self.label_map,
            "available": False,
            "init_error": self._init_error,
        }

    def evaluate(self, text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return self._neutral_result("")

        if not self.available:
            return self._neutral_result(text)

        if self.pipeline is not None:
            pred = self._predict_with_estimator(self.pipeline, [text])
            risk_score = pred["risk_score"]
            bundle_format = "pipeline"
        else:
            X = self.vectorizer.transform([text])
            pred = self._predict_with_estimator(self.classifier, X)
            risk_score = pred["risk_score"]
            bundle_format = "vectorizer_plus_classifier"

        if risk_score >= self.threshold:
            component_label = "phishing"
        elif risk_score <= max(0.20, self.threshold - 0.28):
            component_label = "safe"
        else:
            component_label = "suspicious"

        confidence = max(0.0, min(1.0, abs(risk_score - self.threshold) * 2.0))
        return {
            "model_type": "lexical",
            "model_version": self.model_version,
            "risk_score": round(float(risk_score), 6),
            "component_label": component_label,
            "confidence": round(confidence, 6),
            "threshold_used": self.threshold,
            "bundle_format": bundle_format,
            "label_map": self.label_map,
            "available": True,
            "init_error": None,
        }
