import smtplib
from email.mime.text import MIMEText
from app.integrations.email.base import EmailSender

class SmtpDebugSender(EmailSender):
    """Development email sender targeting local debug SMTP server (e.g. aiosmtpd)."""

    def __init__(self, config=None):
        config = config or {}
        self.host = config.get("SMTP_HOST", "localhost")
        self.port = int(config.get("SMTP_PORT", 1025))
        self.default_sender = config.get("MAIL_DEFAULT_SENDER", "noreply@example.com")

    def send(self, to: str, subject: str, body: str) -> bool:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.default_sender
        msg["To"] = to

        try:
            with smtplib.SMTP(self.host, self.port, timeout=5) as server:
                server.send_message(msg)
            return True
        except (smtplib.SMTPException, OSError):
            return False
