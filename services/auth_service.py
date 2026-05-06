# services/auth_service.py

from __future__ import annotations

import os
import uuid
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
)

load_dotenv()

# ============================================================
# CONFIGURACIÓN
# ============================================================

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_ENV")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 8))
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

async def register_user(payload: AuthRegisterRequest) -> Dict[str, Any]:
    """
    Registra un usuario nuevo y crea una organización inicial.

    Regla MVP:
    - Cada signup crea un businessId propio.
    - El primer usuario normalmente será admin.
    """
    existing_user = get_user_by_email(payload.email)

    if existing_user:
        raise ValueError("El correo ya está registrado")

    now = datetime.now(timezone.utc)

    user_doc = {
        "userId": str(uuid.uuid4()),
        "businessId": str(uuid.uuid4()),
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

    # Nunca devolver passwordHash al frontend.
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