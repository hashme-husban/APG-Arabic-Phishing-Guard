# APG — Arabic Phishing Guard

![Graduation Project](https://img.shields.io/badge/Graduation_Project-Al_al--Bayt_University-0066CC?style=flat-square)
![Arabic NLP](https://img.shields.io/badge/Arabic_NLP-AraBERT-orange?style=flat-square)
![Cybersecurity](https://img.shields.io/badge/Cybersecurity-Phishing_Detection-CC0000?style=flat-square)
![Flutter](https://img.shields.io/badge/Mobile-Flutter-02569B?style=flat-square)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square)
![Explainable AI](https://img.shields.io/badge/Explainable_AI-Risk_Engine-8A2BE2?style=flat-square)

> **Public academic repository — AI Expo Jordan 2026 submission**  
> Al al-Bayt University · Graduation Project 2026

**Arabic-first AI-powered phishing detection and risk analysis system for SMS, URLs, and Android notifications.**

APG is a full-stack security research project developed for AI Expo Jordan 2026. It detects Arabic phishing and smishing attempts using a hybrid AI risk engine, provides explainable risk scores, and monitors Android notifications in real time.

---

## Table of Contents

1. [Overview](#overview)
2. [Problem](#problem)
3. [Key Features](#key-features)
4. [System Architecture](#system-architecture)
5. [Hybrid AI / Risk Engine](#hybrid-ai--risk-engine)
6. [Dataset Summary](#dataset-summary)
7. [Tech Stack](#tech-stack)
8. [Repository Structure](#repository-structure)
9. [How to Run — Backend](#how-to-run--backend)
10. [How to Run — Mobile App](#how-to-run--mobile-app)
11. [How to Run — Admin Dashboard](#how-to-run--admin-dashboard)
12. [Demo Video](#demo-video)
13. [Documentation](#documentation)
14. [Security Notice](#security-notice)
15. [Limitations](#limitations)
16. [Future Work](#future-work)
17. [Team](#team)

---

## Overview

APG (Arabic Phishing Guard) is an Android mobile application and backend platform that:

- Detects **Arabic phishing and smishing** messages in real time
- Analyzes **suspicious URLs** from SMS and notifications
- Identifies **OTP theft attempts**, **fake banking messages**, and **entity impersonation**
- Provides **explainable risk scores** with human-readable justification
- Maintains an **analysis history** for users to review past detections
- Offers an **admin dashboard** for platform management and analytics

---

## Problem

Arabic speakers in Jordan and the broader MENA region face a growing wave of phishing and smishing attacks delivered in Arabic. Existing phishing detection tools are overwhelmingly English-centric and fail to handle:

- Arabic script and right-to-left text
- Jordan-specific entity impersonation (banks, telecoms, government portals)
- SMS-delivered social engineering in colloquial Arabic
- OTP hijacking and fake payment confirmation patterns

APG addresses this gap with an Arabic-first detection system tailored to the Jordanian digital context.

---

## Key Features

- **Arabic phishing/smishing detection** — Deep NLP analysis of Arabic SMS and notification text
- **Suspicious URL analysis** — Multi-provider URL reputation check with local heuristics
- **OTP theft detection** — Behavioral rules targeting OTP hijacking patterns
- **Fake banking/payment message detection** — Entity-aware classification for financial impersonation
- **Entity/brand impersonation detection** — Jordan-focused registry of 166 entities
- **Android notification monitoring** — Real-time background analysis of incoming notifications
- **Explainable risk score** — Human-readable Arabic/English explanation for every decision
- **Analysis history** — Persistent log of past analyses per user
- **Admin dashboard** — React web interface for platform management, user oversight, and analytics
- **FastAPI backend** — RESTful API with JWT authentication
- **PostgreSQL database** — Production-grade persistence

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Android Mobile App (Flutter)                                       │
│  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────────┐   │
│  │ Manual Input │  │ Notification Mon.│  │ Analysis History    │   │
│  └──────┬───────┘  └────────┬─────────┘  └─────────────────────┘   │
└─────────┼───────────────────┼─────────────────────────────────────┘
          │ HTTPS/REST API     │
┌─────────▼───────────────────▼─────────────────────────────────────┐
│  FastAPI Backend                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Hybrid Risk Engine                                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │   │
│  │  │ Sender   │ │ Text     │ │ URL      │ │ Entity       │   │   │
│  │  │ Verif.   │ │ Intell.  │ │ Intell.  │ │ Policy       │   │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │   │
│  │       └────────────┴────────────┴───────────────┘           │   │
│  │                    Decision Fusion Layer                     │   │
│  │                    Explanation Layer                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
          ┌───────────────────┼──────────────────────┐
          ▼                                          ▼
   PostgreSQL Database                   React Admin Dashboard
```

---

## Hybrid AI / Risk Engine

APG's risk engine is a layered pipeline — no single model makes the final verdict:

| Layer | Component | Role |
|-------|-----------|------|
| Layer 00 | Orchestrator | Request routing and session management |
| Layer 01 | Sender Verification | SPF/header analysis for email senders |
| Layer 02 | Entity Policy | Jordan entity registry + impersonation scoring |
| Layer 03 | Normalization | Arabic text normalization and encoding |
| Layer 04 | Text Intelligence | AraBERT + TF-IDF advisory models + behavioral rules |
| Layer 05 | URL Intelligence | Multi-provider reputation + URL heuristics |
| Layer 06 | Decision Fusion | Weighted score fusion from all layers |
| Layer 07 | Explanation | Human-readable risk explanation (Arabic + English) |

**AI models:**
- **AraBERT** (`aubmindlab/bert-base-arabertv2`) — Fine-tuned on Arabic phishing dataset; provides semantic confidence as advisory input
- **TF-IDF Lexical Classifier** — Fast lexical n-gram model; Arabic surface features; acts as a second advisory layer
- **Behavioral Rules** — 1,135 curated Arabic phishing phrase patterns covering urgency, impersonation, action pressure, and OTP theft
- **URL Intelligence** — Local heuristics + optional external providers (VirusTotal, Google Safe Browsing, URLScan, PhishTank)

---

## Dataset Summary

| Split / Set | Examples | Description |
|-------------|----------|-------------|
| Training split | 3,576 | Balanced augmented Arabic phishing/legitimate |
| Focused add-on | 368 | Jordan-context hard negatives |
| Validation set | 124 | Held-out for tuning |
| Test set | 124 | Final evaluation |
| Hard challenge set | 103 | Adversarial/edge-case examples |
| Behavioral phrases | 1,135 | Arabic phishing behavior dictionary |
| Entity registry | 166 | Jordan-focused entities |

Original Arabic email data sourced in part from:  
"Arabic Phishing and Legitimate emails — Samples" (Kaggle).  
Raw source files are **not redistributed** in this repository — see [data/README.md](data/README.md).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile App | Flutter (Dart), Android |
| Backend API | FastAPI (Python 3.11), Uvicorn, Gunicorn |
| Database | PostgreSQL 16 |
| Admin Dashboard | React 18, TypeScript, Vite, Tailwind CSS |
| AI — Semantic | AraBERT (`aubmindlab/bert-base-arabertv2`), HuggingFace Transformers, PyTorch |
| AI — Lexical | scikit-learn TF-IDF + Logistic Regression |
| Containerization | Docker, Docker Compose |
| OCR | Tesseract (Arabic), PaddleOCR microservice |
| Reverse Proxy | Nginx |
| Auth | JWT (python-jose), bcrypt |

---

## Repository Structure

```
APG-Arabic-Phishing-Guard/
├── backend/                  # FastAPI backend application
│   ├── app/
│   │   ├── routers/          # API endpoints
│   │   ├── services/         # Business logic
│   │   ├── models.py         # SQLAlchemy DB models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── auth.py           # JWT authentication
│   │   └── main.py           # FastAPI app entry point
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── mobile/                   # Flutter Android app
│   ├── lib/
│   │   ├── screens/          # UI screens
│   │   ├── models/           # Data models
│   │   ├── widgets/          # Reusable widgets
│   │   └── main.dart
│   └── pubspec.yaml
├── frontend/                 # React admin dashboard
│   ├── src/
│   │   ├── pages/            # Dashboard pages
│   │   ├── components/       # React components
│   │   ├── api/              # API client
│   │   └── store/            # State management
│   ├── package.json
│   └── .env.example
├── layers/                   # Risk engine pipeline layers (00–07)
├── configs/                  # JSON configs for risk engine
├── models/                   # ML model artifacts and metadata
│   ├── lexical_model/        # TF-IDF model bundle (included)
│   ├── semantic_arabert/     # AraBERT metadata (weights excluded — see models/README.md)
│   └── README.md
├── data/                     # Dataset splits
│   ├── processed/            # Training/val/test splits
│   ├── challenge_sets/       # Adversarial challenge sets
│   └── README.md
├── ocr_service/              # PaddleOCR microservice
├── nginx/                    # Nginx reverse proxy config
├── scripts/                  # Utility and dev scripts
├── docs/                     # Project documentation
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## How to Run — Backend

### Prerequisites

- Python 3.11+
- PostgreSQL 16 (or Docker)

### Local development (SQLite fallback)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL, JWT_SECRET, SMTP credentials

uvicorn app.main:app --reload --port 8000
```

API documentation available at: `http://127.0.0.1:8000/docs`

### Docker Compose (full stack)

```bash
cp .env.example .env
# Edit .env with your values

docker compose up --build
```

Services:
- Backend API: `http://localhost/api`
- Admin Dashboard: `http://localhost`
- PostgreSQL: port 5432 (internal only)

---

## How to Run — Mobile App

### Prerequisites

- Flutter SDK 3.x
- Android Studio / Android SDK
- Android device or emulator (API 26+)

```bash
cd mobile
flutter pub get
flutter run
```

By default the app points to `http://10.0.2.2:8000/api` (Android emulator localhost).  
To connect to a real backend, update `mobile/lib/config/` with your backend URL.

---

## How to Run — Admin Dashboard

### Local development

```bash
cd frontend
npm install
cp .env.example .env
# Set VITE_API_BASE_URL=http://127.0.0.1:8000/api for local backend

npm run dev
```

Dashboard available at: `http://localhost:5173`

### Production build

```bash
npm run build
# Outputs to frontend/dist/ — served by Nginx in Docker Compose
```

---

## Demo Video

> **Demo video:** To be added before AI Expo Jordan 2026 submission.  
> Record a 2–3 minute walkthrough of the mobile app and admin dashboard, then paste the link here.

---

## Documentation

> **Extended documentation:** To be added (project report, poster, slides).

| Document | Description |
|----------|-------------|
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | High-level project overview |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture details |
| [docs/AI_APPROACH.md](docs/AI_APPROACH.md) | AI/ML methodology |
| [docs/DATASET_SUMMARY.md](docs/DATASET_SUMMARY.md) | Dataset details and preprocessing |
| [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) | Full setup and deployment guide |
| [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) | Demo walkthrough |
| [data/README.md](data/README.md) | Dataset policy and licensing |
| [models/README.md](models/README.md) | Model artifacts policy |

---

## Security Notice

This repository is a **public research release**. The following are intentionally excluded:

- `.env` files with real credentials
- API keys (VirusTotal, Google Safe Browsing, URLScan, PhishTank)
- SMTP credentials and Gmail app passwords
- Database passwords and connection strings
- JWT secrets
- Android signing keys (`.keystore`, `.jks`)
- Database dumps (`.db`, `.sqlite`)
- Private server IP addresses

Use the provided `.env.example` files as templates. Generate strong secrets before any deployment.

> **Important:** If you are reproducing this project, generate fresh JWT secrets,
> database passwords, and API keys. Do not reuse any placeholder values in production.

---

## Limitations

- **Android-only** notification monitoring (iOS not implemented)
- Dataset size is moderate; larger corpora would improve recall on novel attack patterns
- Production hardening (HTTPS/TLS, domain, rate limiting) is recommended before any real deployment
- External URL reputation providers (VirusTotal, etc.) are optional; the system degrades gracefully without them
- The AraBERT fine-tuned weights are excluded from GitHub due to file size (516 MB)
- Dynamic URL sandbox (Playwright-based) is disabled by default and requires additional setup

---

## Future Work

- Expand the Arabic phishing dataset with diverse regional dialects
- iOS support for notification monitoring
- Browser extension for web-based phishing detection
- Production deployment hardening (HTTPS, WAF, monitoring)
- Active learning pipeline using feedback from user reports
- Landing-page analysis for URL-only messages (Phase 5B)

---

## Team

| Name | Role |
|------|------|
| **Hashem Ibrahim Al-Hosban** | Team Leader — Backend, Mobile Integration, AI Risk Engine |
| **Ruba Basem Al-Zyoud** | Co-Developer — UI, Testing, Documentation, Evaluation |
| **Dr. Mohammed Al-Shinwan** | Academic Supervisor |

**Institution:** Al al-Bayt University  
**Submission:** AI Expo Jordan 2026

---

## License

The **source code** in this repository is released under the [MIT License](LICENSE).

> **Important notice:** This license applies to the source code only.  
> Datasets, model artifacts, third-party resources, and external provider outputs  
> may have separate licenses and are **not automatically covered** by the MIT License.  
> See [data/README.md](data/README.md) and [models/README.md](models/README.md) for details.
