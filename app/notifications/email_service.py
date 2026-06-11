import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def send_email_notification(to_email: str, ad_title: str, ad_link: str, query: str):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM") or username

    if not host or not username or not password:
        print("[EMAIL] SMTP not configured. Skipping email.")
        return False

    message = EmailMessage()
    message["Subject"] = f"SmartAdds - New ad for '{query}'"
    message["From"] = sender
    message["To"] = to_email

    message.set_content(f"""
Здраво,

SmartAdds пронајде нов оглас што одговара на твоето зачувано пребарување.

Пребарување:
{query}

Оглас:
{ad_title}

Линк:
{ad_link}

Поздрав,
SmartAdds
""")

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)

        print(f"[EMAIL] Sent to {to_email}")
        return True

    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False