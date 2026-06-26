import smtplib
from email.mime.text import MIMEText
import os
import random
import requests
from utils.db_helpers import admin_email


def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def send_email_otp(receiver_email: str, otp: str):
    sender_email = admin_email()
    sender_password = os.getenv("GMAIL_APP_PASSWORD")

    body = f"""\
Hello,

You're receiving this email because a library registration is currently being processed for your email address.

Your One-Time Password (OTP) for verification is:

    {otp}

This OTP is valid for 5 minutes. Please enter it on the library registration screen to confirm your identity and complete the sign-up process.

If you did not request this, you can safely ignore this email — no account will be created without OTP verification.

Regards,
Library Management System
"""

    msg = MIMEText(body)
    msg["Subject"] = "Your Library Registration OTP"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())