# APG — Setup Guide

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| Python | 3.11+ |
| Node.js | 18+ |
| Flutter | 3.x |
| PostgreSQL | 16 (or Docker) |
| Docker | 24+ (for full-stack compose) |
| Android SDK | API 26+ |

---

## Option A — Docker Compose (Recommended for Full Stack)

This is the fastest way to run the complete APG stack locally or on a VPS.

### 1. Clone the repository

```bash
git clone https://github.com/USERNAME/APG-Arabic-Phishing-Guard.git
cd APG-Arabic-Phishing-Guard
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — at minimum set:

```
POSTGRES_PASSWORD=your-strong-password
DATABASE_URL=postgresql+psycopg2://apg_user:your-strong-password@db:5432/apg
JWT_SECRET=your-long-random-jwt-secret
APP_SECRET=your-long-random-app-secret
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your-admin-password
```

For SMTP email (optional — required for user email verification):

```
SMTP_USERNAME=your-gmail@gmail.com
SMTP_PASSWORD=your_gmail_app_password
```

### 3. Build and start

```bash
docker compose up --build
```

### 4. Access services

| Service | URL |
|---------|-----|
| Admin dashboard | http://localhost |
| Backend API docs | http://localhost/api/docs |
| Health check | http://localhost/api/health |

---

## Option B — Manual Local Development

### Backend

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env (see above)

uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs

### Frontend (Admin Dashboard)

```bash
cd frontend
npm install

cp .env.example .env
# Set VITE_API_BASE_URL=http://127.0.0.1:8000/api

npm run dev
```

Dashboard: http://localhost:5173

### Mobile App

```bash
cd mobile
flutter pub get

# Start Android emulator or connect physical device
flutter run
```

The app defaults to `http://10.0.2.2:8000/api` (Android emulator → host localhost).
To connect to a remote backend, edit `mobile/lib/config/` with your backend URL.

---

## Setting Up AI Models

### TF-IDF Lexical Model

The lexical model bundle (`models/lexical_model/lexical_model_bundle.joblib`) is included
in the repository and loads automatically at backend startup.

### AraBERT Semantic Model

The AraBERT weights (`model.safetensors`, ~516 MB) are **not included** in the repository.

To use the AraBERT advisory layer:

**Option 1 — Re-train from the provided dataset:**

```bash
# Requires GPU (recommended: 8 GB VRAM minimum)
pip install transformers torch datasets

python models/semantic_arabert/train_arabert.py \
    --data_dir data/processed \
    --output_dir models/semantic_arabert/final_model
```

**Option 2 — Contact the team** to obtain the fine-tuned weights directly.

**If weights are missing:** The backend starts normally but the AraBERT advisory layer
is skipped. The TF-IDF + behavioral rules + URL intelligence layers still operate.
Configure `APG_ANALYZER_ENGINE=risk_engine_v1` in `.env`.

---

## Creating the Admin Account

After the backend is running:

```bash
cd backend
python scripts/create_admin.py --email admin@example.com --password yourpassword
```

Or with Docker:

```bash
docker compose exec backend python scripts/create_admin.py \
    --email admin@example.com --password yourpassword
```

---

## OCR Setup (Optional)

APG supports Arabic OCR for extracting text from notification screenshots.

**Tesseract** (default, included in Docker image):
- No extra setup needed in Docker
- For local development: install `tesseract-ocr` and `tesseract-ocr-ara`

**PaddleOCR microservice** (optional, higher accuracy):
- Runs as a separate `ocr_service` Docker container
- Configured automatically in `docker-compose.yml`
- To enable: `OCR_ENGINE=paddle_microservice` in `.env`

---

## URL Reputation Providers (Optional)

APG works without external URL APIs. To enable enhanced URL analysis, add API keys
to `.env`:

```
VIRUSTOTAL_API_KEY=your-key
GOOGLE_SAFE_BROWSING_API_KEY=your-key
URLSCAN_API_KEY=your-key
PHISHTANK_API_KEY=your-key
```

Missing keys are silently skipped — no errors.

---

## Production Deployment Notes

- Use a domain name with HTTPS/TLS (Let's Encrypt recommended)
- Update `CORS_ALLOWED_ORIGINS` in `.env` to your domain
- Change all default passwords and secrets before deploying
- Do not enable `APP_DEBUG=true` in production
- Review `nginx/nginx.conf` for rate limiting and security headers
- Set `ENABLE_DEV_SEED_ON_STARTUP=false` (already default)
