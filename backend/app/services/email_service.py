import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("apg.email")


class EmailService:
    """Transactional email delivery with a dev-safe fallback."""

    def send_verification_code(self, email: str, code: str) -> bool:
        settings = get_settings()
        if settings.email_provider == "smtp":
            return self._send_smtp_verification_code(email, code)

        if settings.is_production:
            logger.error("Email provider is not configured; verification email was not sent")
            return False

        logger.warning("DEV EMAIL VERIFICATION CODE for %s: %s", email, code)
        return True

    def _send_smtp_verification_code(self, email: str, code: str) -> bool:
        settings = get_settings()
        if not all(
            [
                settings.smtp_host,
                settings.smtp_port,
                settings.smtp_username,
                settings.smtp_password,
                settings.email_from,
            ]
        ):
            logger.error("SMTP email provider is missing required environment variables")
            return False

        message = EmailMessage()
        message["Subject"] = "رمز التحقق من APG"
        message["From"] = settings.email_from
        message["To"] = email
        message.set_content(
            "\n".join(
                [
                    f"رمز التحقق الخاص بك هو: {code}",
                    "ينتهي الرمز خلال 10 دقائق.",
                    "لا تشارك هذا الرمز مع أي شخص.",
                ]
            ),
            subtype="plain",
            charset="utf-8",
        )

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
            logger.info("Verification email sent to %s", email)
            return True
        except Exception as exc:
            logger.error(
                "Verification email delivery failed type=%s message=%s",
                type(exc).__name__,
                str(exc),
                exc_info=True,
            )
            return False
