"""
APG Entity Registry Expansion Audit
====================================
Reads jo_entities.json and prints a structured quality report covering
schema completeness, data hygiene, coverage gaps, and expansion readiness.

Exit codes
----------
  0  REGISTRY_EXPANSION_AUDIT_STATUS: PASS  (no blocking errors)
  1  REGISTRY_EXPANSION_AUDIT_STATUS: FAIL  (JSON invalid or required fields missing)

WARN items are printed but do not affect the exit code.

Usage
-----
  cd backend
  python scripts/audit_entity_registry_expansion.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
REGISTRY_PATH = BACKEND_DIR / "app" / "data" / "entities" / "jo_entities.json"

# ── Required fields ────────────────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "id",
    "name",
    "primary_arabic_name",
    "aliases",
    "entity_type",
    "country",
    "official_domains",
    "official_sender_names",
    "allowed_message_types",
    "forbidden_requests",
    "risk_notes",
]

# ── Future expansion targets (entity_type → min count) ────────────────────────
COVERAGE_TARGETS: dict[str, int] = {
    "bank": 15,
    "government": 25,
    "telecom": 5,
    "e_wallet": 8,
    "payment_gateway": 10,
    "payment_network": 5,
    "delivery_logistics": 12,
    "ecommerce": 15,
    "healthcare": 15,
    "education_university": 20,
    "utilities": 10,
    "ride_hailing": 5,
    "social_platform": 10,
    "streaming_subscription": 8,
}

# ── Common-word alias risks ────────────────────────────────────────────────────
# Arabic and short English tokens that collide with common vocabulary.
_COMMON_WORD_RISKS = {
    "زين", "نور", "سند", "بنك", "دفع", "امن", "امان", "حكومه", "حكومة",
    "طيران", "بريد", "ماء", "كهرباء", "كهربا", "مدفوعات", "رسائل",
    "pay", "bank", "go", "id", "my", "net", "now", "info",
}

# ── Canonical forbidden-request values ────────────────────────────────────────
# Keep in sync with entity_policy.py.
CANONICAL_FORBIDDEN = {
    "account_pin", "bank_otp_code", "bank_password", "card_number", "card_pin",
    "cvv", "online_banking_password", "otp_code", "password", "recovery_code",
    "sanad_password", "secure_key", "two_factor_backup_code", "wallet_password",
    "wallet_pin", "sim_swap_code",
}

_SEP = "-" * 70


def _normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[ـً-ٰٟ]", "", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", text).strip()


def _strip_url(domain: str) -> str:
    domain = re.sub(r"(?i)^https?://", "", domain.strip())
    domain = re.sub(r"(?i)^www\.", "", domain)
    domain = domain.split("/")[0].split("?")[0].split("#")[0].split(":")[0]
    return domain.lower().strip()


def _is_arabic(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text))


def main() -> int:
    print()
    print("=" * 70)
    print("  APG Entity Registry Expansion Audit")
    print("=" * 70)

    # ── Load JSON ──────────────────────────────────────────────────────────────
    if not REGISTRY_PATH.exists():
        print(f"\n  ERROR: registry not found at {REGISTRY_PATH}")
        print(f"\n  REGISTRY_EXPANSION_AUDIT_STATUS: FAIL")
        return 1

    try:
        with REGISTRY_PATH.open(encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"\n  ERROR: JSON parse failed: {exc}")
        print(f"\n  REGISTRY_EXPANSION_AUDIT_STATUS: FAIL")
        return 1

    # Root may be a dict with an "entities" key, or a bare array.
    if isinstance(raw, dict):
        entities: list[dict] = raw.get("entities", [])
    elif isinstance(raw, list):
        entities = raw
    else:
        print("\n  ERROR: registry root must be a JSON object or array")
        print(f"\n  REGISTRY_EXPANSION_AUDIT_STATUS: FAIL")
        return 1

    if not isinstance(entities, list):
        print("\n  ERROR: 'entities' value must be a JSON array")
        print(f"\n  REGISTRY_EXPANSION_AUDIT_STATUS: FAIL")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    # ── Basic counts ───────────────────────────────────────────────────────────
    total = len(entities)
    count_by_type: dict[str, int] = defaultdict(int)
    count_by_country: dict[str, int] = defaultdict(int)
    total_aliases = 0
    total_domains = 0
    total_senders = 0
    total_forbidden = 0
    total_allowed_mt = 0

    # ── Index structures for duplicate detection ───────────────────────────────
    ids_seen: dict[str, list[str]] = defaultdict(list)
    alias_norm_seen: dict[str, list[str]] = defaultdict(list)
    domain_seen: dict[str, list[str]] = defaultdict(list)
    sender_norm_seen: dict[str, list[str]] = defaultdict(list)

    # ── Per-entity findings ────────────────────────────────────────────────────
    missing_required: list[str] = []
    empty_domains: list[str] = []
    empty_senders: list[str] = []
    empty_aliases: list[str] = []
    domain_with_protocol: list[str] = []
    domain_with_path: list[str] = []
    domain_with_uppercase: list[str] = []
    www_duplicates: list[str] = []
    short_alias_risks: list[tuple[str, str]] = []
    common_word_risks: list[tuple[str, str]] = []
    unmapped_forbidden: list[tuple[str, str]] = []

    for ent in entities:
        eid = ent.get("id", "<no-id>")

        # Required fields
        missing = [f for f in REQUIRED_FIELDS if f not in ent]
        if missing:
            missing_required.append(f"{eid}: missing {missing}")
            errors.append(f"MISSING FIELDS [{eid}]: {missing}")

        ids_seen[eid].append(eid)
        etype = ent.get("entity_type", "")
        country = ent.get("country", "")
        count_by_type[etype] += 1
        count_by_country[country] += 1

        # Aliases
        aliases = ent.get("aliases", [])
        if not aliases:
            empty_aliases.append(eid)
        for alias in aliases:
            total_aliases += 1
            norm = _normalize(alias)
            alias_norm_seen[norm].append(eid)
            # Short alias risk
            stripped = re.sub(r"[^a-z0-9؀-ۿ]", "", norm)
            if 0 < len(stripped) < 4:
                short_alias_risks.append((eid, alias))
            # Common word risk
            if norm in _COMMON_WORD_RISKS:
                common_word_risks.append((eid, alias))

        # Official domains
        domains = ent.get("official_domains", [])
        if not domains:
            empty_domains.append(eid)
        for domain in domains:
            total_domains += 1
            cleaned = _strip_url(domain)
            domain_seen[cleaned].append(eid)
            if re.search(r"(?i)^https?://", domain):
                domain_with_protocol.append(f"{eid}: {domain}")
            if "/" in domain or "?" in domain:
                domain_with_path.append(f"{eid}: {domain}")
            if domain != domain.lower():
                domain_with_uppercase.append(f"{eid}: {domain}")
            if domain.lower().startswith("www."):
                www_duplicates.append(f"{eid}: {domain}")

        # Official sender names
        senders = ent.get("official_sender_names", [])
        if not senders:
            empty_senders.append(eid)
        for s in senders:
            total_senders += 1
            sender_norm_seen[_normalize(s)].append(eid)

        # Forbidden requests
        frs = ent.get("forbidden_requests", [])
        total_forbidden += len(frs)
        for fr in frs:
            if fr not in CANONICAL_FORBIDDEN:
                unmapped_forbidden.append((eid, fr))

        # Allowed message types
        total_allowed_mt += len(ent.get("allowed_message_types", []))

    # ── Duplicate detection ────────────────────────────────────────────────────
    duplicate_ids = {k: v for k, v in ids_seen.items() if len(v) > 1}
    duplicate_aliases = {
        k: v for k, v in alias_norm_seen.items() if len(v) > 1
    }
    shared_domains = {
        k: v for k, v in domain_seen.items() if len(v) > 1
    }
    duplicate_domains = shared_domains  # shared but expected per policy
    duplicate_senders = {
        k: v for k, v in sender_norm_seen.items() if len(v) > 1
    }

    # ── Coverage gaps ──────────────────────────────────────────────────────────
    under_target: list[tuple[str, int, int]] = []
    for etype, target in COVERAGE_TARGETS.items():
        actual = count_by_type.get(etype, 0)
        if actual < target:
            under_target.append((etype, actual, target))

    # ── Print report ───────────────────────────────────────────────────────────
    print()
    print("  Registry Summary")
    print(_SEP)
    print(f"  total_entities             {total}")
    for c in sorted(count_by_country):
        print(f"    country={c:<10}          {count_by_country[c]}")
    print()
    for t in sorted(count_by_type):
        print(f"    type={t:<28} {count_by_type[t]}")
    print()
    print(f"  total_aliases              {total_aliases}")
    print(f"  total_official_domains     {total_domains}")
    print(f"  total_official_senders     {total_senders}")
    print(f"  total_forbidden_requests   {total_forbidden}")
    print(f"  total_allowed_msg_types    {total_allowed_mt}")

    print()
    print("  Schema Integrity")
    print(_SEP)
    _pr_list("MISSING required fields", missing_required, errors)
    _pr_list("Duplicate entity IDs", [f"{k}: {v}" for k, v in duplicate_ids.items()], errors)

    print()
    print("  Completeness Checks")
    print(_SEP)
    _pr_list("Entities with no official domains", empty_domains, warnings)
    _pr_list("Entities with no official sender names", empty_senders, warnings)
    _pr_list("Entities with no aliases", empty_aliases, warnings)

    print()
    print("  Domain Hygiene")
    print(_SEP)
    _pr_list("Domains with protocol prefix", domain_with_protocol, errors)
    _pr_list("Domains with path/query", domain_with_path, errors)
    _pr_list("Domains with uppercase", domain_with_uppercase, warnings)
    _pr_list("Domains starting with www.", www_duplicates, warnings)
    print(f"  Shared (duplicate) domains:    {len(shared_domains)}")
    for dom, owners in sorted(shared_domains.items()):
        print(f"    {dom} => {', '.join(owners)}")

    print()
    print("  Alias Hygiene")
    print(_SEP)
    dup_alias_cross = {
        k: list(set(v)) for k, v in duplicate_aliases.items()
        if len(set(v)) > 1
    }
    dup_alias_self = {
        k: v for k, v in duplicate_aliases.items()
        if len(set(v)) == 1
    }
    print(f"  Cross-entity duplicate aliases:  {len(dup_alias_cross)}")
    for k, v in list(dup_alias_cross.items())[:10]:
        print(f"    '{k}' used by: {v}")
    print(f"  Same-entity duplicate aliases:   {len(dup_alias_self)}")
    print(f"  Short alias risks (< 4 chars):   {len(short_alias_risks)}")
    for eid, alias in short_alias_risks[:10]:
        print(f"    [{eid}] '{alias}'")
    print(f"  Common-word alias risks:         {len(common_word_risks)}")
    for eid, alias in common_word_risks[:10]:
        print(f"    [{eid}] '{alias}'")

    print()
    print("  Sender Hygiene")
    print(_SEP)
    dup_senders_cross = {
        k: list(set(v)) for k, v in duplicate_senders.items()
        if len(set(v)) > 1
    }
    print(f"  Cross-entity duplicate senders:  {len(dup_senders_cross)}")
    for k, v in list(dup_senders_cross.items())[:10]:
        print(f"    '{k}' used by: {v}")

    print()
    print("  Forbidden Request Hygiene")
    print(_SEP)
    print(f"  Unmapped forbidden request values: {len(unmapped_forbidden)}")
    for eid, fr in unmapped_forbidden[:10]:
        print(f"    [{eid}] '{fr}'")
    if unmapped_forbidden:
        warnings.append(
            f"{len(unmapped_forbidden)} unmapped forbidden request value(s) — add to CANONICAL_FORBIDDEN or entity_policy.py"
        )

    print()
    print("  Coverage vs. Expansion Targets")
    print(_SEP)
    if under_target:
        for etype, actual, target in under_target:
            gap = target - actual
            marker = "WARN" if actual > 0 else "GAP"
            print(f"  {marker}  {etype:<30} current={actual:<4} target={target}  gap={gap}")
            warnings.append(f"Under target: {etype} ({actual}/{target})")
    else:
        print("  All entity types at or above target.")

    # ── Final status ───────────────────────────────────────────────────────────
    print()
    print(_SEP)
    if warnings:
        print(f"  WARN items: {len(warnings)}")
        for w in warnings:
            print(f"    - {w}")
    print()

    if errors:
        print(f"  ERRORS: {len(errors)}")
        for e in errors:
            print(f"    ! {e}")
        print()
        print("  REGISTRY_EXPANSION_AUDIT_STATUS: FAIL")
        print()
        return 1

    print("  REGISTRY_EXPANSION_AUDIT_STATUS: PASS")
    if warnings:
        print("  (WARN items above are informational — review before next batch)")
    print()
    return 0


def _pr_list(label: str, items: list, bucket: list) -> None:
    print(f"  {label}: {len(items)}")
    for item in items[:5]:
        print(f"    {item}")
    if items:
        if bucket is not None:
            bucket.extend(items)


if __name__ == "__main__":
    sys.exit(main())
