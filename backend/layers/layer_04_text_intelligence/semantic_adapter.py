from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class SemanticModelAdapter:
    """Transformer-based semantic classifier with graceful fallback.

    The original implementation hard-failed when transformers/torch or the model directory
    were not available. This version keeps the backend bootable and returns a neutral result
    when the semantic model cannot be loaded.
    """

    def __init__(
        self,
        model_dir: Optional[str],
        threshold_path: Optional[str] = None,
        device: Optional[str] = None,
        max_length: int = 256,
    ) -> None:
        self.model_dir = Path(model_dir) if model_dir else None
        self.threshold = self._load_threshold(threshold_path)
        self.max_length = max_length
        self.device_name = device or "auto"
        self.available = False
        self.model_version = self.model_dir.name if self.model_dir else "semantic_unavailable"
        self._init_error: Optional[str] = None

        self._torch = None
        self.tokenizer = None
        self.model = None
        self.device = None

        if not self.model_dir or not self.model_dir.exists():
            self._init_error = f"Semantic model directory not found: {self.model_dir}"
            return

        try:
            import torch  # type: ignore
            from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore
        except Exception as exc:  # pragma: no cover - env dependent
            self._init_error = f"Semantic dependencies are unavailable: {exc}"
            return

        try:
            self._torch = torch
            self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
            self.model = AutoModelForSequenceClassification.from_pretrained(str(self.model_dir))
            self.model.to(self.device)
            self.model.eval()
            self.available = True
            self.model_version = self.model_dir.name
        except Exception as exc:
            self._init_error = f"Failed to load semantic model: {exc}"
            self.available = False

    def _load_threshold(self, threshold_path: Optional[str]) -> float:
        if not threshold_path:
            return 0.5

        path = Path(threshold_path)
        if not path.exists():
            return 0.5

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("best_threshold", data.get("threshold", 0.5)))
        except Exception:
            return 0.5

    def _normalize_label(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower().replace(" ", "_")

    def _find_index_by_keywords(self, labels: List[str], keywords: List[str]) -> Optional[int]:
        for idx, label in enumerate(labels):
            if any(keyword in label for keyword in keywords):
                return idx
        return None

    def _resolve_indices(self, num_labels: int) -> Dict[str, Optional[int]]:
        id2label = getattr(self.model.config, "id2label", None) or {}
        labels = [self._normalize_label(id2label.get(i, str(i))) for i in range(num_labels)]

        phishing_idx = self._find_index_by_keywords(labels, ["phish", "spam", "fraud", "malicious"])
        suspicious_idx = self._find_index_by_keywords(labels, ["suspicious", "suspect", "gray", "uncertain"])
        safe_idx = self._find_index_by_keywords(labels, ["legit", "ham", "safe", "benign", "normal"])

        if num_labels == 2:
            if phishing_idx is None:
                phishing_idx = 1
            if safe_idx is None:
                safe_idx = 0 if phishing_idx == 1 else 1

        return {
            "phishing_idx": phishing_idx,
            "suspicious_idx": suspicious_idx,
            "safe_idx": safe_idx,
        }

    def _neutral_result(self, text: str = "") -> Dict[str, Any]:
        return {
            "model_type": "semantic",
            "model_version": self.model_version,
            "risk_score": 0.5,
            "component_label": "suspicious" if text else "not_enough_text",
            "confidence": 0.0 if not text else 0.12,
            "threshold_used": self.threshold,
            "raw_probabilities": {},
            "available": False,
            "init_error": self._init_error,
        }

    def evaluate(self, text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return self._neutral_result("")

        if not self.available or self.model is None or self.tokenizer is None or self._torch is None:
            return self._neutral_result(text)

        torch = self._torch
        encoded = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            outputs = self.model(**encoded)
            logits = outputs.logits.detach().cpu().squeeze(0)

        if getattr(logits, "ndim", 0) == 0:
            logits = logits.unsqueeze(0)

        num_labels = int(logits.shape[-1])

        if num_labels == 1:
            phishing_prob = torch.sigmoid(logits)[0].item()
            risk_score = float(phishing_prob)
            raw_probabilities = {
                "phishing": round(phishing_prob, 6),
                "safe": round(1.0 - phishing_prob, 6),
            }
        else:
            probs = torch.softmax(logits, dim=-1).tolist()
            indices = self._resolve_indices(num_labels)

            phishing_prob = probs[indices["phishing_idx"]] if indices["phishing_idx"] is not None else 0.0
            suspicious_prob = probs[indices["suspicious_idx"]] if indices["suspicious_idx"] is not None else 0.0
            safe_prob = probs[indices["safe_idx"]] if indices["safe_idx"] is not None else 0.0

            risk_score = float(min(1.0, phishing_prob + (0.5 * suspicious_prob))) if num_labels >= 3 else float(phishing_prob)
            raw_probabilities = {
                "phishing": round(phishing_prob, 6),
                "suspicious": round(suspicious_prob, 6),
                "safe": round(safe_prob, 6),
            }

        if risk_score >= self.threshold:
            label = "phishing"
        elif risk_score <= max(0.20, self.threshold - 0.28):
            label = "safe"
        else:
            label = "suspicious"

        confidence = max(0.0, min(1.0, abs(risk_score - self.threshold) * 2.0))

        return {
            "model_type": "semantic",
            "model_version": self.model_version,
            "risk_score": round(risk_score, 6),
            "component_label": label,
            "confidence": round(confidence, 6),
            "threshold_used": self.threshold,
            "raw_probabilities": raw_probabilities,
            "available": True,
            "init_error": None,
        }
