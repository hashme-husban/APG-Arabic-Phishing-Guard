from __future__ import annotations

import re

from .schemas import EntityResult, IntentResult, Signal


class SenderTrustAnalyzer:
    PACKAGE_NAMES = {"com.whatsapp", "com.samsung.android.messaging", "com.google.android.gm", "com.google.android.apps.messaging", "org.telegram.messenger"}

    def evaluate(self, entities: EntityResult, intents: IntentResult) -> list[Signal]:
        sender_value = (entities.sender or entities.sender_name or "").strip()
        package_value = (entities.package_name or entities.source_app or "").strip()
        trust = (entities.sender_trust or "unknown").strip().lower()
        signals: list[Signal] = []
        sensitive_request = intents.dangerous_text_request

        if entities.is_known_contact is True or trust in {"known", "trusted_contact", "contact"}:
            weight = 0 if sensitive_request or entities.has_sensitive_entity else -8
            signals.append(Signal("known_contact_sender", "context", weight, "المرسل ضمن جهات الاتصال، وهذا يخفض الخطر فقط للرسائل العادية غير الحساسة.", sender_value))
        elif entities.is_known_contact is False or trust in {"unknown", "stranger", "unknown_contact"}:
            if entities.has_bank_or_account and (intents.has("ambiguous_financial_notice") or intents.has("account_update") or entities.has_link_surface):
                signals.append(Signal("unknown_sender_financial_context", "suspicious", 6, "المرسل غير مؤكد مع سياق مالي، لذلك يزيد الحذر قليلا.", sender_value))

        if not sender_value and not package_value:
            signals.append(Signal("unknown_sender", "context", 0, "هوية المرسل غير متاحة."))
        elif sender_value in self.PACKAGE_NAMES or sender_value == package_value or self._looks_like_package(sender_value):
            signals.append(Signal("unknown_sender", "context", 0, "هوية المرسل غير مؤكدة.", sender_value))

        if entities.has_bank_or_account and sensitive_request:
            signals.append(Signal("sender_claims_official_sensitive_request", "context", 0, "اسم المرسل أو ادعاء الجهة الرسمية ليس دليل أمان لأن معرف المرسل قابل للانتحال.", sender_value))
        return signals

    @staticmethod
    def _looks_like_package(value: str) -> bool:
        return bool(re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", value.strip()))
