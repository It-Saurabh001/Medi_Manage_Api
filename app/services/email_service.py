from flask import has_app_context

from app.extensions import get_current_email_sender
from app.integrations.email.factory import get_email_sender

_SUBJECTS = {
    "login": "Your login verification code",
    "reset": "Your password reset code",
}


def send_otp_email(to_email: str, otp: str, purpose: str = "login") -> bool:
    """Send an OTP email. Returns True on success; never logs the OTP."""
    subject = _SUBJECTS.get(purpose, "Your verification code")
    body = (f"Your verification code is: {otp}. It expires shortly. "
            "If you did not request this, you can ignore this email.")
    sender = get_current_email_sender() if has_app_context() else get_email_sender(
        {"EMAIL_PROVIDER": "dev", "DEBUG": True})
    return bool(sender.send(to=to_email, subject=subject, body=body))
