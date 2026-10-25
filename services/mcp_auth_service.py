# services/mcp_auth_service.py
# ============================================================
# XAPITY LUCA MCP — USER PROVISIONING SERVICE
# ============================================================

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from db.mongo_persistence import get_user_by_email

from db.mongo_mcp_auth_persistence import (
    insert_mcp_provisioning_token,
    get_mcp_provisioning_token,
    MCP_PROVISIONING_PURPOSE,
)


MCP_PROVISIONING_EXPIRE_HOURS = int(
    os.getenv("MCP_PROVISIONING_EXPIRE_HOURS", "48")
)

MCP_ALLOWED_SCOPES = ["luca:sales:read"]


def hash_mcp_provisioning_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_mcp_provisioning_token(email: str) -> str:
    """
    Creates an invitation for an MCP user.

    Must only be called by a trusted provisioning process.
    Never expose through an unauthenticated endpoint.
    """
    normalized_email = str(email).strip().lower()

    if not normalized_email or "@" not in normalized_email:
        raise ValueError("Correo MCP inválido")

    if get_user_by_email(normalized_email):
        raise ValueError("El correo ya está registrado")

    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)

    token_document = {
        "provisioningId": str(uuid.uuid4()),
        "tokenHash": hash_mcp_provisioning_token(token),
        "email": normalized_email,
        "purpose": MCP_PROVISIONING_PURPOSE,
        "scopes": list(MCP_ALLOWED_SCOPES),
        "expiresAt": now + timedelta(
            hours=MCP_PROVISIONING_EXPIRE_HOURS
        ),
        "usedAt": None,
        "createdAt": now,
        "updatedAt": now,
    }

    insert_mcp_provisioning_token(token_document)

    return token


def validate_mcp_provisioning_token(
    token: str,
    email: str,
) -> str:
    """
    Validates an unused invitation without consuming it.
    Returns the token hash.
    """
    normalized_email = str(email).strip().lower()

    if not token:
        raise ValueError("Se requiere invitación MCP")

    token_hash = hash_mcp_provisioning_token(token)

    authorization = get_mcp_provisioning_token(
        token_hash,
        normalized_email,
    )

    if authorization is None:
        raise ValueError(
            "Invitación MCP inválida, utilizada o expirada"
        )

    if authorization.get("scopes") != MCP_ALLOWED_SCOPES:
        raise ValueError(
            "Permisos de invitación MCP inválidos"
        )

    return token_hash
