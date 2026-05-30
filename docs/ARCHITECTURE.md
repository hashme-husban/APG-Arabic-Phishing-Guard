# APG — System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Android Mobile App (Flutter)                                       │
│  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────────┐   │
│  │ Manual Input │  │ Notification Mon.│  │ Analysis History    │   │
│  └──────┬───────┘  └────────┬─────────┘  └─────────────────────┘   │
└─────────┼───────────────────┼─────────────────────────────────────┘
          │ HTTPS REST API     │
┌─────────▼───────────────────▼─────────────────────────────────────┐
│  Nginx Reverse Proxy                                                │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
          ┌───────────────────┼──────────────────────┐
          ▼                   ▼                      ▼
   FastAPI Backend      OCR Microservice      React Dashboard
   (port 8000)          (port 9000)           (port 80, built)
          │
          ▼
   Hybrid Risk Engine
   (layered pipeline)
          │
          ▼
   PostgreSQL Database
```

---

## Backend Internal Structure

### API Layer (`backend/app/routers/`)

| Router | Endpoints |
|--------|-----------|
| `auth.py` | `/api/auth/*` — login, register, OTP, token refresh |
| `analysis.py` | `/api/analyze` — submit text/URL for analysis |
| `history.py` | `/api/history/*` — user analysis history |
| `admin.py` | `/api/admin/*` — admin management endpoints |
| `health.py` | `/api/health` — health check for Docker |

### Risk Engine Pipeline (`layers/`)

The core detection logic is a sequential pipeline of layers. Each layer processes the
input and adds scored evidence to a shared context object passed downstream.

```
Request
   │
   ▼
layer_00_orchestrator      — Validates input, builds context object
   │
   ▼
layer_01_sender_verification — Checks sender header/SPF signals (email)
   │
   ▼
layer_02_entity_policy      — Detects entity impersonation vs. Jordan registry
   │
   ▼
layer_03_normalization      — Arabic text normalization (diacritics, encoding)
   │
   ▼
layer_04_text_intelligence  — AraBERT advisory + TF-IDF advisory + behavioral rules
   │
   ▼
layer_05_url_intelligence   — URL extraction, heuristics, optional external reputation
   │
   ▼
layer_06_decision_fusion    — Weighted fusion of all layer signals → risk score 0–100
   │
   ▼
layer_07_explanation        — Generates human-readable explanation
   │
   ▼
Response (risk_score, verdict, explanation, evidence)
```

---

## Mobile App Structure (`mobile/lib/`)

```
lib/
├── main.dart                  — App entry point
├── config/                    — API base URL, constants
├── models/                    — Analysis result, history, user models
├── screens/
│   ├── home_screen.dart       — Main analysis input screen
│   ├── result_screen.dart     — Risk score display
│   ├── history_screen.dart    — Past analyses
│   ├── notification_screen.dart — Notification monitor
│   └── auth/                  — Login/register screens
├── widgets/                   — Reusable UI components
└── theme/                     — App color scheme and typography
```

---

## Admin Dashboard Structure (`frontend/src/`)

```
src/
├── pages/
│   ├── DashboardPage.tsx      — Analytics overview
│   ├── UsersPage.tsx          — User management
│   ├── AnalysisPage.tsx       — Analysis log browser
│   └── SettingsPage.tsx       — Platform settings
├── components/                — Shared React components
├── api/                       — Axios API client (uses JWT from localStorage)
├── store/                     — Zustand state management
├── i18n/                      — Arabic/English UI strings
├── layouts/                   — Admin layout shell
└── types/                     — TypeScript types matching backend schemas
```

---

## Database Schema (simplified)

```
users
  id, email, hashed_password, role, is_verified, created_at

analyses
  id, user_id, input_text, input_url, risk_score, verdict,
  explanation, evidence_json, created_at

notifications_log
  id, user_id, app_name, notification_text, risk_score, created_at

admin_settings
  key, value, updated_at
```

---

## Docker Compose Services

| Service | Image | Port |
|---------|-------|------|
| `db` | postgres:16-alpine | 5432 (internal) |
| `backend` | custom (Python 3.11) | 8000 (internal) |
| `ocr_service` | custom (PaddleOCR) | 9000 (internal) |
| `frontend` | custom (Nginx + built React) | 80 (public) |

All inter-service communication is internal to the Docker network. Only port 80 is exposed publicly.
