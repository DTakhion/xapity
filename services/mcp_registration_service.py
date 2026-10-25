# services/mcp_registration_service.py
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from services.auth_service import hash_password, hash_registration_code, verify_registration_code
from services.email_service import send_registration_verification_email
from services.mcp_auth_service import validate_mcp_provisioning_token
from db.mongo_mcp_registration import (
    get_mcp_user_by_email, save_mcp_pending_registration,
    get_mcp_pending_registration, increment_mcp_pending_attempts,
    finalize_mcp_registration,
)

MCP_CODE_EXPIRE_MINUTES = 15
MCP_MAX_ATTEMPTS = 5


def start_mcp_registration(payload):
    email = str(payload.email).strip().lower()
    token_hash = validate_mcp_provisioning_token(payload.provisioningToken, email)
    if get_mcp_user_by_email(email):
        raise ValueError('El correo ya está registrado en MCP')

    code = f'{secrets.randbelow(1_000_000):06d}'
    now = datetime.now(timezone.utc)
    save_mcp_pending_registration({
        'email': email,
        'passwordHash': hash_password(payload.password),
        'provisioningTokenHash': token_hash,
        'codeHash': hash_registration_code(code),
        'attempts': 0,
        'usedAt': None,
        'createdAt': now,
        'expiresAt': now + timedelta(minutes=MCP_CODE_EXPIRE_MINUTES),
    })
    send_registration_verification_email(
        to_email=email, code=code, expires_minutes=MCP_CODE_EXPIRE_MINUTES
    )
    return {'message': 'Si la solicitud es válida, recibirás un código de verificación.'}


def verify_mcp_registration(payload):
    email = str(payload.email).strip().lower()
    pending = get_mcp_pending_registration(email)
    now = datetime.now(timezone.utc)
    if not pending or pending.get('usedAt') is not None:
        raise ValueError('Código inválido o expirado')
    if pending['expiresAt'].replace(tzinfo=timezone.utc) <= now:
        raise ValueError('Código inválido o expirado')
    attempts = pending.get('attempts', 0)
    if attempts >= MCP_MAX_ATTEMPTS:
        raise ValueError('Demasiados intentos')
    if not verify_registration_code(payload.code, pending['codeHash']):
        increment_mcp_pending_attempts(email, attempts)
        raise ValueError('Código inválido o expirado')

    user = {
        'userId': str(uuid.uuid4()), 'email': email,
        'passwordHash': pending['passwordHash'],
        'accountType': 'mcp', 'isActive': True, 'isDeleted': False,
        'allowedScopes': ['luca:sales:read'], 'createdAt': now, 'updatedAt': now,
    }
    finalize_mcp_registration(email, pending['codeHash'], user)
    return {'userId': user['userId'], 'email': email,
            'accountType': 'mcp', 'allowedScopes': user['allowedScopes']}
