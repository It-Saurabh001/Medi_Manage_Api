import os
import random, smtplib, ssl
from email.mime.text import MIMEText

def generate_otp():
    return str(random.randint(100000, 999999))  # 6-digit OTP

# for fake email so that otp receive on local host 
def send_email(to_email, otp):
    """Simple send using SMTP to configured server."""
    smtp_server = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    from_email = os.getenv("MAIL_DEFAULT_SENDER", "noreply@example.com")

    message = f"""From: {from_email}
To: {to_email}
Subject: Your OTP

Your OTP is: {otp}"""

    try:
        # Use a short-lived connection to a local debug SMTP server.
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
            server.sendmail(from_email, to_email, message)
        return True
    except (smtplib.SMTPException, OSError):
        return False


# for real email 

def send_otp_email(to_email, otp):
    smtp_server = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    from_email = os.getenv("MAIL_DEFAULT_SENDER", "noreply@example.com")

    subject = "Your Admin Login OTP"
    body = f"Your OTP for admin login is: {otp}. It will expire in 5 minutes."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        return False