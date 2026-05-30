# APG — Demo Guide

## Overview

This guide walks through the key demo scenarios for APG — Arabic Phishing Guard for
AI Expo Jordan 2026.

---

## Prerequisites

- APG backend running (local or VPS — replace `YOUR_SERVER_IP` with your deployment address)
- Mobile app installed on Android device or emulator
- Admin dashboard accessible in browser
- Sample messages from the section below

---

## Health Check

Before the demo, verify the backend is up:

```
http://YOUR_SERVER_IP/api/health
```

Expected response: `{"status": "ok"}`

---

## Demo Flow

### Scenario 1 — Phishing SMS Detection (Mobile App)

**Goal:** Show that APG correctly detects a Jordan-specific phishing SMS.

**Steps:**

1. Open the APG mobile app
2. Tap "تحليل رسالة" (Analyze Message)
3. Paste this sample phishing message:

```
عميلنا العزيز، تم إيقاف حسابك في البنك العربي بسبب نشاط مشبوه.
يرجى تأكيد هويتك عبر الرابط: http://arab-bank-verify.xyz/confirm
```

4. Tap "تحليل" (Analyze)
5. Show the result:
   - Risk score: HIGH_RISK or PHISHING (60+)
   - Triggered evidence: Entity impersonation (Arab Bank), suspicious URL, urgency language
   - Explanation in Arabic

**Key talking points:**
- APG identified "البنك العربي" as a known Jordanian entity
- URL domain mismatch detected (arab-bank-verify.xyz ≠ arabbank.jo)
- Urgency language pattern triggered behavioral rules

---

### Scenario 2 — Legitimate SMS (No False Alarm)

**Goal:** Show APG does not over-flag legitimate messages.

**Steps:**

1. Analyze this legitimate message:

```
رسالة من زين: رصيدك الحالي 12.500 دينار. للاستفسار اتصل 900.
```

2. Show the result:
   - Risk score: SAFE (0–29)
   - Explanation: Known sender (Zain telecom), no suspicious links, no action pressure

---

### Scenario 3 — OTP Theft Attempt

**Goal:** Demonstrate OTP theft detection.

**Steps:**

1. Analyze this message:

```
مصرف الإسكان: رمز التحقق الخاص بك هو 847291. 
لا تشارك هذا الرمز مع أي شخص.
الدعم: أرسل لنا رمزك لتأكيد العملية.
```

2. Show the result:
   - Risk score: HIGH_RISK
   - Triggered: OTP sharing request pattern detected

---

### Scenario 4 — Notification Monitoring (Background)

**Goal:** Show real-time notification monitoring.

1. Open APG → "مراقبة الإشعارات" (Notification Monitor)
2. Show the service is running
3. Trigger a test notification
4. Show APG intercepting and analyzing it in the log
5. Tap the entry to see the full analysis result

---

### Scenario 5 — Admin Dashboard

**Goal:** Show the admin perspective.

1. Open the admin dashboard in a browser (`http://YOUR_SERVER_IP`)
2. Overview page: show analysis count, verdict breakdown chart, recent analyses
3. Users page: show registered users list
4. Analysis Log: filter by HIGH_RISK/PHISHING, open one result, show evidence breakdown
5. Highlight explainability: each risk factor is listed with its contribution

---

## Sample Messages for Live Demo

### High-Risk Examples

```
أوريدو: تم تعليق حسابك مؤقتاً. لتفادي الإيقاف النهائي انقر: http://oreedo-jo.net/verify
```

```
وزارة المالية: مستحقاتك المالية جاهزة للاستلام. سجل دخولك: http://mof.gov-jo.xyz/login
```

```
تهانينا! لقد فزت بجائزة 500 دينار من eFAWATEERcom. أرسل بياناتك لاستلام الجائزة: http://efawateer-prize.com
```

### Legitimate Examples

```
Zain: Your bill for this month is JD 12.50. Pay at any Zain shop or via zain.com
```

```
رسالة من البنك الأهلي: تم إتمام تحويلك بنجاح. للاستفسار: 06-5100000
```

---

## Tips for Demo Day

- Have the backend running and health check passing before the audience arrives
- Pre-load the history screen with a few analyses to show diversity
- Keep the admin dashboard open on a second screen or projector
- Use the sample messages above rather than improvising live
- Emphasize: Arabic-first, explainable scoring, Jordan-specific entity awareness
