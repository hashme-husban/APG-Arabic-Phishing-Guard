from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .schemas import ModelScores

logger = logging.getLogger("apg.analyzer.ai")


def _repo_candidates(*parts: str) -> list[Path]:
    current = Path(__file__).resolve()
    env_key = "APG_SEMANTIC_MODEL_PATH" if parts[:2] == ("semantic_arabert", "final_model") else "APG_LEXICAL_MODEL_PATH"
    candidates: list[Path] = []
    if os.getenv(env_key):
        candidates.append(Path(os.getenv(env_key, "")))
    candidates.extend(
        [
            Path("/app/models", *parts),
            current.parents[4] / "models" / Path(*parts),
            current.parents[3] / "models" / Path(*parts),
        ]
    )
    return candidates


def _first_existing(candidates: list[Path], expected_file: str) -> Path:
    for candidate in candidates:
        if (candidate / expected_file).exists() or (candidate.exists() and candidate.name == expected_file):
            return candidate
    return candidates[0]


class SemanticModel:
    def __init__(self) -> None:
        self.path = _first_existing(_repo_candidates("semantic_arabert", "final_model"), "model.safetensors")
        self.threshold_path = self.path / "best_threshold.json"
        self.adapter = None
        self.loaded = False
        self.error: str | None = None
        try:
            from layers.layer_04_text_intelligence.semantic_adapter import SemanticModelAdapter

            self.adapter = SemanticModelAdapter(str(self.path), str(self.threshold_path))
            self.loaded = bool(getattr(self.adapter, "available", False))
            self.error = getattr(self.adapter, "_init_error", None)
        except Exception as exc:
            self.error = str(exc)
            logger.warning("semantic model adapter failed: %s", exc)

    def score(self, text: str) -> tuple[float, dict[str, Any]]:
        if not self.adapter:
            return 0.0, {"available": False, "init_error": self.error}
        result = self.adapter.evaluate(text)
        return float(result.get("risk_score") or 0.0), result


class LexicalModel:
    def __init__(self) -> None:
        self.path = _first_existing(_repo_candidates("lexical_model"), "lexical_model_bundle.joblib")
        self.bundle_path = self.path / "lexical_model_bundle.joblib" if self.path.is_dir() else self.path
        self.threshold_path = self.path / "lexical_thresholds.json" if self.path.is_dir() else self.path.with_name("lexical_thresholds.json")
        self.adapter = None
        self.loaded = False
        self.error: str | None = None
        try:
            from layers.layer_04_text_intelligence.lexical_adapter import LexicalModelAdapter

            self.adapter = LexicalModelAdapter(str(self.bundle_path), str(self.threshold_path))
            self.loaded = bool(getattr(self.adapter, "available", False))
            self.error = getattr(self.adapter, "_init_error", None)
        except Exception as exc:
            self.error = str(exc)
            logger.warning("lexical model adapter failed: %s", exc)

    def score(self, text: str) -> tuple[float, dict[str, Any]]:
        if not self.adapter:
            return 0.0, {"available": False, "init_error": self.error}
        result = self.adapter.evaluate(text)
        return float(result.get("risk_score") or 0.0), result


class AIAdapter:
    def __init__(self) -> None:
        self.semantic = SemanticModel()
        self.lexical = LexicalModel()

    def score(self, text: str) -> ModelScores:
        semantic_score, semantic_details = self.semantic.score(text)
        lexical_score, lexical_details = self.lexical.score(text)
        return ModelScores(
            semantic_score=semantic_score,
            lexical_score=lexical_score,
            semantic_scaled=int(round(semantic_score * 100)) if self.semantic.loaded else 0,
            lexical_scaled=int(round(lexical_score * 100)) if self.lexical.loaded else 0,
            semantic_details=semantic_details,
            lexical_details=lexical_details,
        )
