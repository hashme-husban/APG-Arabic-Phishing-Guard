"""
APG Risk Intelligence Engine — Evaluation Dataset Runner
=========================================================
Runs the active risk engine against a labeled evaluation dataset and reports
classification accuracy, intent accuracy, and entity accuracy.

Usage
-----
  cd backend
  python scripts/evaluate_dataset.py
  python scripts/evaluate_dataset.py --dataset dataset/eval_messages_jo.json
  python scripts/evaluate_dataset.py --limit 50 --failures-only
  python scripts/evaluate_dataset.py --enable-vt

Output
------
  • Live progress to stdout
  • Summary metrics table
  • Compact failure table (id | exp_cls | got_cls | exp_intent | got_intent | score | text)
  • JSON export → reports/eval_results_jo.json

Exit codes
----------
  0  Evaluation completed (pass or fail — just reporting)
  1  Fatal error (engine failed to load, dataset not found)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_DATASET = BACKEND_DIR / "dataset" / "eval_messages_jo.json"
DEFAULT_REPORT  = BACKEND_DIR / "reports" / "eval_results_jo.json"

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="APG evaluation dataset runner")
parser.add_argument(
    "--dataset",
    default=str(DEFAULT_DATASET),
    help="Path to the labeled dataset JSON (default: dataset/eval_messages_jo.json)",
)
parser.add_argument(
    "--report",
    default=str(DEFAULT_REPORT),
    help="Output path for JSON results (default: reports/eval_results_jo.json)",
)
parser.add_argument(
    "--limit",
    type=int,
    default=None,
    metavar="N",
    help="Evaluate only the first N items",
)
parser.add_argument(
    "--failures-only",
    action="store_true",
    help="Print detailed output only for failed cases",
)
parser.add_argument(
    "--enable-vt",
    action="store_true",
    help="Enable VirusTotal URL reputation checks (disabled by default)",
)
args = parser.parse_args()

# ── Environment flags ─────────────────────────────────────────────────────────
if not args.enable_vt:
    os.environ.setdefault("VIRUSTOTAL_ENABLED", "false")

# ── Load dataset ──────────────────────────────────────────────────────────────
dataset_path = Path(args.dataset)
if not dataset_path.is_absolute():
    dataset_path = BACKEND_DIR / dataset_path

if not dataset_path.exists():
    print(f"ERROR: dataset not found at {dataset_path}", file=sys.stderr)
    sys.exit(1)

with open(dataset_path, encoding="utf-8") as f:
    all_items: list[dict] = json.load(f)

if args.limit:
    all_items = all_items[: args.limit]

print(f"Dataset : {dataset_path}")
print(f"Items   : {len(all_items)}")
print(f"VT      : {'enabled' if args.enable_vt else 'disabled'}")
print()

# ── Engine init ───────────────────────────────────────────────────────────────
print("Initialising engine...", flush=True)
t0 = time.perf_counter()
try:
    from app.services.hybrid_analyzer import get_hybrid_analyzer
    analyzer = get_hybrid_analyzer()
except Exception as exc:
    print(f"ERROR: Could not initialise engine: {exc}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)
print(f"Engine ready in {(time.perf_counter() - t0) * 1000:.0f} ms\n")

# ── Helpers ───────────────────────────────────────────────────────────────────
_VERDICT_MAP = {
    "allow": "safe",
    "caution": "suspicious",
    "warn": "suspicious",
    "block": "dangerous",
}


def _norm_cls(v: str | None) -> str:
    v = (v or "").lower().strip()
    return _VERDICT_MAP.get(v, v)


def _run(item: dict) -> dict:
    """Run one dataset item through the analyzer. Returns result dict."""
    try:
        result = analyzer.analyze(
            item.get("text", ""),
            source=item.get("source", "sms"),
            sender=item.get("sender", ""),
            sender_name=item.get("sender_name", item.get("sender", "")),
            is_known_contact=item.get("is_known_contact"),
            sender_trust=item.get("sender_trust", "unknown"),
        )
    except Exception as exc:
        return {"_error": str(exc), "classification": "error", "risk_score": -1}

    if hasattr(result, "__dict__"):
        d = vars(result)
    elif isinstance(result, dict):
        d = result
    else:
        d = {"classification": str(result), "risk_score": 0}
    return d


def _extract_intent(result: dict) -> str:
    """Pull message_intent from either result fields or nested debug dict."""
    intent = result.get("message_intent")
    if intent and intent != "unknown":
        return intent
    debug = result.get("debug") or {}
    return debug.get("message_intent") or "unknown"


def _extract_entity_id(result: dict) -> str | None:
    """Pull claimed_entity.entity_id from debug dict."""
    debug = result.get("debug") or {}
    claimed = debug.get("claimed_entity")
    if isinstance(claimed, dict):
        return claimed.get("entity_id")
    return None


def _short(text: str, n: int = 55) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text[:n] + "…" if len(text) > n else text


# ── Evaluation loop ───────────────────────────────────────────────────────────
print(f"Running {len(all_items)} item(s)...")
print("-" * 90)

t_start = time.perf_counter()

# Counters
total = 0
cls_correct = cls_wrong = cls_errors = 0
intent_correct = intent_wrong = intent_total = 0
entity_correct = entity_wrong = entity_total = 0

# Safety-critical counters
dangerous_missed = 0   # expected dangerous → got safe or suspicious
safe_flagged = 0       # expected safe → got suspicious or dangerous

# Full records for JSON export
records: list[dict] = []
failures: list[dict] = []

for item in all_items:
    total += 1
    item_id = item.get("id", f"item_{total}")
    text = item.get("text", "")

    exp_cls    = _norm_cls(item.get("expected_classification"))
    exp_intent = (item.get("expected_intent") or "").strip()
    exp_entity = (item.get("expected_claimed_entity") or "").strip() or None

    t_item = time.perf_counter()
    result = _run(item)
    elapsed_ms = (time.perf_counter() - t_item) * 1000

    got_cls    = _norm_cls(result.get("classification"))
    got_intent = _extract_intent(result)
    got_entity = _extract_entity_id(result)
    risk_score = int(result.get("risk_score") or 0)

    has_error = bool(result.get("_error"))

    # Classification
    if has_error:
        cls_errors += 1
        cls_match = False
    elif exp_cls and got_cls == exp_cls:
        cls_correct += 1
        cls_match = True
    elif exp_cls:
        cls_wrong += 1
        cls_match = False
    else:
        cls_match = True  # no expectation → not scored

    # Intent (only when expected_intent is set)
    intent_match = None
    if exp_intent:
        intent_total += 1
        if got_intent == exp_intent:
            intent_correct += 1
            intent_match = True
        else:
            intent_wrong += 1
            intent_match = False

    # Entity (only when expected_claimed_entity is set)
    entity_match = None
    if exp_entity is not None:
        entity_total += 1
        if got_entity == exp_entity:
            entity_correct += 1
            entity_match = True
        else:
            entity_wrong += 1
            entity_match = False

    # Safety-critical tracking
    if exp_cls == "dangerous" and got_cls in ("safe", "suspicious"):
        dangerous_missed += 1
    if exp_cls == "safe" and got_cls in ("suspicious", "dangerous"):
        safe_flagged += 1

    passed = cls_match and (intent_match is not False) and (entity_match is not False)

    record = {
        "id": item_id,
        "text": text,
        "source": item.get("source", "sms"),
        "expected_classification": exp_cls,
        "actual_classification": got_cls,
        "classification_match": cls_match,
        "expected_intent": exp_intent or None,
        "actual_intent": got_intent,
        "intent_match": intent_match,
        "expected_entity": exp_entity,
        "actual_entity": got_entity,
        "entity_match": entity_match,
        "risk_score": risk_score,
        "elapsed_ms": round(elapsed_ms, 1),
        "passed": passed,
        "error": result.get("_error"),
    }
    records.append(record)
    if not passed:
        failures.append(record)

    if not args.failures_only or not passed:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {item_id:<30} cls={got_cls:<12} intent={got_intent:<22} score={risk_score:>3}")

elapsed_total = (time.perf_counter() - t_start) * 1000

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 90)
print("EVALUATION SUMMARY")
print("=" * 90)

cls_acc    = cls_correct / (cls_correct + cls_wrong) * 100 if (cls_correct + cls_wrong) else 0.0
intent_acc = intent_correct / intent_total * 100 if intent_total else 0.0
entity_acc = entity_correct / entity_total * 100 if entity_total else 0.0
overall_pass = sum(1 for r in records if r["passed"])
overall_pct  = overall_pass / total * 100 if total else 0.0

print(f"  Total items              : {total}")
print(f"  Overall pass             : {overall_pass}  ({overall_pct:.1f}%)")
print()
print(f"  Classification accuracy  : {cls_acc:.1f}%  ({cls_correct}/{cls_correct + cls_wrong} evaluated)")
print(f"    Errors (engine crash)  : {cls_errors}")
print()
print(f"  Intent accuracy          : {intent_acc:.1f}%  ({intent_correct}/{intent_total} with expectation)")
print()
print(f"  Entity accuracy          : {entity_acc:.1f}%  ({entity_correct}/{entity_total} with expectation)")
print()
print(f"  Dangerous missed         : {dangerous_missed}  (expected dangerous → got safe/suspicious)")
print(f"  Safe flagged             : {safe_flagged}   (expected safe → got suspicious/dangerous)")
print()
print(f"  Runtime                  : {elapsed_total:.0f} ms  /  {elapsed_total / total:.1f} ms per item")

# ── Failure table ─────────────────────────────────────────────────────────────
if failures:
    print(f"\n-- Failures ({len(failures)}) " + "-" * 65)
    hdr = f"  {'ID':<28}  {'EXP_CLS':<12}  {'GOT_CLS':<12}  {'EXP_INTENT':<22}  {'GOT_INTENT':<22}  {'SCR':>3}  TEXT"
    print(hdr)
    print("  " + "-" * 130)
    for r in failures:
        exp_cls_s  = (r["expected_classification"] or "-")[:12]
        got_cls_s  = (r["actual_classification"]   or "-")[:12]
        exp_int_s  = (r["expected_intent"]          or "-")[:22]
        got_int_s  = (r["actual_intent"]            or "-")[:22]
        score_s    = str(r["risk_score"])
        row = (
            f"  {r['id']:<28}  {exp_cls_s:<12}  {got_cls_s:<12}  "
            f"{exp_int_s:<22}  {got_int_s:<22}  {score_s:>3}  {_short(r['text'])}"
        )
        print(row)
else:
    print("\n  No failures.")

# ── JSON export ───────────────────────────────────────────────────────────────
report_path = Path(args.report)
if not report_path.is_absolute():
    report_path = BACKEND_DIR / report_path

report_path.parent.mkdir(parents=True, exist_ok=True)

report = {
    "dataset": str(dataset_path),
    "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "total": total,
    "overall_pass": overall_pass,
    "overall_pct": round(overall_pct, 2),
    "classification_accuracy": round(cls_acc, 2),
    "intent_accuracy": round(intent_acc, 2),
    "entity_accuracy": round(entity_acc, 2),
    "dangerous_missed": dangerous_missed,
    "safe_flagged": safe_flagged,
    "runtime_ms": round(elapsed_total, 1),
    "results": records,
}

with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\nReport saved to: {report_path}")
sys.exit(0)
