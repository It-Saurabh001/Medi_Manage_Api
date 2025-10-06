import random, smtplib, ssl
import smtplib
from email.mime.text import MIMEText

def generate_otp():
    return str(random.randint(100000, 999999))  # 6-digit OTP

# for fake email so that otp receive on local host 
def send_email(to_email, otp):
    smtp_server = "localhost"
    smtp_port = 1025

    message = f"""\
From: test@example.com
To: {to_email}
Subject: Your OTP

Your OTP is: {otp}"""

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.sendmail("test@example.com", to_email, message)
        print(f"OTP sent to {to_email}: {otp}")  # also print for testing


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

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        # server.starttls()
        # server.login(smtp_user, smtp_pass)        # these commented lines for real gmail to sent otp 
        # server.send_message(msg)
        server.send_message(msg)
        print(f"OTP sent to {to_email}: {otp}(Chekc your debug SMTP server output)")  # also print for testing)