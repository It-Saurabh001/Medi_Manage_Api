import os
import random
from flask import current_app, has_app_context
from app.extensions import get_current_email_sender

def generate_otp() -> str:
    """Generate a 6-digit numeric OTP string."""
    return str(random.randint(100000, 999999))

def send_otp_email(to_email: str, otp: str) -> bool:
    """Dispatch OTP email using the configured email integration provider."""
    subject = "Your Login Verification OTP"
    body = f"Your OTP for login verification is: {otp}. It will expire in 5 minutes."

    if has_app_context():
        sender = get_current_email_sender()
        return sender.send(to=to_email, subject=subject, body=body)
    else:
        # Fallback for standalone script/debug invocation
        from app.integrations.email.dev.smtp_debug_sender import SmtpDebugSender
        sender = SmtpDebugSender()
        return sender.send(to=to_email, subject=subject, body=body)

def send_email(to_email: str, otp: str) -> bool:
    """Backward compatibility alias for send_otp_email."""
    return send_otp_email(to_email, otp)