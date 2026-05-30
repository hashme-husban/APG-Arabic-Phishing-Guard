# APG — Project Overview

## What Is APG?

APG (Arabic Phishing Guard) is an Arabic-first AI-powered phishing detection and risk
analysis system. It targets the growing problem of Arabic SMS phishing (smishing) and
notification-based social engineering in the Jordanian and broader MENA digital context.

APG consists of three integrated components:

1. **Flutter mobile app** — Android app for manual SMS/URL analysis and real-time
   notification monitoring
2. **FastAPI backend** — Python REST API hosting the risk engine, ML models, and
   user/admin management
3. **React admin dashboard** — Web interface for platform administrators

---

## Who Is It For?

- **End users** — Arabic smartphone users who want to verify suspicious SMS, links, or
  notifications before acting on them
- **Security researchers** — Teams studying Arabic phishing patterns in the MENA region
- **Platform administrators** — Staff managing the APG service, reviewing analytics, and
  overseeing user activity

---

## Problem Being Solved

Arabic speakers face rising volumes of phishing and smishing attacks that:

- Impersonate Jordanian banks, telecom operators, and government services
- Use urgency-pressure language in colloquial Arabic
- Attempt OTP theft through fake security alerts
- Deploy suspicious shortened URLs in payment or prize-claim messages

Existing phishing tools are English-centric. APG fills the Arabic gap with a tailored,
explainable detection system.

---

## Core Capabilities

| Capability | Description |
|------------|-------------|
| Text analysis | Arabic NLP-based phishing detection for SMS and notifications |
| URL analysis | Link reputation checking with local + optional external providers |
| OTP threat detection | Rule-based OTP hijacking and banking fraud pattern detection |
| Entity impersonation | Jordan-specific entity registry (banks, telecoms, government) |
| Explainable scoring | Human-readable risk explanation in Arabic and English |
| History | Persistent analysis history per user |
| Notification monitoring | Real-time Android notification listener |
| Admin dashboard | User management, analytics, bulk analysis tools |

---

## Project Status

APG was developed as a research and expo demonstration project. The system is:

- Functional end-to-end (mobile → backend → database → dashboard)
- Deployed on a VPS for live demonstration during AI Expo Jordan 2026
- Not yet hardened for public production deployment (see Limitations in README)
