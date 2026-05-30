from __future__ import annotations

from .contexts import ContextDetector
from .entities import EntityExtractor
from .intents import IntentDetector
from .normalizer import dedupe_signals
from .schemas import EntityResult, RuleResult, Signal, URLReputationResult
from .sender_trust import SenderTrustAnalyzer


class RuleEngine:
    def __init__(self) -> None:
        self.intent_detector = IntentDetector()
        self.context_detector = ContextDetector()
        self.sender_trust = SenderTrustAnalyzer()

    def evaluate(self, normalized: str, entities: EntityResult, entity_signals: list[Signal], url_result: URLReputationResult) -> RuleResult:
        intents = self.intent_detector.detect(normalized, entities)
        signals: list[Signal] = []
        signals.extend(entity_signals)
        signals.extend(self.context_detector.apply(intents, entities))

        if intents.otp_request:
            signals.append(Signal("requests_otp_code", "danger", 90, "الرسالة تطلب إرسال أو إدخال رمز تحقق، وهذا مؤشر تصيّد قوي.", intents.evidence.get("sensitive_request", "")))
        if intents.password_request:
            signals.append(Signal("requests_password_or_pin", "danger", 94, "الرسالة تطلب كلمة مرور أو رقما سريا.", intents.evidence.get("sensitive_request", "")))
        if intents.card_data_request:
            signals.append(Signal("requests_card_or_cvv", "danger", 96, "الرسالة تطلب بيانات بطاقة أو CVV أو بيانات بنكية.", intents.evidence.get("sensitive_request", "")))
        if intents.credential_request and not (intents.otp_request or intents.password_request or intents.card_data_request):
            signals.append(Signal("requests_sensitive_data", "danger", 88, "الرسالة تطلب بيانات حساسة أو معلومات حساب.", intents.evidence.get("sensitive_request", "")))
        financial_sensitive = bool(entities.entities & {"bank", "card", "cvv", "iban", "money_transaction"})
        if intents.url_account_action and intents.credential_request:
            signals.append(Signal("url_credential_request", "danger", 95, "تجمع الرسالة بين رابط أو إجراء دخول وطلب بيانات حساسة.", "url+credentials"))
        if entities.has_link_surface and intents.has("account_update") and intents.threat_urgency:
            signals.append(Signal("threat_url_account", "danger", 92, "تجمع الرسالة بين استعجال أو تهديد وتحديث حساب عبر رابط أو ضغط.", "url+urgency+account"))
        elif entities.has_link_surface and intents.threat_urgency and entities.has_bank_or_account:
            signals.append(Signal("threat_url_account", "danger", 90, "تجمع الرسالة بين استعجال أو تهديد وإجراء على الحساب عبر رابط أو ضغط.", "url+urgency+account"))
        elif entities.has_link_surface and intents.has("account_update") and financial_sensitive:
            signals.append(Signal("url_account_update", "danger", 86, "تطلب الرسالة تحديث أو تفعيل حساب مالي عبر رابط أو ضغط.", "url+account_update"))
        elif entities.has_link_surface and intents.has("account_update"):
            signals.append(Signal("account_update_link", "suspicious", 62, "تطلب الرسالة إجراء تحديث حساب عبر رابط أو ضغط دون دليل كاف على أنها رسمية.", "url+account_update"))
        elif entities.has_link_surface and entities.has_bank_or_account:
            signals.append(Signal("financial_link_action", "suspicious", 60, "تجمع الرسالة بين سياق مالي ورابط أو طلب ضغط.", "url+financial"))
        if intents.has("ambiguous_financial_notice"):
            signals.append(Signal("ambiguous_financial_notice", "suspicious", 48, "الرسالة تتعلق بحساب أو نشاط مالي بصياغة غير حاسمة، فتحتاج تحقق من المصدر.", "financial_notice"))
        if intents.threat_urgency and entities.has_bank_or_account and not intents.dangerous_text_request:
            signals.append(Signal("urgent_account_language", "suspicious", 58, "تستخدم الرسالة استعجالا أو تهديدا في سياق حساب أو بنك.", "urgency"))
        if intents.threat_urgency and (intents.has("account_login") or "password" in entities.entities or "pin" in entities.entities):
            weight = 90 if ("password" in entities.entities or "pin" in entities.entities) else 78
            signals.append(Signal("threat_login_account", "danger", weight, "تجمع الرسالة بين تهديد للحساب وطلب دخول أو كلمة مرور.", "threat+login"))
        if url_result.verdict == "malicious":
            signals.append(Signal("malicious_url_reputation", "danger", 98, "مزود سمعة روابط أشار إلى أن الرابط خبيث أو تصيدي.", url_result.findings[0].domain if url_result.findings else ""))
        signals.extend(url_result.signals)
        signals.extend(self.sender_trust.evaluate(entities, intents))
        return RuleResult(intents=intents, signals=dedupe_signals(signals))
