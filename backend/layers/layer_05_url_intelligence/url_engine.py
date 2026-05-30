from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .canonicalizer import URLCanonicalizer
from .feature_extractor import URLFeatureExtractor
from .rules_engine import URLRulesEngine
from .model_adapter import URLModelAdapter
from .external_reputation import ExternalReputationAdapter
from .fusion import URLFusionEngine


class URLIntelligenceEngine:
    def __init__(
        self,
        canonicalizer: Optional[URLCanonicalizer] = None,
        feature_extractor: Optional[URLFeatureExtractor] = None,
        rules_engine: Optional[URLRulesEngine] = None,
        model_adapter: Optional[URLModelAdapter] = None,
        external_reputation: Optional[ExternalReputationAdapter] = None,
        fusion_engine: Optional[URLFusionEngine] = None,
        config_path: str = "configs/url_layer_config.json",
    ) -> None:
        self.canonicalizer = canonicalizer or URLCanonicalizer()
        self.feature_extractor = feature_extractor or URLFeatureExtractor(config_path=config_path)
        self.rules_engine = rules_engine or URLRulesEngine(config_path=config_path)
        self.model_adapter = model_adapter or URLModelAdapter(model_bundle_path=None)
        self.external_reputation = external_reputation or ExternalReputationAdapter(config_path=config_path)
        self.fusion_engine = fusion_engine or URLFusionEngine(config_path=config_path)
        self.config = self._load_json(config_path)

    def _load_json(self, path_str: str) -> Dict[str, Any]:
        path = Path(path_str)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _prepare_sources(self, urls: List[str], url_candidates: List[str]) -> List[Dict[str, Any]]:
        sources: Dict[str, Dict[str, Any]] = {}

        def add_source(input_url: str, original_source: str, source_kind: str, source_was_obfuscated: bool) -> None:
            repaired = self.canonicalizer.repair_obfuscation(input_url)
            with_scheme = self.canonicalizer.ensure_scheme(repaired)
            key = with_scheme.lower().strip()

            if not key:
                return

            if key not in sources:
                sources[key] = {
                    "input_url": with_scheme,
                    "original_sources": [original_source],
                    "source_kinds": [source_kind],
                    "source_was_obfuscated": bool(source_was_obfuscated),
                }
            else:
                entry = sources[key]
                if original_source not in entry["original_sources"]:
                    entry["original_sources"].append(original_source)
                if source_kind not in entry["source_kinds"]:
                    entry["source_kinds"].append(source_kind)
                entry["source_was_obfuscated"] = entry["source_was_obfuscated"] or bool(source_was_obfuscated)

        for url in urls or []:
            add_source(url, url, "provided", False)

        for token in url_candidates or []:
            repaired = self.canonicalizer.repair_obfuscation(token)
            with_scheme = self.canonicalizer.ensure_scheme(repaired)
            add_source(with_scheme, token, "candidate_recovered", True)

        return list(sources.values())

    def _aggregate_reasons(self, details: List[Dict[str, Any]], dominant: Dict[str, Any]) -> List[str]:
        reasons = list(dominant.get("reasons", []))

        risky_count = sum(1 for item in details if item.get("label") in {"suspicious", "phishing"})
        if len(details) > 1:
            reasons.append(f"The message contains {len(details)} URL(s); the highest-risk URL was used as the main signal.")

        if risky_count > 1:
            reasons.append("More than one URL in the message shows risky characteristics.")

        external = dominant.get("external_result")
        if external and external.get("available") and external.get("hit"):
            provider = external.get("provider", "external reputation service")
            reasons.append(f"External reputation also flagged the dominant URL via {provider}.")

        return reasons[:10]

    def _union_flags(self, details: List[Dict[str, Any]]) -> List[str]:
        seen = set()
        result = []
        for item in details:
            for flag in item.get("flags", []):
                if flag not in seen:
                    seen.add(flag)
                    result.append(flag)
        return result

    def evaluate(
        self,
        urls: List[str],
        url_candidates: List[str] | None = None,
        claimed_entity: Dict[str, Any] | None = None,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        url_sources = self._prepare_sources(urls or [], url_candidates or [])

        if not url_sources:
            return {
                "url_score": 0.0,
                "url_label": "absent",
                "url_flags": [],
                "url_reasons": ["No URL was available for analysis."],
                "analyzed_urls": [],
                "url_details": [],
                "url_analysis_mode": "no_url"
            }

        details = []
        url_count = len(url_sources)

        for source in url_sources:
            canonical_info = self.canonicalizer.canonicalize(
                raw_url=source["input_url"],
                source_was_obfuscated=source["source_was_obfuscated"],
                original_source=source["original_sources"][0],
                source_tags=source["source_kinds"],
            )

            features = self.feature_extractor.extract(
                canonical_info=canonical_info,
                claimed_entity=claimed_entity,
            )

            rules_result = self.rules_engine.evaluate(
                canonical_info=canonical_info,
                features=features,
                claimed_entity=claimed_entity,
                url_count=url_count,
            )

            model_result = self.model_adapter.evaluate(features)

            local_fusion = self.fusion_engine.evaluate(
                rules_result=rules_result,
                model_result=model_result,
                external_result=None,
            )

            external_result = self.external_reputation.evaluate(
                canonical_url=canonical_info.get("canonical_url", ""),
                local_score=float(local_fusion.get("fused_score", 0.0)),
                flags=rules_result.get("rules_flags", []),
            )

            final_fusion = self.fusion_engine.evaluate(
                rules_result=rules_result,
                model_result=model_result,
                external_result=external_result,
            )

            detail = {
                "original_url": canonical_info.get("original_url"),
                "original_sources": source["original_sources"],
                "source_kinds": source["source_kinds"],
                "source_was_obfuscated": source["source_was_obfuscated"],
                "canonical_url": canonical_info.get("canonical_url"),
                "registrable_domain": canonical_info.get("registrable_domain"),
                "rules_score": rules_result.get("rules_score"),
                "model_score": None if not model_result else model_result.get("model_score"),
                "fused_score": final_fusion.get("fused_score"),
                "label": final_fusion.get("fused_label"),
                "flags": rules_result.get("rules_flags", []),
                "reasons": rules_result.get("rules_reasons", []),
                "features": features,
                "fusion_mode": final_fusion.get("fusion_mode"),
                "fusion_confidence": final_fusion.get("fusion_confidence"),
                "external_result": external_result,
            }
            details.append(detail)

        dominant = max(details, key=lambda x: float(x.get("fused_score", 0.0)))
        url_score = float(dominant.get("fused_score", 0.0))

        if len(details) > 1:
            multi_bonus = float(self.config.get("weights", {}).get("MULTIPLE_URLS", 0.04))
            risky_others = sum(
                1 for d in details
                if d is not dominant and d.get("label") in {"suspicious", "phishing"}
            )
            url_score = min(1.0, url_score + min(0.08, risky_others * multi_bonus))

        url_label = self.fusion_engine.label_from_score(url_score)
        reasons = self._aggregate_reasons(details, dominant)
        flags = self._union_flags(details)

        analysis_modes = {d.get("fusion_mode") for d in details}
        if "hybrid_with_external_hit" in analysis_modes or "hybrid_with_external_safe" in analysis_modes:
            overall_mode = "hybrid_with_external"
        elif "hybrid_local" in analysis_modes:
            overall_mode = "hybrid_local"
        else:
            overall_mode = "rules_only"

        return {
            "url_score": round(url_score, 6),
            "url_label": url_label,
            "url_flags": flags,
            "url_reasons": reasons,
            "analyzed_urls": [d["canonical_url"] for d in details],
            "dominant_url": dominant.get("canonical_url"),
            "url_details": details,
            "url_analysis_mode": overall_mode
        }
