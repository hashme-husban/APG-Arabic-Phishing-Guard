"""
APG Phase 4.1 — Promo / Discount False-Positive Evaluation
==========================================================

Regression checks for promotional discount language versus true financial
phishing context. Uses synthetic text and fake .test domains only.

Usage:
  cd backend
  python scripts/evaluate_behavioral_false_positives.py

Exit codes:
  0  all cases PASS
  1  one or more cases FAIL
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.risk_engine.service import RiskEngineV1Service  # noqa: E402


_SVC = RiskEngineV1Service()

_VERDICT_RANK = {
    "allow": 0,
    "caution": 1,
    "warn": 2,
    "block": 3,
}


@dataclass(frozen=True)
class EvalCase:
    id: int
    label: str
    text: str
    max_verdict: str | None = None
    min_verdict: str | None = None
    max_score: int | None = None
    forbidden_evidence: set[str] = field(default_factory=set)
    required_evidence: set[str] = field(default_factory=set)
    forbidden_entities: set[str] = field(default_factory=set)
    required_entities: set[str] = field(default_factory=set)


CASES: list[EvalCase] = [
    EvalCase(
        id=1,
        label="safe_discount_promo_url",
        text="عرض خاص خصم 50% على الباقات من زين https://example.test",
        max_verdict="warn",
        forbidden_evidence={"suspicious_financial_link"},
        forbidden_entities={"money_transaction"},
    ),
    EvalCase(
        id=2,
        label="safe_coupon_promo_url",
        text="كود خصم جديد لفترة محدودة، شاهد التفاصيل https://promo-example.test",
        max_verdict="allow",
        forbidden_evidence={"suspicious_financial_link"},
        forbidden_entities={"money_transaction"},
    ),
    EvalCase(
        id=3,
        label="safe_discount_percentage_no_url",
        text="تخفيضات نهاية الأسبوع على المنتجات",
        max_verdict="allow",
        forbidden_entities={"money_transaction"},
    ),
    EvalCase(
        id=4,
        label="safe_save_more_offer",
        text="وفر أكثر مع عروضنا الجديدة",
        max_verdict="allow",
        forbidden_entities={"money_transaction"},
    ),
    EvalCase(
        id=5,
        label="discount_login_request",
        text="اربح خصم 50% بعد تسجيل الدخول إلى حسابك من الرابط",
        min_verdict="caution",
        required_entities={"account"},
    ),
    EvalCase(
        id=6,
        label="discount_password_request",
        text="للحصول على الخصم أدخل كلمة المرور",
        min_verdict="block",
        required_evidence={"danger_password_request"},
        forbidden_entities={"money_transaction"},
    ),
    EvalCase(
        id=7,
        label="delivery_fee_payment_link",
        text="ادفع رسوم التوصيل 1.5 دينار من الرابط",
        min_verdict="caution",
        required_entities={"money_transaction"},
        required_evidence={"suspicious_financial_link"},
    ),
    EvalCase(
        id=8,
        label="bank_account_update_link",
        text="حسابك البنكي بحاجة لتحديث، ادخل الرابط",
        min_verdict="block",
        required_entities={"bank", "account"},
        required_evidence={"behavioral_account_takeover_url"},
    ),
    EvalCase(
        id=9,
        label="card_data_for_offer",
        text="أدخل بيانات البطاقة للاستفادة من العرض",
        min_verdict="block",
        required_evidence={"danger_card_request"},
    ),
    EvalCase(
        id=10,
        label="invoice_stop_service",
        text="سدد الفاتورة الآن لتجنب إيقاف الخدمة",
        min_verdict="caution",
    ),
    EvalCase(
        id=11,
        label="payment_received_receipt",
        text="تم استلام مبلغ 25 دينار في حسابك",
        max_verdict="allow",
        max_score=30,
        forbidden_evidence={"behavioral_payment_phishing"},
    ),
    EvalCase(
        id=12,
        label="awareness_payment_scam",
        text="تنبيه توعوي: احذر من رسالة تطلب دفع رسوم عبر رابط مجهول ولا تشارك بياناتك",
        max_verdict="allow",
        max_score=30,
    ),
]


def _rank(verdict: str) -> int:
    return _VERDICT_RANK.get(verdict, 99)


def _run(case: EvalCase) -> tuple[dict[str, Any], list[str]]:
    result = _SVC.analyze_full(text=case.text)
    evidence_ids = {ev.id for ev in result.evidence}
    entities = set(result.extracted_entities)

    row = {
        "id": case.id,
        "label": case.label,
        "score": result.risk_score,
        "verdict": result.verdict,
        "category": result.message_category,
        "intent": result.message_intent,
        "entities": sorted(entities),
        "evidence_ids": sorted(evidence_ids),
    }

    issues: list[str] = []
    if case.max_verdict and _rank(result.verdict) > _rank(case.max_verdict):
        issues.append(f"VERDICT_ABOVE_MAX({result.verdict}>{case.max_verdict})")
    if case.min_verdict and _rank(result.verdict) < _rank(case.min_verdict):
        issues.append(f"VERDICT_BELOW_MIN({result.verdict}<{case.min_verdict})")
    if case.max_score is not None and result.risk_score > case.max_score:
        issues.append(f"SCORE_ABOVE_MAX({result.risk_score}>{case.max_score})")

    missing_evidence = case.required_evidence - evidence_ids
    if missing_evidence:
        issues.append(f"MISSING_EVIDENCE({sorted(missing_evidence)})")
    forbidden_evidence = case.forbidden_evidence & evidence_ids
    if forbidden_evidence:
        issues.append(f"FORBIDDEN_EVIDENCE({sorted(forbidden_evidence)})")

    missing_entities = case.required_entities - entities
    if missing_entities:
        issues.append(f"MISSING_ENTITIES({sorted(missing_entities)})")
    forbidden_entities = case.forbidden_entities & entities
    if forbidden_entities:
        issues.append(f"FORBIDDEN_ENTITIES({sorted(forbidden_entities)})")

    return row, issues


def main() -> int:
    hdr = (
        f"{'ID':>2} {'LABEL':32} {'SCORE':>5} {'VERDICT':8} "
        f"{'CATEGORY':22} {'INTENT':20} {'RESULT':4}"
    )
    print("=" * len(hdr))
    print("APG Phase 4.1 — Promo / Discount False-Positive Evaluation")
    print(f"Cases: {len(CASES)}")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    passed = failed = 0
    for case in CASES:
        row, issues = _run(case)
        result = "PASS" if not issues else "FAIL"
        print(
            f"{row['id']:>2} {row['label']:32} {row['score']:>5} "
            f"{row['verdict']:8} {row['category'][:22]:22} "
            f"{row['intent'][:20]:20} {result:4}"
        )
        if issues:
            failed += 1
            for issue in issues:
                print(f"    >> {issue}")
            print(f"    entities: {row['entities']}")
            print(f"    evidence: {row['evidence_ids']}")
        else:
            passed += 1

    print("-" * len(hdr))
    print(f"TOTAL: {passed}/{len(CASES)} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
