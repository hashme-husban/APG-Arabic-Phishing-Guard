from __future__ import annotations

from .schemas import EntityResult, IntentResult, Signal


class ContextDetector:
    def apply(self, intents: IntentResult, entities: EntityResult) -> list[Signal]:
        signals: list[Signal] = []
        dangerous = intents.dangerous_text_request
        if intents.has("educational_awareness") and not dangerous:
            intents.safe_context = "educational_awareness"
            signals.append(Signal("security_awareness_message", "safe", 10, "الرسالة توعوية وتحذر من مشاركة البيانات الحساسة ولا تطلبها."))
        if intents.has("otp_delivery") and not dangerous and not entities.has_link_surface:
            intents.safe_context = intents.safe_context or "otp_delivery"
            signals.append(Signal("otp_informational_do_not_share", "safe", 12, "الرسالة تبدو رمز تحقق معلوماتيا مع تنبيه بعدم مشاركته."))
        if intents.has("bank_transaction") and not dangerous and not entities.has_link_surface and not intents.has("account_update"):
            intents.safe_context = intents.safe_context or "bank_transaction"
            signals.append(Signal("benign_bank_transaction", "safe", 12, "الرسالة تبدو إشعار عملية مالية ولا تطلب إجراء أو بيانات حساسة."))
        if "whatsapp" in entities.entities and intents.has("informational_notification") and not dangerous and not entities.has_link_surface:
            intents.safe_context = intents.safe_context or "whatsapp_status"
            signals.append(Signal("whatsapp_verification_status", "safe", 8, "الرسالة تبدو حالة تحقق من واتساب ولا تطلب مشاركة رمز أو فتح رابط."))
        return signals
