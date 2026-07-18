# APG Project Structure

**Arabic Phishing Guard (APG)** — Single-author project for detecting Arabic-language phishing content.
Author: Hashem Ibrahim Al-Hosban
Role: Project Owner, Researcher, Developer
Cleaned and organized. Last validation: 2026-05-22.

---

## Top-Level Layout

```
APG_Project/
├── backend/              # FastAPI Python backend (runtime)
├── mobile/               # Flutter mobile app (runtime)
├── frontend/             # React + Vite admin dashboard (runtime)
├── configs/              # Shared JSON config files for risk engine
├── data/                 # Training datasets (not loaded at runtime)
├── nginx/                # nginx reverse proxy config
├── docs/                 # Documentation, reports, screenshots
├── archive/              # Preserved old/unused files — NOT runtime
├── docker-compose.yml    # Production orchestration (3 services)
├── start_backend_windows.bat   # Windows dev shortcut: FastAPI
├── start_frontend_windows.bat  # Windows dev shortcut: React
└── PROJECT_STRUCTURE.md  # This file
```

---

## backend/

FastAPI Python backend. Entry point: `backend/app/main.py`.

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory — registers all routers
│   ├── database.py          # SQLAlchemy engine + session setup
│   ├── models/              # ORM models (User, AnalysisResult, etc.)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/
│   │   ├── auth.py          # /api/auth — login, register, token
│   │   ├── analysis.py      # /api/analysis — phishing detection
│   │   └── admin.py         # /api/admin — admin-only endpoints
│   └── services/
│       ├── hybrid_analyzer.py         # Selects engine based on APG_ANALYZER_ENGINE env var
│       ├── risk_engine/               # Active modular risk assessment engine (19 files + 5 YAMLs)
│       └── analyzer/                  # Legacy analyzer (conditionally active via env var)
│           └── ai_adapter.py          # Imports SemanticModelAdapter + LexicalModelAdapter from layers/
├── layers/                  # AI model adapters — partially active: imported by ai_adapter.py
│   │                        # only when APG_ANALYZER_ENGINE=analyzer is set. Do not delete.
│   └── layer_04_text_intelligence/
│       ├── semantic_adapter.py
│       └── lexical_adapter.py
├── Dockerfile               # gunicorn + uvicorn, port 8000, 2 workers
├── requirements.txt         # fastapi, uvicorn, sqlalchemy, torch, transformers, etc.
└── .env                     # Secrets — DO NOT READ OR COMMIT
```

**Runtime entry point:** `gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000`

**Engine selection:** Set `APG_ANALYZER_ENGINE=risk_engine` (default) or `APG_ANALYZER_ENGINE=analyzer` in `.env`.

**Important:** `backend/layers/` is partially active — `ai_adapter.py` imports from it when `APG_ANALYZER_ENGINE=analyzer`. Do not delete it even if the default engine is `risk_engine`.

---

## mobile/

Flutter mobile app (Dart). Entry point: `mobile/lib/main.dart`.

```
mobile/
├── lib/
│   ├── main.dart            # App entry — splash, routing, theme, locale
│   ├── config/
│   │   └── app_config.dart  # Environment/API config
│   ├── l10n/                # Localization (Arabic + English)
│   ├── theme/
│   │   ├── app_tokens.dart  # Color/spacing design tokens (AppTokens class)
│   │   └── app_theme.dart   # ThemeData builder — AppTheme.light() / .dark()
│   ├── screens/
│   │   ├── onboarding_screen.dart   # First-launch onboarding
│   │   ├── login_screen.dart        # Authentication
│   │   ├── app_shell.dart           # 5-tab shell: Home, Analyze, Monitor, History, Settings
│   │   ├── admin_shell.dart         # Admin navigation shell
│   │   ├── home_screen.dart
│   │   ├── analyze_screen.dart
│   │   ├── monitoring_screen.dart
│   │   ├── history_screen.dart
│   │   └── settings_screen.dart
│   ├── services/            # API calls, auth, local storage
│   └── widgets/             # Shared UI components
├── assets/
│   ├── branding/            # App logo (apg_logo_transparent.png)
│   └── fonts/
├── android/                 # Android platform files
├── ios/                     # iOS platform files
└── pubspec.yaml             # Active Flutter dependency manifest
```

**Navigation flow:** `main.dart` → `OnboardingScreen` (first launch) → `LoginScreen` → `AppShell` (user) or `AdminShell` (admin).

**Note:** The old `lib/admin/` folder (standalone admin UI demo) was archived during cleanup and is no longer present in `mobile/lib/`. The active admin shell is `mobile/lib/screens/admin_shell.dart`. The archived copy is at `archive/unused_mobile/admin/`.

**Theme system:** Uses `AppTokens` (not `AppColors` — that class is obsolete and has been archived).

---

## frontend/

React + TypeScript admin dashboard, built with Vite. Served by nginx in production.

```
frontend/
├── src/
│   ├── main.tsx             # React entry point
│   ├── App.tsx              # Router + layout
│   ├── pages/               # Dashboard, Users, Analysis, Reports pages
│   ├── components/          # Shared UI components
│   ├── services/            # API client
│   └── types/               # TypeScript type definitions
├── dist/                    # Built output — served by nginx (DO NOT DELETE)
├── public/
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## configs/

10 JSON configuration files consumed by the risk engine at runtime.

```
configs/
├── entity_aliases.json
├── entity_policy_config.json
├── entity_policy_rules.json
├── fusion_layer_config.json
├── output_layer_config.json
├── sender_layer_config.json
├── sender_registry.json
├── text_layer_config.json
├── url_brand_hints.json
└── url_layer_config.json
```

These are loaded by the risk engine services. Do not delete.

---

## data/

Training and evaluation datasets. **Not loaded at runtime.**

```
data/
├── arabic_phishing_dataset.csv   (or similar)
└── ...
```

Safe to exclude from production deployments.

---

## nginx/

```
nginx/
└── nginx.conf    # Reverse proxy: routes /api/* to backend:8000, / to frontend:80
```

Used in Docker production deployment only.

---

## docker-compose.yml

Defines 3 services for production:

| Service    | Image / Build         | Port  | Purpose                        |
|------------|-----------------------|-------|--------------------------------|
| `db`       | postgres:16-alpine    | 5432  | PostgreSQL database            |
| `backend`  | backend/Dockerfile    | 8000  | FastAPI application            |
| `frontend` | frontend/Dockerfile   | 80    | React app served via nginx     |

---

## docs/

Non-runtime documentation, reports, and design files.

```
docs/
├── APG_Final_Report.pdf         (or similar graduation report)
├── APG_System_Design.pdf
├── mobile/
│   ├── mobile_wireframes.pdf    (or design mockups)
│   └── ...
└── screenshots/
    └── ...
```

---

## archive/

**Preserved files that are no longer part of the active runtime.** Nothing here is deleted — it is kept for reference, history, or potential recovery. Do not deploy any of these.

```
archive/
├── unused_mobile/          # Flutter files removed during design system upgrade
│   ├── screens/
│   │   ├── result_screen.dart        # Used AppColors (obsolete), no active importers
│   │   ├── report_screen.dart        # Used AppColors (obsolete), no active importers
│   │   └── statistics_screen.dart    # Used AppColors (obsolete), no active importers
│   ├── widgets/
│   │   ├── shared.dart               # Used AppColors (obsolete)
│   │   ├── stat_card.dart            # Used AppColors (obsolete)
│   │   ├── section_card.dart         # Used AppColors (obsolete)
│   │   └── empty_state_card.dart     # Used AppColors (obsolete)
│   └── admin/                        # Old standalone admin UI demo (6 files)
│       └── admin_shell.dart          # Different signature from active screens/admin_shell.dart
│
├── legacy_backend/         # Flask-era backend files (replaced by FastAPI)
│   ├── app.py                        # Complete Flask backend (606 lines), ran on port 5000
│   └── apg_layers_engine.py          # Flask-era layers adapter (108 lines), called only by app.py
│
├── experimental/           # One-off scripts and test utilities, never part of deployment
│   ├── app.py
│   ├── backend_factory.py
│   ├── inspect_lexical_bundle.py
│   ├── smoke_test_backend.py
│   ├── test_orchestrator.py
│   └── backend_helpers/
│       ├── _check_coverage.py
│       ├── _test_phrases.py
│       ├── _test_phrases2.py
│       └── _trace_case.py
│
├── root_patches/           # Ad-hoc patch scripts from root level
│   ├── patch_apg.py
│   └── patch2.py
│
├── orphaned_configs/       # Stale config copies that duplicated active files
│   ├── pubspec.yaml                  # Older incomplete copy (missing dependencies vs mobile/pubspec.yaml)
│   └── package-lock.json             # Empty 90-byte stub
│
└── model_evaluation/       # Model evaluation results (hardcoded paths to dev machine)
    └── evaluation/
        ├── evaluate_models_on_layered_challenge.py
        ├── *.csv
        └── *.json
```

---

## Runtime-Critical Files — Do Not Delete

| Path | Why critical |
|------|-------------|
| `backend/app/` | Entire FastAPI application package |
| `backend/layers/` | Partially active — imported by `ai_adapter.py` when `APG_ANALYZER_ENGINE=analyzer` |
| `backend/requirements.txt` | Python dependency manifest |
| `backend/Dockerfile` | Container build instructions |
| `backend/.env` | Runtime secrets and config |
| `mobile/lib/` | All active Dart source code |
| `mobile/pubspec.yaml` | Flutter dependency manifest |
| `mobile/assets/` | App logo and fonts |
| `frontend/dist/` | Built React app served by nginx |
| `frontend/package.json` | Node dependency manifest |
| `configs/` | All 10 JSON files used by risk engine |
| `nginx/nginx.conf` | Reverse proxy routing |
| `docker-compose.yml` | Production service orchestration |

---

## How to Run

### Production (Docker)

```bash
docker compose up --build
```

- Backend API: http://localhost:8000
- Admin dashboard: http://localhost:80

### Backend (Windows dev)

```bash
# From APG_Project root
start_backend_windows.bat
# Runs: uvicorn app.main:app --reload --port 8000
```

Or manually:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (Windows dev)

```bash
# From APG_Project root
start_frontend_windows.bat
# Runs: npm install && npm run dev
```

Or manually:
```bash
cd frontend
npm install
npm run dev
```

### Mobile (Flutter)

```bash
cd mobile
flutter pub get
flutter run
```

---

## Validation Status (2026-05-22)

| Check | Command | Result |
|-------|---------|--------|
| Backend syntax | `python -m compileall backend -q` | **PASS** — 0 errors |
| Flutter analysis | `flutter analyze` (from `mobile/`) | **PASS** — 0 errors |
| Frontend build | `npm run build` (from `frontend/`) | **PASS** — build succeeded |
| Docker config | `docker compose config` | **Not verified locally** — Docker not available on this machine |
