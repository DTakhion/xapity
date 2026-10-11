# services/visitor_auth_service.py

from __future__ import annotations

import os
import uuid

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

from schemas.visitor_auth import (
    VisitorRegisterStartRequest,
    VisitorRegisterVerifyRequest,
)

from db.mongo_persistence import (
    get_user_by_email,
    get_visitor_pending_registrations_collection,
    insert_user,
)

from services.auth_service import (
    hash_password,
    generate_registration_code,
    hash_registration_code,
    verify_registration_code,
)

from services.email_service import (
    send_registration_verification_email,
)


load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

VISITOR_CODE_EXPIRE_MINUTES = int(
    os.getenv("VISITOR_CODE_EXPIRE_MINUTES", "15")
)

VISITOR_MAX_ATTEMPTS = int(
    os.getenv("VISITOR_MAX_ATTEMPTS", "5")
)

VISITOR_RESEND_COOLDOWN_SECONDS = int(
    os.getenv("VISITOR_RESEND_COOLDOWN_SECONDS", "60")
)

class VisitorCooldownError(ValueError):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(
            f"Debes esperar {retry_after} segundos "
            "antes de solicitar otro código."
        )

# ============================================================
# PERSISTENCE HELPERS
# ============================================================

def get_pending_visitor(email: str):
    collection = get_visitor_pending_registrations_collection()

    return collection.find_one({
        "email": email,
        "usedAt": None,
    })


# def increment_visitor_attempts(
#     email: str,
#     pending_id,
# ) -> None:
#     collection = get_visitor_pending_registrations_collection()

#     collection.update_one(
#         {
#             "_id": pending_id,
#             "email": email,
#             "usedAt": None,
#             "attempts": {"$lt": VISITOR_MAX_ATTEMPTS},
#         },
#         {
#             "$inc": {"attempts": 1},
#             "$set": {
#                 "updatedAt": datetime.now(timezone.utc),
#             },
#         },
#     )

# ============================================================
# START VISITOR REGISTRATION
# ============================================================


# async def start_visitor_registration(
#     payload: VisitorRegisterStartRequest,
# ) -> Dict[str, Any]:

#     normalized_email = str(payload.email).strip().lower()

#     if get_user_by_email(normalized_email):
#         raise ValueError(
#             "El correo ya está registrado en Xapity. "
#             "Utiliza tu cuenta existente."
#         )

#     now = datetime.now(timezone.utc)
#     code = generate_registration_code()

#     pending_document = {
#         "pendingRegistrationId": str(uuid.uuid4()),
#         "registrationType": "global_visitor",
#         "name": payload.name.strip(),
#         "rut": payload.rut,
#         "phone": payload.phone,
#         "emergencyPhone": payload.emergencyPhone,
#         "email": normalized_email,
#         "passwordHash": hash_password(payload.password),
#         "verificationCodeHash": hash_registration_code(code),
#         "expiresAt": now + timedelta(
#             minutes=VISITOR_CODE_EXPIRE_MINUTES
#         ),
#         "attempts": 0,
#         "usedAt": None,
#         "createdAt": now,
#         "updatedAt": now,
#     }

#     collection = get_visitor_pending_registrations_collection()

#     collection.replace_one(
#         {"email": normalized_email},
#         pending_document,
#         upsert=True,
#     )

#     send_registration_verification_email(
#         to_email=normalized_email,
#         code=code,
#         expires_minutes=VISITOR_CODE_EXPIRE_MINUTES,
#     )

#     return {
#         "ok": True,
#         "message": "Código de verificación enviado al correo.",
#         "email": normalized_email,
#     }


async def start_visitor_registration(
    payload: VisitorRegisterStartRequest,
) -> Dict[str, Any]:

    import math
    from pymongo import ReturnDocument

    normalized_email = str(payload.email).strip().lower()

    if get_user_by_email(normalized_email):
        raise ValueError(
            "El correo ya está registrado en Xapity. "
            "Utiliza tu cuenta existente."
        )

    now = datetime.now(timezone.utc)
    cooldown = timedelta(
        seconds=VISITOR_RESEND_COOLDOWN_SECONDS
    )

    collection = get_visitor_pending_registrations_collection()

    existing = collection.find_one({
        "email": normalized_email,
    })

    if existing:
        last_sent = existing.get("codeSentAt")

        if last_sent and last_sent.tzinfo is None:
            last_sent = last_sent.replace(
                tzinfo=timezone.utc
            )

        if last_sent and now < last_sent + cooldown:
            retry_after = max(
                1,
                math.ceil(
                    (
                        last_sent + cooldown - now
                    ).total_seconds()
                ),
            )
            raise VisitorCooldownError(retry_after)

        if int(existing.get("attempts") or 0) >= VISITOR_MAX_ATTEMPTS:
            raise ValueError(
                "Se superó el máximo de intentos de verificación."
            )

    code = generate_registration_code()

    update_fields = {
        "registrationType": "global_visitor",
        "name": payload.name.strip(),
        "rut": payload.rut,
        "phone": payload.phone,
        "emergencyPhone": payload.emergencyPhone,
        "email": normalized_email,
        "passwordHash": hash_password(payload.password),
        "verificationCodeHash": hash_registration_code(code),
        "expiresAt": now + timedelta(
            minutes=VISITOR_CODE_EXPIRE_MINUTES
        ),
        "codeSentAt": now,
        "usedAt": None,
        "updatedAt": now,
    }

    if existing:
        # Update only if another request has not
        # modified the pending registration.
        updated = collection.find_one_and_update(
            {
                "_id": existing["_id"],
                "updatedAt": existing["updatedAt"],
                "usedAt": None,
                "attempts": {"$lt": VISITOR_MAX_ATTEMPTS},
            },
            {
                "$set": update_fields,
            },
            return_document=ReturnDocument.AFTER,
        )

        if not updated:
            raise VisitorCooldownError(
                VISITOR_RESEND_COOLDOWN_SECONDS
            )

    else:
        pending_document = {
            **update_fields,
            "pendingRegistrationId": str(uuid.uuid4()),
            "attempts": 0,
            "createdAt": now,
        }

        try:
            collection.insert_one(pending_document)

        except DuplicateKeyError as exc:
            raise VisitorCooldownError(
                VISITOR_RESEND_COOLDOWN_SECONDS
            ) from exc

    send_registration_verification_email(
        to_email=normalized_email,
        code=code,
        expires_minutes=VISITOR_CODE_EXPIRE_MINUTES,
    )

    return {
        "ok": True,
        "message": "Código de verificación enviado al correo.",
        "email": normalized_email,
    }


# ============================================================
# VERIFY VISITOR REGISTRATION
# ============================================================


# async def verify_visitor_registration(
#     payload: VisitorRegisterVerifyRequest,
# ) -> Dict[str, Any]:

#     normalized_email = str(payload.email).strip().lower()

#     if get_user_by_email(normalized_email):
#         raise ValueError(
#             "El correo ya está registrado en Xapity."
#         )

#     pending = get_pending_visitor(normalized_email)

#     if not pending:
#         raise ValueError(
#             "No existe una solicitud de registro pendiente."
#         )

#     if pending.get("registrationType") != "global_visitor":
#         raise ValueError("Tipo de registro inválido.")

#     now = datetime.now(timezone.utc)

#     expires_at = pending.get("expiresAt")

#     if expires_at and expires_at.tzinfo is None:
#         expires_at = expires_at.replace(tzinfo=timezone.utc)

#     if not expires_at or expires_at <= now:
#         raise ValueError("El código de verificación expiró.")

#     attempts = int(pending.get("attempts") or 0)

#     if attempts >= VISITOR_MAX_ATTEMPTS:
#         raise ValueError(
#             "Se superó el máximo de intentos de verificación."
#         )

#     verification_hash = pending.get("verificationCodeHash")

#     if not verification_hash:
#         raise ValueError(
#             "Solicitud de verificación inválida."
#         )

#     if not verify_registration_code(
#         payload.code,
#         verification_hash,
#     ):
#         increment_visitor_attempts(
#             normalized_email,
#             pending["_id"],
#         )
#         raise ValueError(
#             "Código de verificación inválido."
#         )

#     collection = get_visitor_pending_registrations_collection()

#     # Claim the pending registration atomically.
#     claimed = collection.find_one_and_update(
#         {
#             "_id": pending["_id"],
#             "email": normalized_email,
#             "usedAt": None,
#             "expiresAt": {"$gt": now},
#             "attempts": {"$lt": VISITOR_MAX_ATTEMPTS},
#             "verificationCodeHash": verification_hash,
#         },
#         {
#             "$set": {
#                 "usedAt": now,
#                 "updatedAt": now,
#             },
#         },
#     )

#     if not claimed:
#         raise ValueError(
#             "La solicitud ya fue utilizada, modificada o expiró."
#         )

#     user_document = {
#         "userId": str(uuid.uuid4()),
#         "name": claimed["name"],
#         "rut": claimed["rut"],
#         "phone": claimed.get("phone"),
#         "emergencyPhone": claimed["emergencyPhone"],
#         "email": normalized_email,
#         "passwordHash": claimed["passwordHash"],
#         "authProvider": "local",
#         "isEmailVerified": True,
#         "isActive": True,
#         "isDeleted": False,
#         "createdAt": now,
#         "updatedAt": now,
#     }

#     try:
#         inserted_user = insert_user(user_document)

#     except DuplicateKeyError as exc:
#         raise ValueError(
#             "La identidad ya existe en Xapity."
#         ) from exc

#     except Exception:
#         # Release the claim only if this request still owns it.
#         collection.update_one(
#             {
#                 "_id": claimed["_id"],
#                 "usedAt": now,
#                 "verificationCodeHash": verification_hash,
#             },
#             {
#                 "$set": {
#                     "usedAt": None,
#                     "updatedAt": datetime.now(timezone.utc),
#                 },
#             },
#         )
#         raise

#     inserted_user.pop("passwordHash", None)
#     inserted_user.pop("_id", None)

#     return inserted_user


async def verify_visitor_registration(
    payload: VisitorRegisterVerifyRequest,
) -> Dict[str, Any]:

    normalized_email = str(payload.email).strip().lower()

    if get_user_by_email(normalized_email):
        raise ValueError(
            "El correo ya está registrado en Xapity."
        )

    now = datetime.now(timezone.utc)
    collection = get_visitor_pending_registrations_collection()

    # Reserve one verification attempt atomically.
    # Only requests within the configured limit
    # can proceed to code verification.
    pending = collection.find_one_and_update(
        {
            "email": normalized_email,
            "registrationType": "global_visitor",
            "usedAt": None,
            "expiresAt": {"$gt": now},
            "attempts": {"$lt": VISITOR_MAX_ATTEMPTS},
            "verificationCodeHash": {"$exists": True},
        },
        {
            "$inc": {
                "attempts": 1,
            },
            "$set": {
                "updatedAt": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )

    if not pending:
        raise ValueError(
            "La solicitud no existe, expiró o superó "
            "el máximo de intentos de verificación."
        )

    verification_hash = pending.get(
        "verificationCodeHash"
    )

    if not verification_hash:
        raise ValueError(
            "Solicitud de verificación inválida."
        )

    # The attempt has already been consumed.
    if not verify_registration_code(
        payload.code,
        verification_hash,
    ):
        raise ValueError(
            "Código de verificación inválido."
        )

    # Claim the pending registration atomically.
    # The code and attempt counter must still match.
    claimed = collection.find_one_and_update(
        {
            "_id": pending["_id"],
            "email": normalized_email,
            "usedAt": None,
            "expiresAt": {"$gt": now},
            "verificationCodeHash": verification_hash,
            "attempts": pending["attempts"],
        },
        {
            "$set": {
                "usedAt": now,
                "updatedAt": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )

    if not claimed:
        raise ValueError(
            "La solicitud ya fue utilizada, modificada o expiró."
        )

    user_document = {
        "userId": str(uuid.uuid4()),
        "name": claimed["name"],
        "rut": claimed["rut"],
        "phone": claimed.get("phone"),
        "emergencyPhone": claimed["emergencyPhone"],
        "email": normalized_email,
        "passwordHash": claimed["passwordHash"],
        "authProvider": "local",
        "isEmailVerified": True,
        "isActive": True,
        "isDeleted": False,
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        inserted_user = insert_user(user_document)

    except DuplicateKeyError as exc:
        raise ValueError(
            "La identidad ya existe en Xapity."
        ) from exc

    except Exception:
        # Release the claim only if this request still owns it.
        collection.update_one(
            {
                "_id": claimed["_id"],
                "usedAt": now,
                "verificationCodeHash": verification_hash,
            },
            {
                "$set": {
                    "usedAt": None,
                    "updatedAt": datetime.now(timezone.utc),
                },
            },
        )
        raise

    inserted_user.pop("passwordHash", None)
    inserted_user.pop("_id", None)

    return inserted_user
