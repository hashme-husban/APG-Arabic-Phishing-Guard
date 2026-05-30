"""
APG Risk Intelligence Engine v1

Select engine via env var:
  APG_ANALYZER_ENGINE=risk_engine_v1   (default)
  APG_ANALYZER_ENGINE=v5               (legacy fallback)
"""
from .service import RiskEngineV1Service, get_risk_engine_service

__all__ = ["RiskEngineV1Service", "get_risk_engine_service"]
