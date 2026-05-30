"""
APG Production Packaging Script

Creates a clean deployment ZIP for Ubuntu/VPS.

Usage:
    python scripts/package_for_vps.py                   # standard package
    python scripts/package_for_vps.py --dry-run         # list files, no output
    python scripts/package_for_vps.py --include-tests   # include backend/tests/
    python scripts/package_for_vps.py --include-inference-models

Security guarantees:
  - .env files are NEVER included (exact name + pattern exclusion).
  - .env.example IS included (explicit allowlist).
  - *.db / *.sqlite files are NEVER included.
  - __pycache__ / *.pyc are excluded.
  - A post-staging safety check fails the build if any forbidden file slips through.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
STAGE_DIR = DIST_DIR / "APG_Project"
ZIP_PATH = DIST_DIR / "APG_Project_production_vps.zip"
UPLOAD_INSTRUCTIONS_PATH = DIST_DIR / "UPLOAD_INSTRUCTIONS.txt"

LARGE_REPORT_THRESHOLD = 10 * 1024 * 1024
MAX_LARGE_REPORT_ITEMS = 80

# ─── Root-level files to always include ──────────────────────────────────────
# Only list files that actually exist at the project root.
# app.py and backend_factory.py were removed — they do not exist.
ROOT_FILES = {
    ".dockerignore",
    ".env.example",
    "README.md",
    "README_PRODUCTION.md",
    "docker-compose.yml",
    "requirements.txt",
}

# ─── Top-level directories whose entire subtree is included (subject to exclusions) ──
ROOT_DIRS = {
    "backend",
    "frontend",
    "nginx",
    "ocr_service",
    "scripts",
    "configs",
    "layers",
    "docs",
    "app",
}

# ─── Optional model inference artifacts ──────────────────────────────────────
INFERENCE_MODEL_FILES = {
    "models/semantic_arabert/best_threshold.json",
    "models/semantic_arabert/final_model/config.json",
    "models/semantic_arabert/final_model/model.safetensors",
    "models/semantic_arabert/final_model/pytorch_model.bin",
    "models/semantic_arabert/final_model/special_tokens_map.json",
    "models/semantic_arabert/final_model/tokenizer.json",
    "models/semantic_arabert/final_model/tokenizer_config.json",
    "models/semantic_arabert/final_model/vocab.txt",
    "models/semantic_arabert/final_model/merges.txt",
    "models/lexical_model/lexical_model_bundle.joblib",
    "models/lexical_model/lexical_thresholds.json",
}

# ─── Files that are ALWAYS safe to include, regardless of pattern matching ───
# .env.example would otherwise be caught by the ".env.*" pattern exclusion.
NEVER_EXCLUDE_NAMES: frozenset[str] = frozenset({
    ".env.example",
})

# ─── Directories to prune entirely during os.walk ────────────────────────────
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({
    # Version control / IDE
    ".git",
    ".idea",
    ".vscode",
    # Python cache
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
    # Dependencies
    "node_modules",
    ".venv",
    "venv",
    "env",
    # ML training artifacts
    "runs",
    "wandb",
    "tensorboard",
    "outputs",
    "training",
    "datasets",
    # Mobile / frontend build
    ".dart_tool",
    ".gradle",
    "build",
    # Deployment output (prevent recursive inclusion)
    "dist",
    # Local deployment / release archives
    "backups",
    "releases",
    # Phase 1B cleanup quarantine
    "_cleanup_quarantine",
    # Local backend runtime data
    "instance",
})

# ─── Exact filenames that must never appear in a deployment package ───────────
EXCLUDED_FILE_NAMES: frozenset[str] = frozenset({
    # Environment secrets — the most critical exclusion
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
    # ML training checkpoint state
    "optimizer.pt",
    "scheduler.pt",
    "trainer_state.json",
    "training_args.bin",
    "rng_state.pth",
})

# ─── Glob patterns for files to exclude ──────────────────────────────────────
EXCLUDED_FILE_PATTERNS: frozenset[str] = frozenset({
    # Local databases and state
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    # Logs
    "*.log",
    # Python bytecode
    "*.pyc",
    "*.pyo",
    # Temp / backup
    "*.tmp",
    "*.bak",
    # Env variants (.env.example is protected by NEVER_EXCLUDE_NAMES above)
    ".env.*",
    # Release / archive artifacts — avoid packaging the package itself
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.gz",
    "*.apk",
    "*.ipa",
    "*.aab",
})

# ─── Safety check: forbidden in final staging dir (belt + suspenders) ────────
_SAFETY_FORBIDDEN_NAMES: frozenset[str] = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
})
_SAFETY_FORBIDDEN_PATTERNS: frozenset[str] = frozenset({
    "*.db",
    "*.sqlite",
    "*.sqlite3",
})


# ─── Data types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LargeExcludedFile:
    rel_path: str
    size: int
    reason: str


# ─── Utilities ────────────────────────────────────────────────────────────────

def to_posix(path: Path) -> str:
    return path.as_posix()


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def is_checkpoint_part(part: str) -> bool:
    return fnmatch.fnmatch(part, "checkpoint-*")


# ─── Exclusion logic ──────────────────────────────────────────────────────────

def is_excluded_path(
    rel_path: Path,
    *,
    include_tests: bool = True,
) -> tuple[bool, str]:
    """
    Return (True, reason) if rel_path should be excluded from the package.

    Evaluation order:
      1. NEVER_EXCLUDE_NAMES — explicit allowlist overrides everything.
      2. EXCLUDED_DIR_NAMES — any path component (except filename) is a blocked dir.
      3. backend/instance/ — local runtime data (belt+suspenders; also in EXCLUDED_DIR_NAMES).
      4. backend/tests/   — excluded unless include_tests=True.
      5. EXCLUDED_FILE_NAMES — exact filename match (includes .env variants).
      6. EXCLUDED_FILE_PATTERNS — glob pattern match.
    """
    # 1. Explicit allowlist — never excluded
    if rel_path.name in NEVER_EXCLUDE_NAMES:
        return False, ""

    parts = rel_path.parts

    # 2. Directory-level exclusions (check all parts except the filename)
    if any(
        part in EXCLUDED_DIR_NAMES or is_checkpoint_part(part)
        for part in parts[:-1]
    ):
        return True, "excluded directory or checkpoint"

    # 3. backend/instance/ — local runtime data
    if len(parts) >= 2 and parts[0] == "backend" and parts[1] == "instance":
        return True, "local backend instance data"

    # 4. Test files — excluded from deployment packages by default
    if (
        not include_tests
        and len(parts) >= 2
        and parts[0] == "backend"
        and parts[1] == "tests"
    ):
        return True, "test files (omitted from deployment; use --include-tests to override)"

    name = rel_path.name

    # 5. Exact filename exclusions (includes .env and known variants)
    if name in EXCLUDED_FILE_NAMES:
        return True, "environment secrets or training checkpoint state"

    # 6. Pattern-based exclusions (.env.*, *.db, *.pyc, archives, …)
    if any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_FILE_PATTERNS):
        return True, "cache, log, secrets, database, or archive file"

    return False, ""


def is_selected_for_package(
    rel_path: Path,
    include_inference_models: bool,
) -> tuple[bool, str]:
    rel_posix = to_posix(rel_path)
    if rel_posix in ROOT_FILES:
        return True, "root runtime file"
    if rel_path.parts and rel_path.parts[0] in ROOT_DIRS:
        return True, "runtime source directory"
    if include_inference_models and rel_posix in INFERENCE_MODEL_FILES:
        return True, "optional inference model artifact"
    return False, "not selected for VPS runtime"


# ─── Directory walker ─────────────────────────────────────────────────────────

def _prune_walk(dirnames: list[str], current: Path) -> None:
    kept: list[str] = []
    for dirname in dirnames:
        rel = (current / dirname).relative_to(ROOT)
        parts = rel.parts
        if dirname in EXCLUDED_DIR_NAMES or is_checkpoint_part(dirname):
            continue
        if len(parts) >= 2 and parts[0] == "backend" and parts[1] == "instance":
            continue
        kept.append(dirname)
    dirnames[:] = kept


def iter_project_files() -> list[tuple[Path, Path]]:
    results: list[tuple[Path, Path]] = []
    for current_str, dirnames, filenames in os.walk(ROOT):
        current = Path(current_str)
        _prune_walk(dirnames, current)
        for filename in filenames:
            source = current / filename
            rel_path = source.relative_to(ROOT)
            results.append((source, rel_path))
    return results


def iter_project_files_for_report() -> list[tuple[Path, Path]]:
    prune_only = {".git", "node_modules", ".venv", "venv", "env", "dist", "__pycache__"}
    results: list[tuple[Path, Path]] = []
    for current_str, dirnames, filenames in os.walk(ROOT):
        current = Path(current_str)
        dirnames[:] = [d for d in dirnames if d not in prune_only]
        for filename in filenames:
            source = current / filename
            rel_path = source.relative_to(ROOT)
            results.append((source, rel_path))
    return results


# ─── Staging / zip ────────────────────────────────────────────────────────────

def copy_file(source: Path, rel_path: Path) -> int:
    target = STAGE_DIR / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return source.stat().st_size


def create_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in STAGE_DIR.rglob("*"):
            if not source.is_file():
                continue
            archive.write(source, source.relative_to(DIST_DIR))


def create_upload_instructions() -> None:
    text = """APG Production VPS Upload Instructions

Windows PowerShell:

scp dist/APG_Project_production_vps.zip root@YOUR_VPS_IP:/opt/

Ubuntu server:

ssh root@YOUR_VPS_IP
cd /opt
apt update
apt install -y unzip
rm -rf APG_Project
unzip APG_Project_production_vps.zip
cd APG_Project
cp backend/.env.example backend/.env
nano backend/.env          # fill in real secrets
docker compose up -d --build
docker compose ps
docker compose logs -f

If Docker is not installed on Ubuntu:

apt update
apt install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \\
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \\
  > /etc/apt/sources.list.d/docker.list
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker --version
docker compose version
"""
    UPLOAD_INSTRUCTIONS_PATH.write_text(text, encoding="utf-8")


# ─── Safety check ────────────────────────────────────────────────────────────

def safety_check_staged_files(staged: list[Path]) -> None:
    """
    Scan staged files and abort immediately if any forbidden file is found.

    This is a belt-and-suspenders verification after the exclusion logic runs.
    It catches bugs in the exclusion rules before a poisoned package leaves the machine.
    """
    violations: list[str] = []
    for p in staged:
        name = p.name
        rel = to_posix(p.relative_to(STAGE_DIR))
        if name in _SAFETY_FORBIDDEN_NAMES:
            violations.append(f"  [SECRETS] {rel}")
        elif any(fnmatch.fnmatch(name, pat) for pat in _SAFETY_FORBIDDEN_PATTERNS):
            violations.append(f"  [DATABASE] {rel}")
    if violations:
        print()
        print("[APG package] !! SAFETY CHECK FAILED — ABORTING !!")
        print("[APG package] The following forbidden files were staged:")
        for v in sorted(violations):
            print(v)
        print("[APG package] Cleaning up staging directory. Fix the exclusion rules and retry.")
        shutil.rmtree(STAGE_DIR, ignore_errors=True)
        raise SystemExit(1)
    print("[APG package] safety check passed — no secrets or database files in package.")


# ─── Large-file report ────────────────────────────────────────────────────────

def collect_large_excluded_files(
    include_inference_models: bool,
    include_tests: bool,
) -> list[LargeExcludedFile]:
    large_files: list[LargeExcludedFile] = []
    for source, rel_path in iter_project_files_for_report():
        selected, selection_reason = is_selected_for_package(rel_path, include_inference_models)
        excluded, exclude_reason = is_excluded_path(rel_path, include_tests=include_tests)
        if selected and not excluded:
            continue
        try:
            size = source.stat().st_size
        except OSError:
            continue
        if size < LARGE_REPORT_THRESHOLD:
            continue
        reason = exclude_reason or selection_reason
        if rel_path.parts and rel_path.parts[0] == "models" and not include_inference_models:
            reason = "model artifact excluded from default Docker/FastAPI package"
        large_files.append(LargeExcludedFile(to_posix(rel_path), size, reason))
    return sorted(large_files, key=lambda item: item.size, reverse=True)


# ─── Main packaging logic ─────────────────────────────────────────────────────

def package_project(
    *,
    include_inference_models: bool,
    include_tests: bool,
    dry_run: bool,
) -> None:
    all_files = iter_project_files()

    # Apply selection + exclusion filters
    included: list[tuple[Path, Path]] = []
    for source, rel_path in all_files:
        selected, _ = is_selected_for_package(rel_path, include_inference_models)
        excluded, _ = is_excluded_path(rel_path, include_tests=include_tests)
        if selected and not excluded:
            included.append((source, rel_path))

    # ── Dry-run mode ──────────────────────────────────────────────────────────
    if dry_run:
        print("[APG package] DRY-RUN MODE — no files written, no zip created.\n")
        total_bytes = 0
        for source, rel_path in sorted(included, key=lambda x: to_posix(x[1])):
            try:
                size = source.stat().st_size
            except OSError:
                size = 0
            total_bytes += size
            print(f"  {to_posix(rel_path):<80}  {format_bytes(size):>10}")
        print()
        print(f"[APG package] dry-run total: {len(included)} files, {format_bytes(total_bytes)}")
        print("[APG package] No .env or .db files listed above = exclusion rules are working.")
        return

    # ── Real mode: stage → safety check → zip ────────────────────────────────
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    staged: list[Path] = []
    copied_bytes = 0
    for source, rel_path in included:
        copied_bytes += copy_file(source, rel_path)
        staged.append(STAGE_DIR / rel_path)

    # Belt-and-suspenders: verify no secrets/databases slipped through
    safety_check_staged_files(staged)

    create_upload_instructions()
    create_zip()

    large_excluded = collect_large_excluded_files(include_inference_models, include_tests)
    print("[APG package] staging directory:", STAGE_DIR)
    print("[APG package] zip file:", ZIP_PATH)
    print("[APG package] copied:", len(included), "files,", format_bytes(copied_bytes))
    print("[APG package] zip size:", format_bytes(ZIP_PATH.stat().st_size))
    print("[APG package] upload instructions:", UPLOAD_INSTRUCTIONS_PATH)
    if include_inference_models:
        print("[APG package] inference model artifacts included where present.")
    else:
        print("[APG package] inference model artifacts not included (use --include-inference-models).")
    if not include_tests:
        print("[APG package] backend/tests/ excluded (use --include-tests to override).")

    if large_excluded:
        print("[APG package] large excluded files (>10 MB):")
        for item in large_excluded[:MAX_LARGE_REPORT_ITEMS]:
            print(f"  {format_bytes(item.size):>10}  {item.rel_path}  ({item.reason})")
        remaining = len(large_excluded) - MAX_LARGE_REPORT_ITEMS
        if remaining > 0:
            print(f"  ... {remaining} more large excluded files")
    else:
        print("[APG package] no excluded files above the reporting threshold.")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a clean APG production ZIP for Ubuntu/VPS deployment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  List files that would be included (safe preview):
    python scripts/package_for_vps.py --dry-run

  Standard deployment package (no tests, no ML models):
    python scripts/package_for_vps.py

  Include backend tests:
    python scripts/package_for_vps.py --include-tests

  Include ML inference model artifacts:
    python scripts/package_for_vps.py --include-inference-models
""",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be included without writing any output.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include backend/tests/ in the package (excluded by default for deployment).",
    )
    parser.add_argument(
        "--include-inference-models",
        action="store_true",
        help="Include runtime ML inference artifacts from models/. Training checkpoints remain excluded.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    package_project(
        include_inference_models=args.include_inference_models,
        include_tests=args.include_tests,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
