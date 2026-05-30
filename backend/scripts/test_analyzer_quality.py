"""
APG Risk Intelligence Engine — Quality Test Script
===================================================
Loads a JSON fixture (default: tests/fixtures/risk_engine_cases.json) and runs
every case through the active engine, reporting per-category and aggregate metrics.

Exit codes
----------
0  All hard-fail conditions passed
1  One or more hard-fail conditions triggered (printed to stderr)

Usage
-----
  cd backend
  python scripts/test_analyzer_quality.py [--engine risk_engine_v1|v5] [-v] [--category NAME]
  python scripts/test_analyzer_quality.py --fixture tests/fixtures/official_safe_messages.json

URL reputation calls are disabled automatically via URL_REPUTATION_ENABLED=false.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1256 UnicodeEncodeError for box chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

FIXTURES_PATH = BACKEND_DIR / "tests" / "fixtures" / "risk_engine_cases.json"

# ── CLI args ───────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="APG quality test suite")
parser.add_argument("--engine", choices=["risk_engine_v1", "v5"], default=None)
parser.add_argument("--verbose", "-v", action="store_true")
parser.add_argument("--fail-fast", action="store_true")
parser.add_argument("--category", default=None)
parser.add_argument(
    "--fixture",
    default=str(FIXTURES_PATH),
    help="Fixture JSON path, relative to backend/ or absolute. Defaults to risk_engine_cases.json.",
)
args = parser.parse_args()

if args.engine:
    os.environ["APG_ANALYZER_ENGINE"] = args.engine
os.environ["URL_REPUTATION_ENABLED"] = "false"

fixture_path = Path(args.fixture)
if not fixture_path.is_absolute():
    fixture_path = BACKEND_DIR / fixture_path

# ── Load fixtures ──────────────────────────────────────────────────────────────
if not fixture_path.exists():
    print(f"ERROR: fixtures not found at {fixture_path}", file=sys.stderr)
    sys.exit(1)

with open(fixture_path, encoding="utf-8") as f:
    all_cases: list[dict] = json.load(f)

if args.category:
    all_cases = [c for c in all_cases if c.get("category") == args.category]
    if not all_cases:
        print(f"ERROR: No cases in category '{args.category}'", file=sys.stderr)
        sys.exit(1)

# ── Engine init ────────────────────────────────────────────────────────────────
print("Initialising engine...", flush=True)
t0 = time.perf_counter()
try:
    from app.services.hybrid_analyzer import get_hybrid_analyzer
    analyzer = get_hybrid_analyzer()
except Exception as exc:
    print(f"ERROR: Could not initialise engine: {exc}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)
print(f"Engine ready in {(time.perf_counter() - t0)*1000:.0f} ms\n")

# ── Verdict normalisation ──────────────────────────────────────────────────────
_VERDICT_MAP = {"allow": "safe", "caution": "suspicious", "warn": "suspicious", "block": "dangerous"}


def _norm(cls: str) -> str:
    return _VERDICT_MAP.get((cls or "").lower(), (cls or "").lower())


# ── Run one case ───────────────────────────────────────────────────────────────

def _run_case(case: dict) -> dict:
    try:
        result = analyzer.analyze(
            case.get("text", ""),
            source=case.get("source", "sms"),
            sender=case.get("sender"),
            sender_name=case.get("sender_name"),
            is_known_contact=case.get("is_known_contact", False),
            sender_trust=case.get("sender_trust", "unknown"),
            mock_url_reputation=case.get("mock_url_reputation"),
        )
    except TypeError:
        # Older engine signature without all kwargs
        try:
            result = analyzer.analyze(
                case.get("text", ""),
                source=case.get("source", "sms"),
                sender=case.get("sender"),
                sender_name=case.get("sender_name"),
                is_known_contact=case.get("is_known_contact", False),
            )
        except Exception as exc:
            return {"_error": str(exc), "classification": "error", "risk_score": -1}
    except Exception as exc:
        return {"_error": str(exc), "classification": "error", "risk_score": -1}

    if hasattr(result, "__dict__"):
        return vars(result)
    if isinstance(result, dict):
        return result
    return {"classification": str(result), "risk_score": 0}


def _extract_block_reason(policy_trace) -> str | None:
    """Return a block reason string from policy_trace regardless of whether it
    is a dict, a list of dicts/strings, or None."""
    if not policy_trace:
        return None
    _KEYS = ("block_reason", "block_rule", "reason", "rule")
    if isinstance(policy_trace, dict):
        for k in _KEYS:
            v = policy_trace.get(k)
            if v:
                return str(v)
        return None
    if isinstance(policy_trace, list):
        for item in policy_trace:
            if isinstance(item, dict):
                for k in _KEYS:
                    v = item.get(k)
                    if v:
                        return str(v)
            elif isinstance(item, str) and "block" in item.lower():
                return item
    return None


def _pass(case: dict, r: dict) -> tuple[bool, str]:
    exp = case.get("expected", {})
    if isinstance(exp, str):
        exp = {"classification": exp}

    got_cls = _norm(r.get("classification") or r.get("verdict") or "error")
    exp_cls = _norm(exp.get("classification", ""))
    score = int(r.get("risk_score") or 0)

    if r.get("_error"):
        return False, f"engine error: {r['_error']}"
    if exp_cls and got_cls != exp_cls:
        return False, f"classification: expected={exp_cls!r} got={got_cls!r} score={score}"
    min_s = exp.get("min_risk_score")
    if min_s is not None and score < int(min_s):
        return False, f"score {score} < min {min_s}"
    max_s = exp.get("max_risk_score")
    if max_s is not None and score > int(max_s):
        return False, f"score {score} > max {max_s}"
    exp_mcat = exp.get("message_category")
    got_mcat = r.get("message_category")
    if exp_mcat and got_mcat and exp_mcat != got_mcat:
        return False, f"message_category: expected={exp_mcat!r} got={got_mcat!r}"
    return True, ""


# ── Run all cases ──────────────────────────────────────────────────────────────

print(f"Running {len(all_cases)} test cases...")
print("-" * 80)

t_start = time.perf_counter()
failures: list[tuple[dict, dict, str]] = []

# Accumulators
total = passed_n = failed_n = error_n = 0
true_safe = fp = true_dangerous = fn = susp_correct = susp_total = 0
conf_sum = conf_n = 0.0
category_pass: dict[str, int] = {}
category_total: dict[str, int] = {}

# Hard-fail lists
dangerous_as_safe: list[str] = []
safe_cat_as_dangerous: list[str] = []

_SAFE_CATS = {
    "safe_awareness", "awareness_with_phishing_examples",
    "safe_otp_delivery", "safe_bank_transaction",
    "safe_app_verification", "safe_casual", "safe_institutional",
    "safe_government_service", "safe_ecommerce",
    "safe_promotional", "safe_service_notification",
    "safe_subscription_notice", "safe_survey",
    "safe_government_notice", "safe_payment_receipt",
}

for case in all_cases:
    r = _run_case(case)
    ok, reason = _pass(case, r)
    total += 1
    cat = case.get("category", "unknown")
    category_total[cat] = category_total.get(cat, 0) + 1

    exp = case.get("expected", {})
    if isinstance(exp, str):
        exp = {"classification": exp}
    exp_cls = _norm(exp.get("classification", ""))
    got_cls = _norm(r.get("classification") or r.get("verdict") or "error")
    score = int(r.get("risk_score") or 0)
    conf = float(r.get("confidence") or 0)

    if r.get("_error"):
        error_n += 1
    elif ok:
        passed_n += 1
        category_pass[cat] = category_pass.get(cat, 0) + 1
    else:
        failed_n += 1

    if conf > 0:
        conf_sum += conf
        conf_n += 1

    # Metric counting
    if exp_cls == "safe":
        if got_cls == "safe":
            true_safe += 1
        elif got_cls == "dangerous":
            fp += 1
    if exp_cls == "dangerous":
        if got_cls == "dangerous":
            true_dangerous += 1
        elif got_cls == "safe":
            fn += 1
            dangerous_as_safe.append(
                f"  [{case['id']}] score={score} got={got_cls!r}  — {case.get('description','')}"
            )
    if exp_cls == "suspicious":
        susp_total += 1
        if got_cls == "suspicious":
            susp_correct += 1

    # Safe category classified as dangerous (hard fail only if no block reason)
    if cat in _SAFE_CATS and got_cls == "dangerous":
        debug = r.get("debug") or {}
        policy_trace = r.get("policy_trace") or debug.get("policy_trace") or {}
        block_reason = _extract_block_reason(policy_trace)
        if not block_reason:
            safe_cat_as_dangerous.append(
                f"  [{case['id']}] cat={cat} score={score}  — {case.get('description','')}"
            )

    if args.verbose or not ok:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {str(case['id']):<42} {reason}")
        if not ok and args.verbose:
            print(f"         text  : {case['text'][:80]}")
            print(f"         expect: {json.dumps(exp, ensure_ascii=False)}")
            summary = {k: r.get(k) for k in
                       ("classification", "risk_score", "verdict", "message_category", "confidence")
                       if r.get(k) is not None}
            print(f"         got   : {json.dumps(summary, ensure_ascii=False)}")

    if not ok:
        failures.append((case, r, reason))
        if args.fail_fast:
            print("[--fail-fast] Stopping after first failure.")
            break

elapsed_ms = (time.perf_counter() - t_start) * 1000

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 72)
print("QUALITY REPORT")
print("=" * 72)

accuracy = passed_n / total * 100 if total else 0
safe_total_n = true_safe + fp
safe_precision = true_safe / safe_total_n * 100 if safe_total_n else 100.0
safe_fpr = fp / safe_total_n * 100 if safe_total_n else 0.0
dangerous_total_n = true_dangerous + fn
dangerous_recall = true_dangerous / dangerous_total_n * 100 if dangerous_total_n else 100.0
fn_rate = fn / dangerous_total_n * 100 if dangerous_total_n else 0.0
susp_acc = susp_correct / susp_total * 100 if susp_total else 100.0
avg_conf = conf_sum / conf_n if conf_n else 0.0

print(f"  Total cases          : {total}")
print(f"  Passed               : {passed_n}  ({accuracy:.1f}%)")
print(f"  Failed               : {failed_n}")
print(f"  Errors               : {error_n}")
print(f"  Accuracy             : {accuracy:.1f}%")
print(f"")
print(f"  Safe precision       : {safe_precision:.1f}%  ({true_safe}/{safe_total_n})")
print(f"  Safe FPR             : {safe_fpr:.1f}%")
print(f"  Dangerous recall     : {dangerous_recall:.1f}%  ({true_dangerous}/{dangerous_total_n})")
print(f"  False negative rate  : {fn_rate:.1f}%")
print(f"  Suspicious accuracy  : {susp_acc:.1f}%  ({susp_correct}/{susp_total})")
print(f"  Avg confidence       : {avg_conf:.1f}")
print(f"  Runtime              : {elapsed_ms:.0f} ms  /  {elapsed_ms/total:.1f} ms per case")

print("\n-- Per-category -----------------------------------------------------------")
for cat in sorted(category_total):
    tot_c = category_total[cat]
    pass_c = category_pass.get(cat, 0)
    pct = pass_c / tot_c * 100
    bar = "#" * pass_c + "." * (tot_c - pass_c)
    print(f"  {cat:<48} {pass_c:>3}/{tot_c:<3} {pct:>5.1f}%  [{bar}]")

# ── Hard-fail checks ───────────────────────────────────────────────────────────
print("\n-- Hard-fail checks -------------------------------------------------------")
hard_fails: list[str] = []

if dangerous_as_safe:
    hard_fails.append(
        f"HARD FAIL: {len(dangerous_as_safe)} dangerous case(s) classified as SAFE:\n"
        + "\n".join(dangerous_as_safe)
    )

if safe_cat_as_dangerous:
    hard_fails.append(
        f"HARD FAIL: {len(safe_cat_as_dangerous)} awareness/OTP/bank case(s) classified "
        f"DANGEROUS without block evidence:\n" + "\n".join(safe_cat_as_dangerous)
    )

if dangerous_recall < 95.0:
    hard_fails.append(
        f"HARD FAIL: dangerous recall {dangerous_recall:.1f}% < 95.0% threshold"
    )

if safe_fpr > 5.0:
    hard_fails.append(
        f"HARD FAIL: safe false-positive rate {safe_fpr:.1f}% > 5.0% threshold"
    )

if accuracy < 92.0:
    hard_fails.append(
        f"HARD FAIL: overall accuracy {accuracy:.1f}% < 92.0% threshold"
    )

if hard_fails:
    print()
    for hf in hard_fails:
        print(hf)
        print(hf, file=sys.stderr)
    print(f"\n{len(hard_fails)} hard-fail condition(s) triggered.")
    sys.exit(1)

print("  All hard-fail conditions passed.")
print("\nQUALITY TEST PASSED")
sys.exit(0)
