# luca/luca_user_service.py

"""
Servicio de identidad del usuario autenticado en Luca.

Responsabilidades:

- consultar GET /v1/users/me;
- obtener la identidad asociada al bearer token actual;
- validar la respuesta mínima requerida;
- exponer una estructura controlada para otras
  capacidades de Xapity.

Este servicio no:

- persiste usuarios en MongoDB;
- modifica información en Luca;
- decide destinatarios arbitrarios;
- envía correos;
- construye respuestas conversacionales.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)


DEFAULT_LUCA_API_BASE_URL = (
    "https://luca-api-dev-bvxil9xk.ue.gateway.dev"
)

DEFAULT_LUCA_ME_ENDPOINT = (
    "/v1/users/me"
)

DEFAULT_TOKEN_FILE = (
    ROOT_DIR
    / "results"
    / "luca_token.json"
)

DEFAULT_TIMEOUT_SECONDS = 30


# ==================================================
# RESULTADO
# ==================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LucaCurrentUser:
    """
    Identidad normalizada del usuario autenticado
    actualmente en Luca.
    """

    user_id: int
    firstname: str
    lastname: str
    email: str
    organization_id: int | None
    organization_name: str | None
    role_name: str | None
    active: bool

    @property
    def full_name(
        self,
    ) -> str:
        return (
            f"{self.firstname} "
            f"{self.lastname}"
        ).strip()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "userId": self.user_id,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "fullName": self.full_name,
            "email": self.email,
            "organizationId": (
                self.organization_id
            ),
            "organizationName": (
                self.organization_name
            ),
            "roleName": (
                self.role_name
            ),
            "active": self.active,
        }


# ==================================================
# TOKEN
# ==================================================


def _extract_token_from_payload(
    payload: Any,
) -> str | None:
    """
    Extrae un bearer token desde estructuras
    conocidas utilizadas por Luca.
    """

    if isinstance(
        payload,
        str,
    ):
        token = payload.strip()
        return token or None

    if not isinstance(
        payload,
        dict,
    ):
        return None

    candidate_keys = (
        "accessToken",
        "access_token",
        "token",
        "bearerToken",
        "bearer_token",
        "idToken",
        "id_token",
    )

    for key in candidate_keys:
        value = payload.get(
            key
        )

        if (
            isinstance(
                value,
                str,
            )
            and value.strip()
        ):
            return value.strip()

    nested_keys = (
        "data",
        "result",
        "auth",
        "session",
        "user",
    )

    for key in nested_keys:
        token = (
            _extract_token_from_payload(
                payload.get(
                    key
                )
            )
        )

        if token:
            return token

    return None


def load_luca_access_token(
    *,
    token: str | None = None,
    token_file: str | Path = (
        DEFAULT_TOKEN_FILE
    ),
) -> str:
    """
    Obtiene el bearer token siguiendo esta prioridad:

    1. argumento explícito;
    2. LUCA_ACCESS_TOKEN;
    3. LUCA_BEARER_TOKEN;
    4. results/luca_token.json.
    """

    if (
        isinstance(
            token,
            str,
        )
        and token.strip()
    ):
        return (
            token
            .strip()
            .removeprefix(
                "Bearer "
            )
            .strip()
        )

    env_token = (
        os.getenv(
            "LUCA_ACCESS_TOKEN"
        )
        or os.getenv(
            "LUCA_BEARER_TOKEN"
        )
    )

    if (
        isinstance(
            env_token,
            str,
        )
        and env_token.strip()
    ):
        return (
            env_token
            .strip()
            .removeprefix(
                "Bearer "
            )
            .strip()
        )

    token_path = Path(
        token_file
    )

    if not token_path.exists():
        raise RuntimeError(
            "No se encontró el token de Luca. "
            f"Archivo esperado: {token_path}"
        )

    try:
        with token_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(
                file
            )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "El archivo de token de Luca "
            "no contiene JSON válido."
        ) from exc

    extracted_token = (
        _extract_token_from_payload(
            payload
        )
    )

    if not extracted_token:
        raise RuntimeError(
            "No fue posible extraer el "
            "bearer token de Luca."
        )

    return (
        extracted_token
        .removeprefix(
            "Bearer "
        )
        .strip()
    )


# ==================================================
# HTTP
# ==================================================


def _create_luca_session(
    *,
    token: str,
    total_retries: int = 3,
    backoff_factor: float = 0.5,
) -> Session:
    """
    Crea una sesión HTTP autenticada para Luca.
    """

    if not token:
        raise ValueError(
            "Se requiere bearer token."
        )

    retry_strategy = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        status=total_retries,
        backoff_factor=(
            backoff_factor
        ),
        status_forcelist=(
            429,
            500,
            502,
            503,
            504,
        ),
        allowed_methods=frozenset(
            {
                "GET",
            }
        ),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=5,
        pool_maxsize=5,
    )

    session = (
        requests.Session()
    )

    session.mount(
        "https://",
        adapter,
    )

    session.mount(
        "http://",
        adapter,
    )

    session.headers.update(
        {
            "Authorization": (
                f"Bearer {token}"
            ),
            "Accept": (
                "application/json"
            ),
            "User-Agent": (
                "xapity-luca-user-service/1.0"
            ),
        }
    )

    return session


def _raise_for_luca_response(
    response: Response,
) -> None:
    """
    Convierte errores HTTP de Luca en
    excepciones descriptivas.
    """

    if response.status_code == 401:
        raise RuntimeError(
            "Luca respondió 401 Unauthorized. "
            "El bearer token puede haber expirado."
        )

    if response.status_code == 403:
        raise RuntimeError(
            "Luca respondió 403 Forbidden. "
            "El usuario no tiene permisos."
        )

    if response.status_code == 404:
        raise RuntimeError(
            "Luca respondió 404 Not Found "
            "para /v1/users/me."
        )

    if response.status_code >= 400:
        raise RuntimeError(
            "Error consultando usuario actual "
            "en Luca. "
            f"status={response.status_code}"
        )


# ==================================================
# NORMALIZACIÓN
# ==================================================


def _normalize_required_string(
    *,
    value: Any,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise RuntimeError(
            f"Luca no retornó {field_name} "
            "como string."
        )

    normalized = (
        value.strip()
    )

    if not normalized:
        raise RuntimeError(
            f"Luca retornó {field_name} vacío."
        )

    return normalized


def _normalize_optional_string(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = (
        str(value).strip()
    )

    return (
        normalized
        or None
    )


def _normalize_current_user(
    payload: Any,
) -> LucaCurrentUser:
    """
    Valida y normaliza la respuesta de /v1/users/me.
    """

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Luca retornó una respuesta inválida "
            "para el usuario actual."
        )

    user_id = payload.get(
        "id"
    )

    if (
        isinstance(
            user_id,
            bool,
        )
        or not isinstance(
            user_id,
            int,
        )
        or user_id <= 0
    ):
        raise RuntimeError(
            "Luca retornó un id de usuario inválido."
        )

    firstname = (
        _normalize_required_string(
            value=payload.get(
                "firstname"
            ),
            field_name="firstname",
        )
    )

    lastname = (
        _normalize_required_string(
            value=payload.get(
                "lastname"
            ),
            field_name="lastname",
        )
    )

    email = (
        _normalize_required_string(
            value=payload.get(
                "email"
            ),
            field_name="email",
        )
        .lower()
    )

    if (
        "@" not in email
        or email.startswith(
            "@"
        )
        or email.endswith(
            "@"
        )
    ):
        raise RuntimeError(
            "Luca retornó un email inválido "
            "para el usuario actual."
        )

    active = payload.get(
        "active"
    )

    if not isinstance(
        active,
        bool,
    ):
        raise RuntimeError(
            "Luca retornó active inválido "
            "para el usuario actual."
        )

    if not active:
        raise RuntimeError(
            "El usuario actual de Luca "
            "no se encuentra activo."
        )

    organization = (
        payload.get(
            "currentOrganization"
        )
    )

    organization_id: (
        int | None
    ) = None

    organization_name: (
        str | None
    ) = None

    if isinstance(
        organization,
        dict,
    ):
        raw_organization_id = (
            organization.get(
                "id"
            )
        )

        if (
            isinstance(
                raw_organization_id,
                int,
            )
            and not isinstance(
                raw_organization_id,
                bool,
            )
        ):
            organization_id = (
                raw_organization_id
            )

        organization_name = (
            _normalize_optional_string(
                organization.get(
                    "name"
                )
            )
        )

    role = payload.get(
        "role"
    )

    role_name: str | None = None

    if isinstance(
        role,
        dict,
    ):
        role_name = (
            _normalize_optional_string(
                role.get(
                    "name"
                )
            )
        )

    return LucaCurrentUser(
        user_id=user_id,
        firstname=firstname,
        lastname=lastname,
        email=email,
        organization_id=(
            organization_id
        ),
        organization_name=(
            organization_name
        ),
        role_name=role_name,
        active=active,
    )


# ==================================================
# FUNCIÓN PÚBLICA
# ==================================================


def get_luca_current_user(
    *,
    token: str | None = None,
    token_file: str | Path = (
        DEFAULT_TOKEN_FILE
    ),
    timeout_seconds: int = (
        DEFAULT_TIMEOUT_SECONDS
    ),
) -> LucaCurrentUser:
    """
    Consulta el usuario autenticado actual
    mediante GET /v1/users/me.
    """

    resolved_token = (
        load_luca_access_token(
            token=token,
            token_file=token_file,
        )
    )

    base_url = (
        os.getenv(
            "LUCA_API_BASE_URL",
            DEFAULT_LUCA_API_BASE_URL,
        )
        .rstrip("/")
    )

    url = (
        f"{base_url}"
        f"{DEFAULT_LUCA_ME_ENDPOINT}"
    )

    session = (
        _create_luca_session(
            token=resolved_token
        )
    )

    try:
        response = session.get(
            url,
            timeout=(
                timeout_seconds
            ),
        )

        _raise_for_luca_response(
            response
        )

        try:
            payload = (
                response.json()
            )
        except ValueError as exc:
            raise RuntimeError(
                "Luca no retornó JSON válido "
                "para /v1/users/me."
            ) from exc

        return (
            _normalize_current_user(
                payload
            )
        )

    finally:
        session.close()