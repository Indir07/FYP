from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_email(*, to_email: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", username or "no-reply@cryptovolt.local").strip()
    use_tls = os.getenv("SMTP_USE_TLS", "1").strip() != "0"

    if not host or not from_email:
        raise RuntimeError("SMTP is not configured. Set SMTP_HOST/SMTP_FROM_EMAIL (and credentials).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=8) as server:
        if use_tls:
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(msg)

