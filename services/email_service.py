# services/email_service.py

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


EMAIL_MODE = os.getenv("EMAIL_MODE", "console").lower()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME or "no-reply@xapity.app")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Xapity")


def send_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> None:
    """
    Sends an email.

    Modes:
    - EMAIL_MODE=console: prints email content in terminal.
    - EMAIL_MODE=smtp: sends email using SMTP settings.
    """
    if EMAIL_MODE == "console":
        print("\n" + "=" * 72)
        print("[XAPITY EMAIL - CONSOLE MODE]")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print("-" * 72)
        print(body_text)

        if body_html:
            print("-" * 72)
            print("[HTML]")
            print(body_html)

        print("=" * 72 + "\n")
        return

    if EMAIL_MODE != "smtp":
        raise RuntimeError(f"Unsupported EMAIL_MODE: {EMAIL_MODE}")

    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        raise RuntimeError("SMTP configuration is incomplete.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = to_email

    message.set_content(body_text)

    if body_html:
        message.add_alternative(body_html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)


def send_registration_verification_email(
    *,
    to_email: str,
    code: str,
    expires_minutes: int,
) -> None:
    """
    Sends the registration verification code to the user's email.
    """
    subject = "Verifica tu correo en Xapity"

    body_text = f"""
Hola,

Gracias por registrarte en Xapity.

Tu código de verificación es:

{code}

Este código expira en {expires_minutes} minutos.

Si tú no solicitaste este registro, puedes ignorar este correo.

Equipo Xapity
""".strip()

    body_html = f"""
<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #111827;">
    <h2>Verifica tu correo en Xapity</h2>

    <p>Hola,</p>

    <p>Gracias por registrarte en Xapity.</p>

    <p>Tu código de verificación es:</p>

    <p style="font-size: 28px; font-weight: bold; letter-spacing: 4px;">
      {code}
    </p>

    <p>Este código expira en <strong>{expires_minutes} minutos</strong>.</p>

    <p>Si tú no solicitaste este registro, puedes ignorar este correo.</p>

    <p>Equipo Xapity</p>
  </body>
</html>
""".strip()

    send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )

def send_password_reset_email(
    *,
    to_email: str,
    code: str,
    expires_minutes: int,
) -> None:
    """
    Sends the password reset code to the user's email.
    """
    subject = "Recupera tu contraseña en Xapity"

    body_text = f"""
Hola,

Recibimos una solicitud para recuperar tu contraseña en Xapity.

Tu código de recuperación es:

{code}

Este código expira en {expires_minutes} minutos.

Si tú no solicitaste este cambio, puedes ignorar este correo.

Equipo Xapity
""".strip()

    body_html = f"""
<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #111827;">
    <h2>Recupera tu contraseña en Xapity</h2>

    <p>Hola,</p>

    <p>Recibimos una solicitud para recuperar tu contraseña en Xapity.</p>

    <p>Tu código de recuperación es:</p>

    <p style="font-size: 28px; font-weight: bold; letter-spacing: 4px;">
      {code}
    </p>

    <p>Este código expira en <strong>{expires_minutes} minutos</strong>.</p>

    <p>Si tú no solicitaste este cambio, puedes ignorar este correo.</p>

    <p>Equipo Xapity</p>
  </body>
</html>
""".strip()

    send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )

def send_invitation_email(
    *,
    to_email: str,
    invited_by_name: str,
    organization_name: str,
    invitation_url: str,
    expires_hours: int,
) -> None:
    """
    Sends an invitation email to join Xapity.
    """
    subject = f"Invitación a Xapity - {organization_name}"

    body_text = f"""
Hola,

{invited_by_name} te ha invitado a unirte a Xapity para la organización {organization_name}.

Para aceptar la invitación y crear tu contraseña, ingresa al siguiente enlace:

{invitation_url}

Este enlace expira en {expires_hours} horas.

Si no esperabas esta invitación, puedes ignorar este correo.

Equipo Xapity
""".strip()

    body_html = f"""
<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #111827;">
    <h2>Invitación a Xapity</h2>

    <p>Hola,</p>

    <p>
      <strong>{invited_by_name}</strong> te ha invitado a unirte a Xapity
      para la organización <strong>{organization_name}</strong>.
    </p>

    <p>Para aceptar la invitación y crear tu contraseña, haz clic en el siguiente enlace:</p>

    <p>
      <a href="{invitation_url}"
         style="display: inline-block; padding: 10px 16px; background: #111827; color: #ffffff; text-decoration: none; border-radius: 6px;">
        Aceptar invitación
      </a>
    </p>

    <p>O copia y pega este enlace en tu navegador:</p>

    <p style="word-break: break-all;">{invitation_url}</p>

    <p>Este enlace expira en <strong>{expires_hours} horas</strong>.</p>

    <p>Si no esperabas esta invitación, puedes ignorar este correo.</p>

    <p>Equipo Xapity</p>
  </body>
</html>
""".strip()

    send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )