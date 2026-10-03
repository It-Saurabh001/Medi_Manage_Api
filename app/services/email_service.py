import random, smtplib, ssl
from email.mime.text import MIMEText

def generate_otp():
    return str(random.randint(100000, 999999))  # 6-digit OTP

# for fake email so that otp receive on local host 
def send_email(to_email, otp):
    """Simple send using SMTP to a debug server. Returns True if sent, False otherwise."""
    smtp_server = "localhost"
    smtp_port = 1025

    message = f"""From: test@example.com
To: {to_email}
Subject: Your OTP

Your OTP is: {otp}"""

    try:
        # Use a short-lived connection to a local debug SMTP server.
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
            server.sendmail("test@example.com", to_email, message)
        print(f"OTP sent to {to_email}: {otp}")  # also print for testing
        return True
    except (smtplib.SMTPException, OSError) as e:
        # Connection refused or other SMTP error (e.g. WinError 10061)
        print(f"Failed to send OTP to {to_email}: {e}")
        # For debugging/development, still print OTP so the developer can copy it.
        print(f"DEBUG OTP for {to_email}: {otp}")
        return False


# for real email 

def send_otp_email(to_email, otp):
    smtp_server = "localhost"              #"smtp.example.com"
    smtp_port = 1025 # debug server port        #587
    # smtp_user = "youremail@example.com"
    # smtp_pass = "yourpassword"

    subject = "Your Admin Login OTP"
    body = f"Your OTP for admin login is: {otp}. It will expire in 5 minutes."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] =  "test@example.com"             #smtp_user
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
            # server.starttls()
            # server.login(smtp_user, smtp_pass)        # these commented lines for real gmail to sent otp 
            server.send_message(msg)
        print(f"OTP sent to {to_email}: {otp} (Check your debug SMTP server output)")  # also print for testing
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"Failed to send OTP (send_otp_email) to {to_email}: {e}")
        print(f"DEBUG OTP for {to_email}: {otp}")
        return False