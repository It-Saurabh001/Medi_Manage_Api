import smtplib
import ssl
from email.mime.text import MIMEText
from app.integrations.email.base import EmailSender

class EmailDeliveryError(Exception):
    """Raised when production email delivery fails."""
    pass

class SmtpSender(EmailSender):
    """Production SMTP email sender supporting STARTTLS and authentication."""

    def __init__(self, config=None):
        config = config or {}
        self.host = config.get("SMTP_HOST")
        self.port = int(config.get("SMTP_PORT", 587))
        self.user = config.get("SMTP_USER")
        self.password = config.get("SMTP_PASS")
        self.use_tls = config.get("SMTP_USE_TLS", True)
        self.default_sender = config.get("MAIL_DEFAULT_SENDER")

    def send(self, to: str, subject: str, body: str) -> bool:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.default_sender
        msg["To"] = to

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls(context=context)
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            # Never log the OTP or email body in production
            raise EmailDeliveryError(f"Production email delivery failed for recipient: {type(e).__name__}")
