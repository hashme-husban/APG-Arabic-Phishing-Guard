from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional


class URLModelAdapter:
    """Optional URL ML adapter with lazy dependency loading."""

    def __init__(self, model_bundle_path: Optional[str] = None) -> None:
        self.available = False
        self.bundle = None
        self.estimator = None
        self.scaler = None
        self.feature_order: List[str] = []
        self._joblib = None
        self._numpy = None
        self._init_error = None

        if not model_bundle_path:
            return

        path = Path(model_bundle_path)
        if not path.exists():
            self._init_error = f"Model bundle not found: {path}"
            return

        try:
            import joblib  # type: ignore
            import numpy as np  # type: ignore

            self._joblib = joblib
            self._numpy = np
            self.bundle = joblib.load(path)
            self._unpack_bundle()
            self.available = self.estimator is not None
        except Exception as exc:
            self.available = False
            self._init_error = str(exc)

    def _unpack_bundle(self) -> None:
        if self.bundle is None:
            return

        if hasattr(self.bundle, "predict_proba") or hasattr(self.bundle, "decision_function"):
            self.estimator = self.bundle
            return

        if isinstance(self.bundle, dict):
            self.estimator = (
                self.bundle.get("model")
                or self.bundle.get("classifier")
                or self.bundle.get("estimator")
            )
            self.scaler = self.bundle.get("scaler")
            self.feature_order = list(self.bundle.get("feature_order", self.bundle.get("feature_names", [])))

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def _resolve_positive_index(self, classes: Optional[List[Any]], num_probs: int) -> int:
        if not classes:
            return 1 if num_probs >= 2 else 0

        normalized = [str(c).strip().lower() for c in classes]
        for i, label in enumerate(normalized):
            if any(k in label for k in ["phishing", "phish", "spam", "fraud", "malicious"]):
                return i
        for i, label in enumerate(normalized):
            if label in {"1", "true", "positive"}:
                return i
        return 1 if num_probs >= 2 else 0

    def evaluate(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.available or self.estimator is None or self._numpy is None:
            return None

        numeric_features = {
            k: float(v)
            for k, v in features.items()
            if isinstance(v, (int, float, bool))
        }

        if self.feature_order:
            row = [numeric_features.get(name, 0.0) for name in self.feature_order]
        else:
            ordered_keys = sorted(numeric_features.keys())
            row = [numeric_features[k] for k in ordered_keys]
            self.feature_order = ordered_keys

        np = self._numpy
        X = np.array([row], dtype=float)

        if self.scaler is not None:
            X = self.scaler.transform(X)

        if hasattr(self.estimator, "predict_proba"):
            probs = self.estimator.predict_proba(X)[0]
            classes = list(getattr(self.estimator, "classes_", []))
            pos_idx = self._resolve_positive_index(classes, len(probs))
            model_score = float(probs[pos_idx])
        elif hasattr(self.estimator, "decision_function"):
            raw_score = self.estimator.decision_function(X)
            raw_score = float(np.ravel(raw_score)[0])
            model_score = self._sigmoid(raw_score)
        else:
            return None

        return {
            "model_score": round(model_score, 6),
            "model_used": True,
            "feature_count": len(self.feature_order),
            "init_error": self._init_error,
        }
