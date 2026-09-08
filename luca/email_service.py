# luca/email_service.py

"""
Servicio genérico de envío de correos para Xapity.

Responsabilidades:

- leer configuración SMTP desde variables de entorno;
- construir mensajes MIME;
- soportar cuerpo de texto y HTML;
- soportar adjuntos en memoria;
- autenticar mediante SMTP + STARTTLS;
- enviar correos.

Este módulo NO:

- consulta MongoDB;
- resuelve usuarios;
- genera reportes;
- modifica estados de acciones.
"""

from __future__ import annotations

import os
import smtplib

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable

from dotenv import load_dotenv


load_dotenv()


# ==================================================
# MODELOS
# ==================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EmailAttachment:
    """
    Archivo adjunto enviado completamente en memoria.
    """

    filename: str
    content_type: str
    content: bytes


@dataclass(
    frozen=True,
    slots=True,
)
class EmailSendResult:
    """
    Resultado estructurado de un envío SMTP.
    """

    success: bool
    sender_email: str
    recipient_email: str
    subject: str
    attachments_count: int


# ==================================================
# CONFIGURACIÓN
# ==================================================


def _require_env(
    name: str,
) -> str:
    value = os.getenv(
        name
    )

    if value is None:
        raise RuntimeError(
            f"Falta la variable de entorno {name}."
        )

    normalized = value.strip()

    if not normalized:
        raise RuntimeError(
            f"La variable de entorno {name} está vacía."
        )

    return normalized


def _load_smtp_config() -> dict[str, object]:
    """
    Obtiene la configuración SMTP desde variables
    de entorno.
    """

    email_mode = _require_env(
        "EMAIL_MODE"
    ).lower()

    if email_mode != "smtp":
        raise RuntimeError(
            "EMAIL_MODE debe ser 'smtp' para utilizar "
            "este servicio."
        )

    host = _require_env(
        "SMTP_HOST"
    )

    port_raw = _require_env(
        "SMTP_PORT"
    )

    try:
        port = int(
            port_raw
        )
    except ValueError as error:
        raise RuntimeError(
            "SMTP_PORT debe ser un entero."
        ) from error

    username = _require_env(
        "SMTP_USERNAME"
    )

    password = _require_env(
        "SMTP_PASSWORD"
    )

    from_email = _require_env(
        "SMTP_FROM_EMAIL"
    )

    from_name = (
        os.getenv(
            "SMTP_FROM_NAME",
            "Xapity",
        ).strip()
        or "Xapity"
    )

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from_email": from_email,
        "from_name": from_name,
    }


# ==================================================
# VALIDACIONES
# ==================================================


def _validate_email_address(
    *,
    value: str,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} debe ser un string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} no puede estar vacío."
        )

    if (
        "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
        raise ValueError(
            f"{field_name} no parece ser un correo válido."
        )

    return normalized


def _validate_subject(
    subject: str,
) -> str:
    if not isinstance(
        subject,
        str,
    ):
        raise TypeError(
            "subject debe ser un string."
        )

    normalized = subject.strip()

    if not normalized:
        raise ValueError(
            "subject no puede estar vacío."
        )

    return normalized


# ==================================================
# CONSTRUCCIÓN MIME
# ==================================================


def _add_attachment(
    *,
    message: EmailMessage,
    attachment: EmailAttachment,
) -> None:
    if not isinstance(
        attachment,
        EmailAttachment,
    ):
        raise TypeError(
            "Cada attachment debe ser una instancia "
            "de EmailAttachment."
        )

    if not attachment.filename.strip():
        raise ValueError(
            "attachment.filename no puede estar vacío."
        )

    if not isinstance(
        attachment.content,
        bytes,
    ):
        raise TypeError(
            "attachment.content debe ser bytes."
        )

    if "/" not in attachment.content_type:
        raise ValueError(
            "attachment.content_type debe tener "
            "formato tipo/subtipo."
        )

    maintype, subtype = (
        attachment.content_type.split(
            "/",
            1,
        )
    )

    message.add_attachment(
        attachment.content,
        maintype=maintype,
        subtype=subtype,
        filename=attachment.filename,
    )


def build_email_message(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    attachments: Iterable[
        EmailAttachment
    ] | None = None,
) -> EmailMessage:
    """
    Construye un EmailMessage listo para ser enviado.
    """

    config = (
        _load_smtp_config()
    )

    recipient_email = (
        _validate_email_address(
            value=to_email,
            field_name="to_email",
        )
    )

    resolved_subject = (
        _validate_subject(
            subject
        )
    )

    if not isinstance(
        text_body,
        str,
    ):
        raise TypeError(
            "text_body debe ser un string."
        )

    if (
        html_body is not None
        and not isinstance(
            html_body,
            str,
        )
    ):
        raise TypeError(
            "html_body debe ser string o None."
        )

    message = EmailMessage()

    message["From"] = formataddr(
        (
            str(
                config[
                    "from_name"
                ]
            ),
            str(
                config[
                    "from_email"
                ]
            ),
        )
    )

    message["To"] = (
        recipient_email
    )

    message["Subject"] = (
        resolved_subject
    )

    message.set_content(
        text_body
    )

    if html_body:
        message.add_alternative(
            html_body,
            subtype="html",
        )

    if attachments:
        for attachment in attachments:
            _add_attachment(
                message=message,
                attachment=attachment,
            )

    return message


# ==================================================
# ENVÍO SMTP
# ==================================================


def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    attachments: Iterable[
        EmailAttachment
    ] | None = None,
) -> EmailSendResult:
    """
    Envía un correo mediante SMTP + STARTTLS.

    Lanza excepción si el transporte falla.
    """

    config = (
        _load_smtp_config()
    )

    resolved_attachments = list(
        attachments
        or []
    )

    message = (
        build_email_message(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            attachments=(
                resolved_attachments
            ),
        )
    )

    with smtplib.SMTP(
        str(
            config[
                "host"
            ]
        ),
        int(
            config[
                "port"
            ]
        ),
        timeout=30,
    ) as smtp:
        smtp.ehlo()

        smtp.starttls()

        smtp.ehlo()

        smtp.login(
            str(
                config[
                    "username"
                ]
            ),
            str(
                config[
                    "password"
                ]
            ),
        )

        smtp.send_message(
            message
        )

    return EmailSendResult(
        success=True,
        sender_email=str(
            config[
                "from_email"
            ]
        ),
        recipient_email=(
            _validate_email_address(
                value=to_email,
                field_name="to_email",
            )
        ),
        subject=(
            _validate_subject(
                subject
            )
        ),
        attachments_count=len(
            resolved_attachments
        ),
    )