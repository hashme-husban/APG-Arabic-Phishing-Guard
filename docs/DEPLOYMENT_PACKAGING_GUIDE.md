# APG Deployment Packaging Guide

**Last updated:** 2026-05-23

---

## Overview

`scripts/package_for_vps.py` creates a clean production ZIP that is safe to upload
to a VPS.  It enforces strict exclusion rules and runs a post-staging safety check
before finalising the archive.

---

## Quick Start

```bash
# Preview — lists files that WOULD be included, writes nothing
python scripts/package_for_vps.py --dry-run

# Standard deployment package (no tests, no ML model weights)
python scripts/package_for_vps.py

# Include backend/tests/ (e.g. for staging environment)
python scripts/package_for_vps.py --include-tests

# Include ML inference model artifacts (~500 MB+)
python scripts/package_for_vps.py --include-inference-models
```

Output is written to `dist/APG_Project_production_vps.zip`.

---

## Security Guarantees

### Files that are NEVER included

| Category | Exclusion mechanism |
|---|---|
| `.env` | `EXCLUDED_FILE_NAMES` (exact match) |
| `.env.local`, `.env.production`, `.env.staging`, `.env.test`, `.env.development` | `EXCLUDED_FILE_NAMES` + `.env.*` pattern |
| `*.db`, `*.sqlite`, `*.sqlite3` | `EXCLUDED_FILE_PATTERNS` |
| `__pycache__/`, `*.pyc`, `*.pyo` | Dir + pattern exclusion |
| `backend/instance/` | Directory exclusion (local runtime data) |
| `backups/`, `releases/` | Directory exclusion |
| `*.zip`, `*.tar`, `*.tar.gz`, `*.apk` | Pattern exclusion (avoids packaging the package itself) |
| `*.log` | Pattern exclusion |

### Files that ARE included (intentionally)

| File | Reason |
|---|---|
| `backend/.env.example` | Safe template — no real secrets; protected by `NEVER_EXCLUDE_NAMES` |
| `.env.example` (root) | Same — always allowed regardless of `.env.*` pattern |

### Post-staging safety check (belt + suspenders)

After all files are copied to the staging directory and **before** the ZIP is
created, `safety_check_staged_files()` scans every staged file and fails
immediately if any `.env` (exact match) or `*.db / *.sqlite` file is found.

If the check fails:
- The staging directory is deleted.
- The script exits with code 1.
- No ZIP is written.

This means a bug in the exclusion rules cannot silently produce a poisoned package.

---

## Exclusion Rule Reference

### `EXCLUDED_DIR_NAMES` (entire subtree pruned)

```
.git, .idea, .vscode                       # version control / IDE
.pytest_cache, .mypy_cache, __pycache__    # Python cache
node_modules, .venv, venv, env             # dependency installs
.dart_tool, .gradle, build, dist           # mobile / frontend build
runs, wandb, tensorboard, outputs,         # ML training artifacts
training, datasets
backups, releases                          # local archives
_cleanup_quarantine                        # Phase 1B cleanup
instance                                   # local backend runtime data
```

### `EXCLUDED_FILE_NAMES` (exact filename match)

```
.env, .env.local, .env.production, .env.development, .env.staging, .env.test
optimizer.pt, scheduler.pt, trainer_state.json, training_args.bin, rng_state.pth
```

### `EXCLUDED_FILE_PATTERNS` (glob match on filename)

```
*.db, *.sqlite, *.sqlite3          # databases
*.log                              # logs
*.pyc, *.pyo                       # Python bytecode
*.tmp, *.bak                       # temporaries
.env.*                             # all .env variants (EXCEPT .env.example — see NEVER_EXCLUDE_NAMES)
*.zip, *.tar, *.tar.gz, *.gz       # archives
*.apk, *.ipa, *.aab                # mobile release artifacts
```

### `NEVER_EXCLUDE_NAMES` (always included, overrides patterns)

```
.env.example
```

---

## What is Included by Default

Selected by `ROOT_FILES` (root-level files):
```
.dockerignore
.env.example
README.md
README_PRODUCTION.md
docker-compose.yml
requirements.txt
```

Selected by `ROOT_DIRS` (top-level directory subtrees):
```
backend/    frontend/    nginx/    scripts/
configs/    layers/      docs/     app/
```

**`backend/tests/`** is excluded by default. Use `--include-tests` to override.

**`models/`** (ML weights) is excluded by default. Use `--include-inference-models`
to include only the inference artifacts (not training checkpoints).

---

## Deploying to VPS

```bash
# 1. Build the package
python scripts/package_for_vps.py --dry-run    # verify first
python scripts/package_for_vps.py              # build

# 2. Upload
scp dist/APG_Project_production_vps.zip root@YOUR_VPS_IP:/opt/

# 3. On the server
ssh root@YOUR_VPS_IP
cd /opt
unzip APG_Project_production_vps.zip
cd APG_Project
cp backend/.env.example backend/.env    # create from template
nano backend/.env                       # fill in real secrets
docker compose up -d --build
docker compose ps
docker compose logs -f
```

---

## Adding a New Exclusion Rule

To exclude a specific filename everywhere:
```python
# In scripts/package_for_vps.py
EXCLUDED_FILE_NAMES: frozenset[str] = frozenset({
    ...,
    "your-file.ext",
})
```

To exclude by pattern:
```python
EXCLUDED_FILE_PATTERNS: frozenset[str] = frozenset({
    ...,
    "*.ext",
})
```

To exclude a top-level directory:
```python
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({
    ...,
    "your-dir",
})
```

Always run `--dry-run` after changing rules to verify the change has the intended effect.

---

## Troubleshooting

**Safety check failed:**
```
[APG package] !! SAFETY CHECK FAILED — ABORTING !!
[APG package] The following forbidden files were staged:
  [SECRETS] backend/.env
```
A `.env` or `*.db` file was staged despite the exclusion rules. Check that the
file doesn't have an unusual name that bypasses the pattern (e.g., `prod.env`).
Add it to `EXCLUDED_FILE_NAMES` or `EXCLUDED_FILE_PATTERNS` and re-run.

**File I expect to be included is missing:**
Run `--dry-run` and search the output. If the file is from a directory not in
`ROOT_DIRS`, add the directory. If it matches an exclusion pattern, add an entry
to `NEVER_EXCLUDE_NAMES`.

**`dist/` folder grows large:**
The `dist/` directory is in `EXCLUDED_DIR_NAMES`, so the packaging script never
includes its own output in the next package. Delete `dist/` between builds to
keep it clean.
