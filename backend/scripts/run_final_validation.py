"""
APG Final Validation Runner
===========================
Runs all four evaluation packs and prints a structured summary.
Optionally runs the registry expansion audit (informational only).

Usage:
    cd backend
    python scripts/run_final_validation.py

Exit codes:
    0  all packs PASS  (registry audit WARN does not affect exit code)
    1  one or more packs FAIL or errored
       (registry audit FAIL — schema errors — also sets exit code 1)
"""
from __future__ import annotations

import subprocess
import sys
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]

PACKS = [
    {
        "key": "entity_result",
        "label": "Entity Intelligence v2",
        "script": "scripts/evaluate_entity_intelligence_v2.py",
        "pass_pattern": re.compile(r"entity_cases_passed=(\d+)"),
        "fail_pattern": re.compile(r"entity_cases_failed=(\d+)"),
        "phase_marker": re.compile(r"PHASE_5_STATUS:\s*(\w+)"),
        "phase_key": "PHASE_5_STATUS",
    },
    {
        "key": "behavioral_result",
        "label": "Behavioral Intelligence v2",
        "script": "scripts/evaluate_behavioral_v2.py",
        "pass_pattern": re.compile(r"PASS:\s*(\d+)"),
        "fail_pattern": re.compile(r"FAIL:\s*(\d+)"),
        "phase_marker": re.compile(r"PHASE_4_STATUS:\s*(\w+)"),
        "phase_key": "PHASE_4_STATUS",
    },
    {
        "key": "promo_fp_result",
        "label": "Promo False-Positive Pack",
        "script": "scripts/evaluate_behavioral_false_positives.py",
        "pass_pattern": re.compile(r"TOTAL:\s*(\d+)/\d+\s+passed"),
        "fail_pattern": re.compile(r"(\d+)\s+failed"),
        "phase_marker": None,
        "phase_key": None,
    },
    {
        "key": "sandbox_result",
        "label": "Dynamic URL Sandbox",
        "script": "scripts/evaluate_dynamic_url_sandbox.py",
        "pass_pattern": re.compile(r"TOTAL:\s*(\d+)/\d+\s+passed"),
        "fail_pattern": re.compile(r"(\d+)\s+failed"),
        "phase_marker": None,
        "phase_key": None,
    },
]


def _run_pack(pack: dict) -> dict:
    script = BACKEND_DIR / pack["script"]
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(BACKEND_DIR),
            timeout=300,
        )
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return {"passed": 0, "failed": -1, "status": "TIMEOUT", "phase_status": None, "output": ""}
    except Exception as exc:
        return {"passed": 0, "failed": -1, "status": f"ERROR: {exc}", "phase_status": None, "output": ""}

    passed = 0
    failed = 0
    phase_status = None

    m = pack["pass_pattern"].search(output)
    if m:
        passed = int(m.group(1))

    m = pack["fail_pattern"].search(output)
    if m:
        failed = int(m.group(1))

    if pack["phase_marker"]:
        m = pack["phase_marker"].search(output)
        if m:
            phase_status = m.group(1)

    status = "PASS" if failed == 0 and passed > 0 else "FAIL"
    return {"passed": passed, "failed": failed, "status": status, "phase_status": phase_status}


def _run_audit() -> str:
    """Run the registry expansion audit and return PASS/WARN/FAIL/ERROR."""
    audit_script = BACKEND_DIR / "scripts" / "audit_entity_registry_expansion.py"
    if not audit_script.exists():
        return "SKIPPED"
    try:
        proc = subprocess.run(
            [sys.executable, str(audit_script)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(BACKEND_DIR),
            timeout=60,
        )
        output = proc.stdout + proc.stderr
        if "REGISTRY_EXPANSION_AUDIT_STATUS: PASS" in output:
            m = re.search(r"WARN items: (\d+)", output)
            return f"PASS (WARN={m.group(1)})" if m else "PASS"
        if "REGISTRY_EXPANSION_AUDIT_STATUS: FAIL" in output:
            return "FAIL"
        return "UNKNOWN"
    except Exception as exc:
        return f"ERROR: {exc}"


def main() -> int:
    print()
    print("=" * 60)
    print("  APG — Final Validation Runner")
    print("=" * 60)
    print()

    results: dict[str, dict] = {}
    phase_statuses: dict[str, str] = {}

    for pack in PACKS:
        print(f"  Running: {pack['label']} ...", end=" ", flush=True)
        r = _run_pack(pack)
        results[pack["key"]] = r
        if pack["phase_key"] and r["phase_status"]:
            phase_statuses[pack["phase_key"]] = r["phase_status"]
        status_str = f"{r['status']} ({r['passed']} passed, {r['failed']} failed)"
        print(status_str)

    # Registry expansion audit — informational; FAIL blocks, WARN does not.
    print(f"  Running: Registry Expansion Audit ...", end=" ", flush=True)
    audit_status = _run_audit()
    print(audit_status)

    total_passed = sum(r["passed"] for r in results.values())
    total_failed = sum(max(r["failed"], 0) for r in results.values())
    total_cases = total_passed + total_failed
    all_pack_pass = all(r["status"] == "PASS" for r in results.values())
    audit_ok = not audit_status.startswith("FAIL")
    final_status = "PASS" if all_pack_pass and audit_ok else "FAIL"

    print()
    print("-" * 60)
    print(f"  {'entity_result':<28} {results['entity_result']['status']}")
    print(f"  {'behavioral_result':<28} {results['behavioral_result']['status']}")
    print(f"  {'promo_fp_result':<28} {results['promo_fp_result']['status']}")
    print(f"  {'sandbox_result':<28} {results['sandbox_result']['status']}")
    print(f"  {'registry_expansion_audit':<28} {audit_status}  [informational]")
    print("-" * 60)
    print(f"  {'total_cases_across_packs':<28} {total_cases}")
    print(f"  {'total_passed':<28} {total_passed}")
    print(f"  {'total_failed':<28} {total_failed}")
    print()
    for pk, pv in phase_statuses.items():
        print(f"  {pk:<28} {pv}")
    print()
    print(f"  FINAL_VALIDATION_STATUS:     {final_status}")
    print("=" * 60)
    print()

    return 0 if all_pack_pass and audit_ok else 1


if __name__ == "__main__":
    sys.exit(main())
