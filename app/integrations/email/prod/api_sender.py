import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from app.integrations.email.base import EmailSender
from app.integrations.email.prod.smtp_sender import EmailDeliveryError

logger = logging.getLogger(__name__)

_ENDPOINTS = {
    "brevo": "https://api.brevo.com/v3/smtp/email",
    "resend": "https://api.resend.com/emails",
}


class ApiEmailSender(EmailSender):
    """HTTPS email API sender (Brevo or Resend). Used where outbound SMTP ports are blocked (Render)."""

    def __init__(self, config=None):
        config = config or {}
        self.provider = (config.get("EMAIL_API_PROVIDER") or "brevo").lower()
        if self.provider not in _ENDPOINTS:
            raise ValueError(f"Unknown EMAIL_API_PROVIDER: {self.provider}")
        self.api_key = config.get("EMAIL_API_KEY")
        self.sender_name, self.sender_email = parseaddr(config.get("MAIL_DEFAULT_SENDER") or "")

    def _request(self, to, subject, body):
        if self.provider == "brevo":
            payload = {"sender": {"email": self.sender_email, "name": self.sender_name or self.sender_email},
                       "to": [{"email": to}], "subject": subject, "textContent": body}
            headers = {"api-key": self.api_key}
        else:
            sender = f"{self.sender_name} <{self.sender_email}>" if self.sender_name else self.sender_email
            payload = {"from": sender, "to": [to], "subject": subject, "text": body}
            headers = {"Authorization": f"Bearer {self.api_key}"}
        headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        return urllib.request.Request(_ENDPOINTS[self.provider], data=json.dumps(payload).encode(),
                                      headers=headers, method="POST")

    def send(self, to: str, subject: str, body: str) -> bool:
        if not self.api_key or not self.sender_email:
            raise EmailDeliveryError("EMAIL_API_KEY or MAIL_DEFAULT_SENDER is not configured")
        try:
            with urllib.request.urlopen(self._request(to, subject, body), timeout=15) as resp:
                status, raw = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            logger.error("Email API %s rejected message: HTTP %s %s", self.provider, exc.code, detail)
            raise EmailDeliveryError(f"{self.provider} HTTP {exc.code}")
        except Exception as exc:
            logger.error("Email API %s unreachable: %s", self.provider, type(exc).__name__)
            raise EmailDeliveryError(f"{self.provider} unreachable: {type(exc).__name__}")
        try:
            data = json.loads(raw or "{}")
        except ValueError:
            data = {}
        message_id = data.get("messageId") or data.get("id")
        logger.warning("Email API %s accepted message: HTTP %s message_id=%s", self.provider, status, message_id)
        return 200 <= status < 300
