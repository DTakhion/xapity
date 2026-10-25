# db/mongo_oauth_persistence.py
# ============================================================
# XAPITY — MCP OAUTH PERSISTENCE
# ============================================================

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
from pymongo.errors import PyMongoError
from mcp.shared.auth import OAuthClientInformationFull

from db.mongo_persistence import get_database

import hashlib
import secrets
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from pymongo import ReturnDocument
from mcp.server.auth.provider import AuthorizationCode

CLIENTS_COLLECTION = "mcp_oauth_clients"
CODES_COLLECTION = "mcp_oauth_codes"
TOKENS_COLLECTION = "mcp_oauth_tokens"
FAMILIES_COLLECTION = "mcp_oauth_token_families"


def get_oauth_token_families_collection() -> Collection:
    return get_database()[FAMILIES_COLLECTION]


def get_oauth_clients_collection() -> Collection:
    return get_database()[CLIENTS_COLLECTION]


def get_oauth_codes_collection() -> Collection:
    return get_database()[CODES_COLLECTION]


def get_oauth_tokens_collection() -> Collection:
    return get_database()[TOKENS_COLLECTION]


def initialize_oauth_storage() -> None:
    """
    Inicializa índices para persistencia OAuth.

    La inicialización debe ejecutarse explícitamente
    antes de habilitar el servidor de autorización.
    """

    clients = get_oauth_clients_collection()
    codes = get_oauth_codes_collection()
    tokens = get_oauth_tokens_collection()

    clients.create_index(
        "clientId",
        unique=True,
        name="ux_mcp_oauth_client_id",
    )

    codes.create_index(
        "codeHash",
        unique=True,
        name="ux_mcp_oauth_code_hash",
    )

    codes.create_index(
        "expiresAt",
        expireAfterSeconds=0,
        name="ttl_mcp_oauth_codes",
    )

    tokens.create_index(
        "tokenHash",
        unique=True,
        name="ux_mcp_oauth_token_hash",
    )
    
    families = get_oauth_token_families_collection()

    families.create_index(
        "familyId",
        unique=True,
        name="ux_mcp_oauth_family_id",
    )

    tokens.create_index(
        "expiresAt",
        expireAfterSeconds=0,
        name="ttl_mcp_oauth_tokens",
    )


def detect_oauth_refresh_token_replay(
    token: str,
    *,
    client_id: str,
) -> bool:
    """
    Detecta reutilización de un refresh token consumido.

    Solo considera tokens pertenecientes al cliente
    indicado. Ante replay confirmado, revoca la familia.

    Retorna True si detecta reutilización.
    """

    if not token or not client_id:
        return False

    document = get_oauth_tokens_collection().find_one({
        "tokenHash": _hash_oauth_secret(token),
        "tokenType": "refresh",
        "clientId": client_id,
        "consumedAt": {"$ne": None},
    })

    if document is None:
        return False

    family_id = document.get("familyId")

    if not family_id:
        return False

    revoke_oauth_token_family(family_id)

    return True


# ============================================================
# XAPITY MCP — OAUTH CLIENT PERSISTENCE
# ============================================================

def _validate_redirect_uri(uri: str) -> None:
    """
    Valida las URI de redirección para clientes
    públicos de la PoC.
    """

    parsed = urlsplit(uri)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Unsupported redirect URI scheme.")

    if not parsed.hostname:
        raise ValueError("Redirect URI requires a hostname.")

    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Invalid redirect URI.")

    if parsed.scheme == "http" and parsed.hostname not in (
        "localhost",
        "127.0.0.1",
        "::1",
    ):
        raise ValueError(
            "HTTP redirect URIs are allowed only for loopback."
        )

def register_oauth_client(
    client: OAuthClientInformationFull,
) -> None:
    """
    Registra clientes OAuth públicos y confidenciales.

    Compatible con el registro dinámico (DCR) del SDK MCP.
    """

    allowed_auth_methods = {
        "none",
        "client_secret_post",
        "client_secret_basic",
    }

    auth_method = client.token_endpoint_auth_method

    if auth_method not in allowed_auth_methods:
        raise ValueError(
            "Unsupported OAuth client authentication method."
        )

    # Consistencia entre método y secreto emitido por el SDK.
    if auth_method == "none":
        if client.client_secret is not None:
            raise ValueError(
                "Public OAuth clients must not have a secret."
            )
    else:
        if not client.client_secret:
            raise ValueError(
                "Confidential OAuth clients require a secret."
            )

    # Solo los grants implementados por nuestro proveedor.
    allowed_grants = {
        "authorization_code",
        "refresh_token",
    }

    grant_types = set(client.grant_types or [])

    if (
        "authorization_code" not in grant_types
        or not grant_types.issubset(allowed_grants)
    ):
        raise ValueError(
            "Unsupported OAuth grant types."
        )

    if client.response_types != ["code"]:
        raise ValueError(
            "Only code response type is supported."
        )

    if not client.redirect_uris:
        raise ValueError(
            "At least one redirect URI is required."
        )

    for uri in client.redirect_uris:
        _validate_redirect_uri(str(uri))

    collection = get_oauth_clients_collection()

    document = {
        "clientId": client.client_id,
        "clientData": client.model_dump(mode="json"),
    }

    try:
        collection.insert_one(document)

    except DuplicateKeyError as exc:
        raise ValueError(
            "OAuth client already registered."
        ) from exc


def get_oauth_client(
    client_id: str,
) -> OAuthClientInformationFull | None:
    """
    Recupera un cliente OAuth registrado.
    """

    collection = get_oauth_clients_collection()

    document = collection.find_one({
        "clientId": client_id,
    })

    if document is None:
        return None

    return OAuthClientInformationFull.model_validate(
        document["clientData"]
    )

# ============================================================
# XAPITY MCP — OAUTH AUTHORIZATION CODES
# ============================================================

AUTHORIZATION_CODE_TTL_SECONDS = 300


def _hash_oauth_secret(value: str) -> str:
    """
    SHA-256 para identificadores OAuth aleatorios
    de alta entropía.
    """
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def create_oauth_authorization_code(
    *,
    client_id: str,
    subject: str,
    scopes: list[str],
    code_challenge: str,
    redirect_uri: str,
    redirect_uri_provided_explicitly: bool,
    resource: str | None = None,
) -> str:
    """
    Genera y almacena un código OAuth temporal.

    Devuelve el código original únicamente al
    componente que completa la autorización.
    """

    if not client_id or not subject:
        raise ValueError("Client and subject are required.")

    if not code_challenge:
        raise ValueError("PKCE code challenge is required.")

    if not redirect_uri:
        raise ValueError("Redirect URI is required.")

    code = secrets.token_urlsafe(32)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        seconds=AUTHORIZATION_CODE_TTL_SECONDS
    )

    collection = get_oauth_codes_collection()

    collection.insert_one({
        "codeHash": _hash_oauth_secret(code),
        "clientId": client_id,
        "subject": subject,
        "scopes": scopes,
        "codeChallenge": code_challenge,
        "redirectUri": redirect_uri,
        "redirectUriProvidedExplicitly": (
            redirect_uri_provided_explicitly
        ),
        "resource": resource,
        "createdAt": now,
        "expiresAt": expires_at,
        "usedAt": None,
    })

    return code


def get_oauth_authorization_code(
    code: str,
) -> AuthorizationCode | None:
    """
    Recupera un código OAuth sin consumirlo.

    Permite que el SDK MCP valide:
    - Cliente OAuth.
    - Expiración.
    - Redirect URI.
    - PKCE.

    El consumo definitivo ocurre únicamente
    durante exchange_authorization_code().
    """

    now = datetime.now(timezone.utc)

    collection = get_oauth_codes_collection()

    document = collection.find_one(
        {
            "codeHash": _hash_oauth_secret(code),
            "usedAt": None,
            "expiresAt": {"$gt": now},
        }
    )

    if document is None:
        return None

    expires_at = document["expiresAt"]

    # PyMongo puede devolver UTC sin tzinfo.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    return AuthorizationCode(
        code=code,
        client_id=document["clientId"],
        subject=document["subject"],
        scopes=document["scopes"],
        expires_at=expires_at.timestamp(),
        code_challenge=document["codeChallenge"],
        redirect_uri=document["redirectUri"],
        redirect_uri_provided_explicitly=(
            document["redirectUriProvidedExplicitly"]
        ),
        resource=document.get("resource"),
    )

def consume_oauth_authorization_code(
    code: str,
) -> AuthorizationCode | None:
    """
    Consume atómicamente un código OAuth.

    Un código expirado o previamente utilizado
    no puede volver a consumirse.
    """

    now = datetime.now(timezone.utc)

    collection = get_oauth_codes_collection()

    document = collection.find_one_and_update(
        {
            "codeHash": _hash_oauth_secret(code),
            "usedAt": None,
            "expiresAt": {"$gt": now},
        },
        {
            "$set": {
                "usedAt": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if document is None:
        return None
    
    expires_at = document["expiresAt"]

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    return AuthorizationCode(
        code=code,
        client_id=document["clientId"],
        subject=document["subject"],
        scopes=document["scopes"],
        expires_at=expires_at.timestamp(),
        code_challenge=document["codeChallenge"],
        redirect_uri=document["redirectUri"],
        redirect_uri_provided_explicitly=(
            document["redirectUriProvidedExplicitly"]
        ),
        resource=document.get("resource"),
    )


def exchange_oauth_authorization_code(
    code: str,
    *,
    client_id: str,
    expected_code_challenge: str,
    expected_redirect_uri: str,
    expected_redirect_uri_provided_explicitly: bool,
    expected_resource: str | None,
    expected_subject: str,
    expected_scopes: list[str],
) -> tuple[str, str] | None:
    """
    Intercambia un código OAuth por access y refresh tokens.

    Operación transaccional:
    - Consume el código una sola vez.
    - Crea una familia de tokens.
    - Emite access y refresh tokens.
    - Revierte todos los cambios ante un error.

    IMPORTANTE:
    Debe invocarse únicamente después de que el SDK
    haya validado redirect_uri y PKCE.
    """

    if not code or not client_id:
        return None

    codes = get_oauth_codes_collection()
    tokens = get_oauth_tokens_collection()
    families = get_oauth_token_families_collection()

    now = datetime.now(timezone.utc)

    family_id = uuid4().hex

    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    
    
    code_filter = {
        "codeHash": _hash_oauth_secret(code),
        "clientId": client_id,
        "usedAt": None,
        "expiresAt": {"$gt": now},
        "codeChallenge": expected_code_challenge,
        "redirectUri": expected_redirect_uri,
        "redirectUriProvidedExplicitly": (
            expected_redirect_uri_provided_explicitly
        ),
        "resource": expected_resource,
        "subject": expected_subject,
        "scopes": list(expected_scopes),
    }

    if expected_code_challenge is not None:
        code_filter["codeChallenge"] = expected_code_challenge

    if expected_redirect_uri is not None:
        code_filter["redirectUri"] = expected_redirect_uri

    if expected_redirect_uri_provided_explicitly is not None:
        code_filter["redirectUriProvidedExplicitly"] = (
            expected_redirect_uri_provided_explicitly
        )

    if expected_resource is not None:
        code_filter["resource"] = expected_resource

    if expected_subject is not None:
        code_filter["subject"] = expected_subject

    if expected_scopes is not None:
        code_filter["scopes"] = list(expected_scopes)


    with codes.database.client.start_session() as session:
        with session.start_transaction():

            document = codes.find_one_and_update(
                code_filter,
                {
                    "$set": {"usedAt": now},
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )

            if document is None:
                return None

            subject = document["subject"]
            scopes = document["scopes"]
            resource = document.get("resource")

            if not subject or not scopes or not resource:
                raise ValueError(
                    "Incomplete authorization code context."
                )

            families.insert_one(
                {
                    "familyId": family_id,
                    "clientId": client_id,
                    "subject": subject,
                    "resource": resource,
                    "status": "active",
                    "version": 1,
                    "createdAt": now,
                    "revokedAt": None,
                },
                session=session,
            )

            common_fields = {
                "clientId": client_id,
                "subject": subject,
                "scopes": list(scopes),
                "resource": resource,
                "familyId": family_id,
                "createdAt": now,
                "revokedAt": None,
                "consumedAt": None,
            }

            tokens.insert_many(
                [
                    {
                        **common_fields,
                        "tokenHash": _hash_oauth_secret(
                            access_token
                        ),
                        "tokenType": "access",
                        "expiresAt": now + timedelta(
                            seconds=ACCESS_TOKEN_TTL_SECONDS
                        ),
                    },
                    {
                        **common_fields,
                        "tokenHash": _hash_oauth_secret(
                            refresh_token
                        ),
                        "tokenType": "refresh",
                        "expiresAt": now + timedelta(
                            seconds=REFRESH_TOKEN_TTL_SECONDS
                        ),
                    },
                ],
                session=session,
            )

    return access_token, refresh_token


# ============================================================
# XAPITY MCP — OAUTH TOKEN PERSISTENCE
# ============================================================

ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60


def _create_oauth_token(
    *,
    token_type: str,
    client_id: str,
    subject: str,
    scopes: list[str],
    resource: str,
    ttl_seconds: int,
    family_id: str | None = None,
) -> str:
    """
    Crea un token opaco y almacena únicamente su hash.
    """

    if token_type not in ("access", "refresh"):
        raise ValueError("Invalid OAuth token type.")

    if not client_id or not subject:
        raise ValueError("Client and subject are required.")

    if not resource:
        raise ValueError("OAuth resource is required.")

    if not scopes:
        raise ValueError("At least one scope is required.")

    token = secrets.token_urlsafe(32)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)

    get_oauth_tokens_collection().insert_one({
        "tokenHash": _hash_oauth_secret(token),
        "tokenType": token_type,
        "clientId": client_id,
        "subject": subject,
        "scopes": list(scopes),
        "resource": resource,
        "familyId": family_id,
        "consumedAt": None,
        "createdAt": now,
        "expiresAt": expires_at,
        "revokedAt": None,
    })

    return token


def create_oauth_access_token(
    *,
    client_id: str,
    subject: str,
    scopes: list[str],
    resource: str,
) -> str:
    return _create_oauth_token(
        token_type="access",
        client_id=client_id,
        subject=subject,
        scopes=scopes,
        resource=resource,
        ttl_seconds=ACCESS_TOKEN_TTL_SECONDS,
    )



def create_oauth_refresh_token(
    *,
    client_id: str,
    subject: str,
    scopes: list[str],
    resource: str,
    family_id: str | None = None,
) -> str:
    """
    Crea un refresh token y su familia de forma atómica.

    Si se reutiliza una familia existente, exige que
    continúe activa y pertenezca al mismo contexto.
    """

    if not client_id or not subject or not resource or not scopes:
        raise ValueError("Incomplete OAuth token context.")

    families = get_oauth_token_families_collection()
    tokens = get_oauth_tokens_collection()

    now = datetime.now(timezone.utc)
    new_family = family_id is None

    if new_family:
        family_id = uuid4().hex

    token = secrets.token_urlsafe(32)

    token_document = {
        "tokenHash": _hash_oauth_secret(token),
        "tokenType": "refresh",
        "clientId": client_id,
        "subject": subject,
        "scopes": list(scopes),
        "resource": resource,
        "familyId": family_id,
        "createdAt": now,
        "expiresAt": now + timedelta(
            seconds=REFRESH_TOKEN_TTL_SECONDS
        ),
        "revokedAt": None,
        "consumedAt": None,
    }

    with tokens.database.client.start_session() as session:
        with session.start_transaction():

            if new_family:
                families.insert_one(
                    {
                        "familyId": family_id,
                        "clientId": client_id,
                        "subject": subject,
                        "resource": resource,
                        "status": "active",
                        "version": 0,
                        "createdAt": now,
                        "revokedAt": None,
                    },
                    session=session,
                )

            family_updated = families.update_one(
                {
                    "familyId": family_id,
                    "status": "active",
                    "clientId": client_id,
                    "subject": subject,
                    "resource": resource,
                },
                {
                    "$inc": {"version": 1},
                },
                session=session,
            )

            if family_updated.matched_count != 1:
                raise ValueError(
                    "OAuth token family unavailable."
                )

            tokens.insert_one(
                token_document,
                session=session,
            )

    return token



def get_oauth_token(
    token: str,
    *,
    token_type: str,
) -> dict | None:
    """
    Recupera un token vigente y no revocado.

    Si pertenece a una familia OAuth, exige que
    esta permanezca activa y corresponda al
    mismo cliente, usuario y recurso.
    """

    if token_type not in ("access", "refresh"):
        raise ValueError("Invalid OAuth token type.")

    if not token:
        return None

    now = datetime.now(timezone.utc)

    document = get_oauth_tokens_collection().find_one({
        "tokenHash": _hash_oauth_secret(token),
        "tokenType": token_type,
        "expiresAt": {"$gt": now},
        "revokedAt": None,
    })

    if document is None:
        return None

    if (
        token_type == "refresh"
        and document.get("consumedAt") is not None
    ):
        return None

    family_id = document.get("familyId")

    # Todo refresh token debe pertenecer a una familia.
    if token_type == "refresh" and not family_id:
        return None

    if family_id:
        family = get_oauth_token_family(family_id)

        if family is None:
            return None

        if family.get("status") != "active":
            return None

        if family.get("clientId") != document.get("clientId"):
            return None

        if family.get("subject") != document.get("subject"):
            return None

        if family.get("resource") != document.get("resource"):
            return None

    return document


def revoke_oauth_token(
    token: str,
    *,
    token_type: str,
) -> bool:
    """
    Revoca un token mediante una operación atómica.
    """

    if token_type not in ("access", "refresh"):
        raise ValueError("Invalid OAuth token type.")

    if not token:
        return False

    now = datetime.now(timezone.utc)

    result = get_oauth_tokens_collection().update_one(
        {
            "tokenHash": _hash_oauth_secret(token),
            "tokenType": token_type,
            "revokedAt": None,
        },
        {
            "$set": {
                "revokedAt": now,
            }
        },
    )

    return result.modified_count == 1

# ============================================================
# XAPITY MCP — REFRESH TOKEN ROTATION
# ============================================================



def consume_oauth_refresh_token(
    token: str,
    *,
    client_id: str,
) -> dict | None:
    """
    Operación deshabilitada.

    La renovación debe utilizar exclusivamente
    rotate_oauth_refresh_token().
    """
    raise RuntimeError(
        "Use rotate_oauth_refresh_token() instead."
    )


def revoke_oauth_token_family(
    family_id: str,
) -> int:
    if not family_id:
        return 0

    now = datetime.now(timezone.utc)

    families = get_oauth_token_families_collection()
    tokens = get_oauth_tokens_collection()

    with families.database.client.start_session() as session:
        with session.start_transaction():
            updated = families.update_one(
                {
                    "familyId": family_id,
                    "status": "active",
                },
                {
                    "$set": {
                        "status": "revoked",
                        "revokedAt": now,
                    },
                    "$inc": {
                        "version": 1,
                    },
                },
                session=session,
            )

            if updated.modified_count == 1:
                tokens.update_many(
                    {
                        "familyId": family_id,
                        "revokedAt": None,
                    },
                    {
                        "$set": {"revokedAt": now}
                    },
                    session=session,
                )

    return updated.modified_count

# ============================================================
# XAPITY MCP — ATOMIC REFRESH TOKEN ROTATION
# ============================================================


# def rotate_oauth_refresh_token(
#     token: str,
#     *,
#     client_id: str,
# ) -> str | None:
#     """
#     Rota un refresh token de manera transaccional.

#     Devuelve el nuevo token cuando la rotación
#     se confirma correctamente.

#     Si detecta reutilización de un token consumido,
#     revoca la familia completa.

#     Requiere MongoDB con soporte de transacciones.
#     """

#     if not token or not client_id:
#         return None

#     collection = get_oauth_tokens_collection()
#     token_hash = _hash_oauth_secret(token)

#     now = datetime.now(timezone.utc)

#     # --------------------------------------------------------
#     # 1. Consultar el token original
#     # --------------------------------------------------------

#     original = collection.find_one({
#         "tokenHash": token_hash,
#         "tokenType": "refresh",
#         "clientId": client_id,
#     })

#     if original is None:
#         return None

#     family_id = original.get("familyId")

#     if not family_id:
#         return None

#     # --------------------------------------------------------
#     # 2. Detectar reutilización
#     # --------------------------------------------------------

#     if original.get("consumedAt") is not None:
#         revoke_oauth_token_family(family_id)
#         return None

#     if original.get("revokedAt") is not None:
#         return None

#     expires_at = original.get("expiresAt")

#     if expires_at is None:
#         return None

#     # PyMongo devuelve fechas naive por defecto.
#     # MongoDB almacena las fechas en UTC.
#     if expires_at.tzinfo is None:
#         expires_at = expires_at.replace(tzinfo=timezone.utc)

#     if expires_at <= now:
#         return None

#     # --------------------------------------------------------
#     # 3. Preparar el token de reemplazo
#     # --------------------------------------------------------

#     new_token = secrets.token_urlsafe(32)

#     new_document = {
#         "tokenHash": _hash_oauth_secret(new_token),
#         "tokenType": "refresh",
#         "clientId": original["clientId"],
#         "subject": original["subject"],
#         "scopes": original["scopes"],
#         "resource": original["resource"],
#         "familyId": family_id,
#         "createdAt": now,
#         "expiresAt": now + timedelta(
#             seconds=REFRESH_TOKEN_TTL_SECONDS
#         ),
#         "revokedAt": None,
#         "consumedAt": None,
#     }

#     # --------------------------------------------------------
#     # 4. Consumir A y crear B en una transacción
#     # --------------------------------------------------------

#     client = collection.database.client

#     try:
#         with client.start_session() as session:
#             with session.start_transaction():

#                 updated = collection.update_one(
#                     {
#                         "_id": original["_id"],
#                         "consumedAt": None,
#                         "revokedAt": None,
#                         "expiresAt": {"$gt": now},
#                     },
#                     {
#                         "$set": {
#                             "consumedAt": now,
#                         }
#                     },
#                     session=session,
#                 )

#                 if updated.modified_count != 1:
#                     raise ValueError(
#                         "Refresh token already consumed."
#                     )

#                 collection.insert_one(
#                     new_document,
#                     session=session,
#                 )

#     except ValueError:
#         # Posible carrera con otra renovación.
#         # La siguiente consulta determina si hubo consumo.
#         latest = collection.find_one({
#             "tokenHash": token_hash,
#             "tokenType": "refresh",
#             "clientId": client_id,
#         })

#         if latest and latest.get("consumedAt") is not None:
#             revoke_oauth_token_family(family_id)

#         return None

#     except PyMongoError:
#         # No entregar un token si la transacción falla.
#         raise

#     return new_token


def rotate_oauth_refresh_token(
    token: str,
    *,
    client_id: str,
) -> str | None:
    """
    Rota un refresh token mediante una transacción.

    La familia participa en la misma transacción
    que el consumo del token y la emisión del sucesor.

    La reutilización confirmada revoca la familia.
    """

    if not token or not client_id:
        return None

    tokens = get_oauth_tokens_collection()
    families = get_oauth_token_families_collection()

    token_hash = _hash_oauth_secret(token)
    now = datetime.now(timezone.utc)

    original = tokens.find_one({
        "tokenHash": token_hash,
        "tokenType": "refresh",
        "clientId": client_id,
    })

    if original is None:
        return None

    family_id = original.get("familyId")

    if not family_id:
        return None

    # Reutilización confirmada.
    if original.get("consumedAt") is not None:
        revoke_oauth_token_family(family_id)
        return None

    if original.get("revokedAt") is not None:
        return None

    expires_at = original.get("expiresAt")

    if expires_at is None:
        return None

    # PyMongo devuelve fechas UTC naive por defecto.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at <= now:
        return None

    new_token = secrets.token_urlsafe(32)

    new_document = {
        "tokenHash": _hash_oauth_secret(new_token),
        "tokenType": "refresh",
        "clientId": original["clientId"],
        "subject": original["subject"],
        "scopes": list(original["scopes"]),
        "resource": original["resource"],
        "familyId": family_id,
        "createdAt": now,
        "expiresAt": now + timedelta(
            seconds=REFRESH_TOKEN_TTL_SECONDS
        ),
        "revokedAt": None,
        "consumedAt": None,
    }

    try:
        with tokens.database.client.start_session() as session:
            with session.start_transaction():

                # Bloqueo lógico mediante escritura compartida
                # del documento de familia.
                family_updated = families.update_one(
                    {
                        "familyId": family_id,
                        "status": "active",
                        "clientId": original["clientId"],
                        "subject": original["subject"],
                        "resource": original["resource"],
                    },
                    {
                        "$inc": {"version": 1},
                    },
                    session=session,
                )

                if family_updated.matched_count != 1:
                    raise ValueError(
                        "OAuth token family unavailable."
                    )

                consumed = tokens.update_one(
                    {
                        "_id": original["_id"],
                        "consumedAt": None,
                        "revokedAt": None,
                        "expiresAt": {"$gt": now},
                    },
                    {
                        "$set": {"consumedAt": now},
                    },
                    session=session,
                )

                if consumed.modified_count != 1:
                    raise ValueError(
                        "Refresh token unavailable."
                    )

                tokens.insert_one(
                    new_document,
                    session=session,
                )

    except ValueError:
        # La transacción fue abortada.
        # Comprobar si otra solicitud consumió A.
        latest = tokens.find_one({
            "tokenHash": token_hash,
            "tokenType": "refresh",
            "clientId": client_id,
        })

        if latest and latest.get("consumedAt") is not None:
            revoke_oauth_token_family(family_id)

        return None

    except PyMongoError:
        # No entregar tokens ante errores de MongoDB.
        # El proveedor OAuth deberá tratar este error
        # como fallo de servicio, no como autenticación válida.
        raise

    return new_token


def rotate_oauth_refresh_token_pair(
    token: str,
    *,
    client_id: str,
) -> tuple[str, str] | None:
    """
    Rota un refresh token y emite un access token
    dentro de la misma transacción MongoDB.

    Retorna:
        (access_token, refresh_token)

    La reutilización confirmada revoca la familia.
    """

    if not token or not client_id:
        return None

    tokens = get_oauth_tokens_collection()
    families = get_oauth_token_families_collection()

    token_hash = _hash_oauth_secret(token)
    now = datetime.now(timezone.utc)

    original = tokens.find_one({
        "tokenHash": token_hash,
        "tokenType": "refresh",
        "clientId": client_id,
    })

    if original is None:
        return None

    family_id = original.get("familyId")

    if not family_id:
        return None

    if original.get("consumedAt") is not None:
        revoke_oauth_token_family(family_id)
        return None

    if original.get("revokedAt") is not None:
        return None

    expires_at = original.get("expiresAt")

    if expires_at is None:
        return None

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at <= now:
        return None

    new_access_token = secrets.token_urlsafe(32)
    new_refresh_token = secrets.token_urlsafe(32)

    common_fields = {
        "clientId": original["clientId"],
        "subject": original["subject"],
        "scopes": list(original["scopes"]),
        "resource": original["resource"],
        "familyId": family_id,
        "createdAt": now,
        "revokedAt": None,
        "consumedAt": None,
    }

    try:
        with tokens.database.client.start_session() as session:
            with session.start_transaction():

                family_updated = families.update_one(
                    {
                        "familyId": family_id,
                        "status": "active",
                        "clientId": original["clientId"],
                        "subject": original["subject"],
                        "resource": original["resource"],
                    },
                    {
                        "$inc": {"version": 1},
                    },
                    session=session,
                )

                if family_updated.matched_count != 1:
                    raise ValueError(
                        "OAuth token family unavailable."
                    )

                consumed = tokens.update_one(
                    {
                        "_id": original["_id"],
                        "consumedAt": None,
                        "revokedAt": None,
                        "expiresAt": {"$gt": now},
                    },
                    {
                        "$set": {"consumedAt": now},
                    },
                    session=session,
                )

                if consumed.modified_count != 1:
                    raise ValueError(
                        "Refresh token unavailable."
                    )

                tokens.insert_many(
                    [
                        {
                            **common_fields,
                            "tokenHash": _hash_oauth_secret(
                                new_access_token
                            ),
                            "tokenType": "access",
                            "expiresAt": now + timedelta(
                                seconds=ACCESS_TOKEN_TTL_SECONDS
                            ),
                        },
                        {
                            **common_fields,
                            "tokenHash": _hash_oauth_secret(
                                new_refresh_token
                            ),
                            "tokenType": "refresh",
                            "expiresAt": now + timedelta(
                                seconds=REFRESH_TOKEN_TTL_SECONDS
                            ),
                        },
                    ],
                    session=session,
                )

    except ValueError:
        latest = tokens.find_one({
            "tokenHash": token_hash,
            "tokenType": "refresh",
            "clientId": client_id,
        })

        if latest and latest.get("consumedAt") is not None:
            revoke_oauth_token_family(family_id)

        return None

    except PyMongoError:
        raise

    return new_access_token, new_refresh_token


# ============================================================
# XAPITY MCP — TOKEN FAMILIES
# ============================================================

def create_oauth_token_family(
    *,
    client_id: str,
    subject: str,
    resource: str,
) -> str:
    family_id = uuid4().hex
    now = datetime.now(timezone.utc)

    get_oauth_token_families_collection().insert_one({
        "familyId": family_id,
        "clientId": client_id,
        "subject": subject,
        "resource": resource,
        "status": "active",
        "createdAt": now,
        "revokedAt": None,
    })

    return family_id


def get_oauth_token_family(
    family_id: str,
) -> dict | None:
    return get_oauth_token_families_collection().find_one({
        "familyId": family_id,
    })