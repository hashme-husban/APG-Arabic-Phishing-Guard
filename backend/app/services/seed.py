from datetime import datetime, timedelta
from random import randint
from sqlalchemy.orm import Session
from app.models import AnalysisResult, Device, Incident, Report, SystemStatus, ThreatSignal, User
from app.services.masking import detect_url, mask_sensitive
from app.services.security import hash_password


def _upsert_dev_user(db: Session, *, name: str, email: str, password: str, role: str) -> User:
    """Create or repair a development account every startup.

    This is intentional for the local APG development console: if the SQLite DB
    already exists from an older build, the seed must still update the password,
    role, and active flag so the documented credentials always work.
    """
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None:
        user = User(
            name=name,
            email=normalized_email,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user

    changed = False
    if user.name != name:
        user.name = name
        changed = True
    if user.role != role:
        user.role = role
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    # Always refresh the dev password hash. This fixes stale SQLite databases
    # created before the credential/email changes.
    user.password_hash = hash_password(password)
    changed = True
    if changed:
        db.flush()
    return user


def seed_data(db: Session) -> None:
    # Development accounts. Both the public-looking email and the old .local
    # alias are kept working, and their passwords are repaired on every startup.
    admin_primary = _upsert_dev_user(db, name="APG Admin", email="admin@apg-secure.com", password="admin123", role="admin")
    _upsert_dev_user(db, name="APG Admin", email="admin@apg.local", password="admin123", role="admin")

    user = _upsert_dev_user(db, name="APG User", email="user@apg-secure.com", password="user123", role="user")
    _upsert_dev_user(db, name="APG User", email="user@apg.local", password="user123", role="user")

    # Ensure there is at least one device and seeded analysis data for the demo user.
    if db.query(Device).filter(Device.user_id == user.id).count() == 0:
        device = Device(user_id=user.id, device_label="dev-8A2F", platform="android", app_version="1.0.0")
        db.add(device)
        db.flush()
        samples = [
            ("manual", "تم تأكيد موعدك الجامعي غدًا الساعة 10 صباحًا", 12, "safe", ["لا توجد مؤشرات خطيرة"]),
            ("sms", "عاجل: سيتم إيقاف حسابك البنكي. أدخل رمز التحقق OTP 123456 عبر https://bit.ly/bank-secure", 94, "dangerous", ["طلب رمز تحقق OTP", "رابط مختصر", "صياغة استعجالية"]),
            ("whatsapp", "اربح جائزة الآن عبر الرابط التالي https://reward-login.example/verify", 78, "dangerous", ["وعد بجائزة", "مسار verify", "رابط غير موثوق"]),
            ("email", "يرجى تحديث بياناتك لتجنب تعليق الحساب عبر الرابط المرفق", 66, "suspicious", ["طلب تحديث بيانات", "تهديد بتعليق الحساب"]),
            ("notification", "رسالة من تطبيق غير معروف تطلب تسجيل الدخول من رابط خارجي", 58, "suspicious", ["مصدر غير معروف", "طلب تسجيل دخول"]),
        ]
        for idx, (source, text, score, cls, reasons) in enumerate(samples):
            db.add(AnalysisResult(
                user_id=user.id,
                device_id=device.id,
                source=source,
                input_text=text,
                masked_text=mask_sensitive(text),
                detected_url=detect_url(text),
                risk_score=score,
                classification=cls,
                reasons=reasons,
                recommendation="تحقق من المصدر الرسمي قبل اتخاذ أي إجراء." if cls != "safe" else "يمكن المتابعة بحذر.",
                needs_review=cls in {"dangerous", "suspicious"},
                review_status="pending" if cls in {"dangerous", "suspicious"} else "none",
                response_time_ms=randint(90, 260),
                created_at=datetime.utcnow() - timedelta(hours=idx * 4),
            ))

    # Add reports only when there are no reports yet, and attach them to actual seeded analyses.
    if db.query(Report).count() == 0:
        dangerous_items = db.query(AnalysisResult).filter(AnalysisResult.user_id == user.id, AnalysisResult.classification == "dangerous").limit(2).all()
        if dangerous_items:
            db.add(Report(analysis_id=dangerous_items[0].id, user_id=user.id, report_type="inaccurate_result", message="النتيجة تحتاج مراجعة لأنها تطلب OTP.", status="new"))
        if len(dangerous_items) > 1:
            db.add(Report(analysis_id=dangerous_items[1].id, user_id=user.id, report_type="missed_phishing", message="الرابط يبدو تصيديًا ولم يتم توضيح سبب كافٍ.", status="in_review"))

    if db.query(Incident).count() == 0:
        incidents = [
            ("Fake OTP banking campaign", "high", "active", "SMS", 75, 24, ["OTP request", "Shortened URL", "Urgency"], "Messages impersonate banks and request OTP verification codes.", "Block related shortened domains and warn affected users."),
            ("Login/verify link pattern", "medium", "monitoring", "Email", 41, 18, ["/verify path", "Account update"], "Emails push users to fake login verification pages.", "Increase link path weighting for verify/login routes."),
            ("Fake educational sender", "medium", "active", "WhatsApp", 26, 11, ["University sender", "Data update"], "Messages claim to be from education institutions.", "Review brand-sender similarity rules."),
            ("External APK link", "high", "monitoring", "Notification", 13, 8, ["External APK", "Unknown sender"], "Notifications direct users to install external APK files.", "Raise impact for APK link signal."),
            ("Prize/reward lure", "low", "resolved", "WhatsApp", 8, 5, ["Prize mention"], "Low-volume reward messages sharing suspicious links.", "Continue monitoring for new domains."),
        ]
        for i, row in enumerate(incidents):
            db.add(Incident(
                title=row[0], severity=row[1], status=row[2], channel=row[3], cases_count=row[4], affected_devices=row[5],
                indicators=row[6], description=row[7], recommended_action=row[8],
                first_seen=datetime.utcnow() - timedelta(days=4 + i), last_seen=datetime.utcnow() - timedelta(hours=i * 3)
            ))

    if db.query(ThreatSignal).count() == 0:
        signals = [
            ("OTP code request", "text", "Detects requests for one-time verification codes.", "high", True, 92, "low"),
            ("Shortened URL", "link", "Detects bit.ly and similar short links.", "high", True, 82, "medium"),
            ("Account closure threat", "behavior", "Urgent wording about account suspension or closure.", "high", True, 76, "medium"),
            ("Sender resembles known brand", "sender", "Flags sender names similar to banks or platforms.", "medium", True, 64, "medium"),
            ("Banking data request", "text", "Detects direct requests for banking information.", "high", True, 96, "low"),
            ("/verify path", "link", "Detects suspicious verify/login paths.", "medium", True, 58, "medium"),
            ("Prize or reward mention", "text", "Detects prize/reward lures.", "low", True, 34, "high"),
            ("External APK link", "link", "Detects links to APK downloads.", "high", True, 88, "low"),
        ]
        for s in signals:
            db.add(ThreatSignal(name=s[0], category=s[1], description=s[2], impact=s[3], enabled=s[4], weight=s[5], false_positive_risk=s[6]))

    if db.query(SystemStatus).count() == 0:
        db.add(SystemStatus(server_status="connected", database_status="connected", api_latency_ms=124, model_version="APG-NLP v1.9", rules_version="rules-2026.05"))

    db.commit()

# ---- Final production polish seed helpers ----

def _ensure_incident(db: Session, title: str, severity: str, status: str, channel: str, cases: int, devices: int, indicators: list[str], description: str, action: str) -> None:
    item = db.query(Incident).filter(Incident.title == title).first()
    if item:
        item.severity = severity
        item.status = status
        item.channel = channel
        item.cases_count = max(item.cases_count or 0, cases)
        item.affected_devices = max(item.affected_devices or 0, devices)
        item.indicators = indicators
        item.description = description
        item.recommended_action = action
        item.updated_at = datetime.utcnow()
        return
    db.add(Incident(
        title=title, severity=severity, status=status, channel=channel,
        cases_count=cases, affected_devices=devices, indicators=indicators,
        description=description, recommended_action=action,
        first_seen=datetime.utcnow() - timedelta(days=randint(2, 12)),
        last_seen=datetime.utcnow() - timedelta(hours=randint(1, 18)),
    ))


def _ensure_signal(db: Session, name: str, category: str, description: str, impact: str, enabled: bool, weight: int, fp: str) -> None:
    item = db.query(ThreatSignal).filter(ThreatSignal.name == name).first()
    if item:
        item.category = category
        item.description = description
        item.impact = impact
        item.enabled = enabled
        item.weight = weight
        item.false_positive_risk = fp
        item.updated_at = datetime.utcnow()
        return
    db.add(ThreatSignal(name=name, category=category, description=description, impact=impact, enabled=enabled, weight=weight, false_positive_risk=fp))


def _seed_polish_data(db: Session, admin: User, user: User) -> None:
    more_incidents = [
        ("Fake OTP banking campaign", "high", "active", "SMS", 75, 24, ["OTP request", "Shortened URL", "Urgency", "Bank name"], "Bank impersonation messages request OTP codes through shortened links.", "Keep OTP detection enabled and block related short-link domains."),
        ("Login/verify link pattern", "medium", "monitoring", "Email", 41, 18, ["/verify path", "/login path", "Account update"], "Messages push users to fake login or verification pages.", "Increase link-path signal weight and review related cases."),
        ("Fake educational sender", "medium", "active", "WhatsApp", 26, 11, ["University sender", "Data update", "Urgent wording"], "Arabic messages impersonate educational institutions and ask for account updates.", "Tune trusted-sender checks for universities and schools."),
        ("Fake update notifications", "low", "monitoring", "Notification", 18, 9, ["App update", "External site"], "Notifications direct users to update accounts outside official apps.", "Monitor notifications from non-approved apps."),
        ("Banking data requests", "high", "active", "SMS", 63, 21, ["Banking data request", "Account closure threat"], "Messages ask users for account or card information under urgency.", "Escalate banking data signal and review sources."),
        ("Shortened URL redirect campaign", "high", "monitoring", "WhatsApp", 54, 17, ["Shortened URL", "Redirect", "Reward lure"], "Shortened URLs redirect to fake prize or login pages.", "Add redirect-chain checks to link inspection."),
        ("Fake prize reward campaign", "low", "resolved", "WhatsApp", 22, 10, ["Prize/reward mention", "Unknown sender"], "Low-volume reward lures with suspicious links.", "Keep monitoring for fresh domains."),
    ]
    for row in more_incidents:
        _ensure_incident(db, *row)

    more_signals = [
        ("OTP code request", "text", "Detects requests for one-time verification codes.", "high", True, 92, "low"),
        ("Shortened URL", "link", "Detects bit.ly and similar short links.", "high", True, 82, "medium"),
        ("Account closure threat", "behavior", "Urgent wording about account suspension or closure.", "high", True, 76, "medium"),
        ("Sender resembles known brand", "sender", "Flags sender names similar to banks or platforms.", "medium", True, 64, "medium"),
        ("Banking data request", "text", "Detects direct requests for banking or card data.", "high", True, 96, "low"),
        ("/verify path", "link", "Detects suspicious verification paths.", "medium", True, 58, "medium"),
        ("/login path", "link", "Detects login paths used by suspicious URLs.", "medium", True, 57, "medium"),
        ("Prize/reward mention", "text", "Detects prize and reward lures.", "low", True, 34, "high"),
        ("External APK link", "link", "Detects links to APK downloads outside official stores.", "high", True, 88, "low"),
        ("Urgent action wording", "behavior", "Detects urgent calls to act immediately.", "medium", True, 61, "medium"),
        ("Suspicious domain age", "link", "Weights newly observed or unknown domains.", "medium", True, 55, "medium"),
        ("URL without message context", "link", "Flags URL-only inputs with little supporting context.", "medium", True, 49, "medium"),
    ]
    for row in more_signals:
        _ensure_signal(db, *row)

    # Add more activity/action history if audit is sparse.
    from app.models import AdminAction
    if db.query(AdminAction).count() < 5:
        db.add(AdminAction(admin_id=admin.id, action_type="rules_synced", target_type="system", note="rules-2026.05 loaded"))
        db.add(AdminAction(admin_id=admin.id, action_type="signal_updated", target_type="threat_signal", target_id=1, note="OTP signal weight reviewed"))
        db.add(AdminAction(admin_id=admin.id, action_type="incident_resolved", target_type="incident", target_id=1, note="Legacy incident closed"))
        db.add(AdminAction(admin_id=admin.id, action_type="connection_tested", target_type="system", note="latency=118ms"))

    db.commit()

# Wrap original seed_data to extend existing seed without duplicating UI logic.
_original_seed_data = seed_data

def seed_data(db: Session) -> None:  # type: ignore[no-redef]
    _original_seed_data(db)
    admin = db.query(User).filter(User.email == "admin@apg-secure.com").first() or db.query(User).filter(User.role == "admin").first()
    user = db.query(User).filter(User.email == "user@apg-secure.com").first() or db.query(User).filter(User.role == "user").first()
    if admin and user:
        _seed_polish_data(db, admin, user)
