# services/auth_service.py

from __future__ import annotations

import os
import uuid
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import jwt

from schemas.auth import AuthRegisterRequest, AuthLoginRequest

from db.mongo_persistence import (
    insert_user,
    get_user_by_email,
    get_user_by_user_id,
    upsert_pending_registration,
    get_pending_registration_by_email,
    mark_pending_registration_used,
    increment_pending_registration_attempts,
)

from services.email_service import send_registration_verification_email

load_dotenv()

# ============================================================
# CONFIGURACIÓN
# ============================================================

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_ENV")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 8))
)

REGISTRATION_CODE_EXPIRE_MINUTES = int(
    os.getenv("REGISTRATION_CODE_EXPIRE_MINUTES", "15")
)

REGISTRATION_MAX_ATTEMPTS = int(
    os.getenv("REGISTRATION_MAX_ATTEMPTS", "5")
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# HELPERS PASSWORD
# ============================================================

def hash_password(password: str) -> str:
    """
    Genera un hash seguro para la contraseña.
    Nunca se guarda la contraseña original.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compara una contraseña ingresada contra el hash almacenado.
    """
    return pwd_context.verify(plain_password, hashed_password)

# ============================================================
# HELPERS REGISTRATION CODE
# ============================================================

def generate_registration_code() -> str:
    """
    Generates a 6-digit numeric registration verification code.
    """
    return f"{random.randint(0, 999999):06d}"


def hash_registration_code(code: str) -> str:
    """
    Hashes the verification code before storing it.
    """
    return pwd_context.hash(code)


def verify_registration_code(plain_code: str, hashed_code: str) -> bool:
    """
    Verifies a plain verification code against the stored hash.
    """
    return pwd_context.verify(plain_code, hashed_code)


# ============================================================
# JWT
# ============================================================

def create_access_token(data: dict) -> str:
    """
    Genera un JWT con expiración.
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ============================================================
# REGISTER
# ============================================================

# async def register_user(payload: AuthRegisterRequest) -> Dict[str, Any]:
#     """
#     Registra un usuario nuevo y crea una organización inicial.

#     Regla MVP:
#     - Cada signup crea un businessId propio.
#     - El primer usuario normalmente será admin.
#     """
#     existing_user = get_user_by_email(payload.email)

#     if existing_user:
#         raise ValueError("El correo ya está registrado")

#     now = datetime.now(timezone.utc)

#     user_doc = {
#         "userId": str(uuid.uuid4()),
#         "businessId": str(uuid.uuid4()),
#         "name": payload.name,
#         "email": payload.email,
#         "passwordHash": hash_password(payload.password),
#         "phone": payload.phone,
#         "organizationName": payload.organizationName,
#         "role": payload.role,
#         "authProvider": "local",
#         "isEmailVerified": False,
#         "isActive": True,
#         "isDeleted": False,
#         "createdAt": now,
#         "updatedAt": now,
#     }

#     inserted_user = insert_user(user_doc)

#     # Nunca devolver passwordHash al frontend.
#     inserted_user.pop("passwordHash", None)

#     return inserted_user

async def start_user_registration(
    payload: AuthRegisterRequest,
    business_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Starts a pending user registration.

    This does NOT create the final user yet.
    It stores a pending registration and sends a verification code by email.
    """
    existing_user = get_user_by_email(payload.email)

    if existing_user:
        raise ValueError("El correo ya está registrado")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=REGISTRATION_CODE_EXPIRE_MINUTES)

    code = generate_registration_code()

    pending_doc = {
        "pendingRegistrationId": str(uuid.uuid4()),
        "businessId": business_id or str(uuid.uuid4()),
        "name": payload.name,
        "email": str(payload.email).strip().lower(),
        "passwordHash": hash_password(payload.password),
        "phone": payload.phone,
        "organizationName": payload.organizationName,
        "role": payload.role,
        "verificationCodeHash": hash_registration_code(code),
        "expiresAt": expires_at,
        "attempts": 0,
        "usedAt": None,
        "createdAt": now,
        "updatedAt": now,
    }

    upsert_pending_registration(pending_doc)

    send_registration_verification_email(
        to_email=pending_doc["email"],
        code=code,
        expires_minutes=REGISTRATION_CODE_EXPIRE_MINUTES,
    )

    return {
        "ok": True,
        "message": "Código de verificación enviado al correo.",
        "email": pending_doc["email"],
    }


async def verify_user_registration(
    email: str,
    code: str,
) -> Dict[str, Any]:
    """
    Verifies a pending registration code and creates the final user.
    """
    normalized_email = str(email).strip().lower()

    existing_user = get_user_by_email(normalized_email)

    if existing_user:
        raise ValueError("El correo ya está registrado")

    pending = get_pending_registration_by_email(normalized_email)

    if not pending:
        raise ValueError("No existe una solicitud pendiente para este correo")

    now = datetime.now(timezone.utc)

    expires_at = pending.get("expiresAt")
    
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at and expires_at < now:
        raise ValueError("El código de verificación expiró")

    attempts = int(pending.get("attempts") or 0)

    if attempts >= REGISTRATION_MAX_ATTEMPTS:
        raise ValueError("Se superó el máximo de intentos de verificación")

    verification_code_hash = pending.get("verificationCodeHash")

    if not verification_code_hash:
        raise ValueError("Solicitud de verificación inválida")

    if not verify_registration_code(code, verification_code_hash):
        increment_pending_registration_attempts(normalized_email)
        raise ValueError("Código de verificación inválido")

    user_doc = {
        "userId": str(uuid.uuid4()),
        "businessId": pending["businessId"],
        "name": pending["name"],
        "email": pending["email"],
        "passwordHash": pending["passwordHash"],
        "phone": pending.get("phone"),
        "organizationName": pending["organizationName"],
        "role": pending["role"],
        "authProvider": "local",
        "isEmailVerified": True,
        "isActive": True,
        "isDeleted": False,
        "createdAt": now,
        "updatedAt": now,
    }

    inserted_user = insert_user(user_doc)
    mark_pending_registration_used(normalized_email)

    inserted_user.pop("passwordHash", None)

    return inserted_user

async def register_user(
    payload: AuthRegisterRequest,
    business_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Registra un usuario nuevo y crea una organización inicial.

    Regla MVP:
    - Si viene business_id desde el endpoint, se usa ese valor.
    - Si no viene, se crea un businessId propio.
    """
    existing_user = get_user_by_email(payload.email)

    if existing_user:
        raise ValueError("El correo ya está registrado")

    now = datetime.now(timezone.utc)

    user_doc = {
        "userId": str(uuid.uuid4()),
        "businessId": business_id or str(uuid.uuid4()),
        "name": payload.name,
        "email": payload.email,
        "passwordHash": hash_password(payload.password),
        "phone": payload.phone,
        "organizationName": payload.organizationName,
        "role": payload.role,
        "authProvider": "local",
        "isEmailVerified": False,
        "isActive": True,
        "isDeleted": False,
        "createdAt": now,
        "updatedAt": now,
    }

    inserted_user = insert_user(user_doc)
    inserted_user.pop("passwordHash", None)

    return inserted_user

# ============================================================
# LOGIN
# ============================================================

async def login_user(payload: AuthLoginRequest) -> Dict[str, Any]:
    """
    Login con email + password.
    """
    user = get_user_by_email(payload.email)

    if not user:
        raise ValueError("Credenciales inválidas")

    if not user.get("isActive", True):
        raise ValueError("Usuario inactivo")

    password_hash = user.get("passwordHash")

    if not password_hash:
        raise ValueError("Credenciales inválidas")

    if not verify_password(payload.password, password_hash):
        raise ValueError("Credenciales inválidas")

    token_data = {
        "sub": user["userId"],
        "userId": user["userId"],
        "businessId": user["businessId"],
        "email": user["email"],
        "role": user["role"],
    }

    access_token = create_access_token(token_data)

    user.pop("passwordHash", None)

    return {
        "accessToken": access_token,
        "tokenType": "bearer",
        "user": user,
    }


# ============================================================
# GET CURRENT USER
# ============================================================

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene un usuario por userId.
    """
    user = get_user_by_user_id(user_id)

    if not user:
        return None

    user.pop("passwordHash", None)

    return user