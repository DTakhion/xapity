# luca_mcp/luca_sales.py

import json
import os
from pathlib import Path

import requests


LUCA_API_BASE_URL = os.getenv(
    "LUCA_API_BASE_URL",
    "https://luca-api-dev-bvxil9xk.ue.gateway.dev",
)

BUSINESS_ID = 70
PAGE_SIZE = 30

TOKEN_FILE = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "luca_token.json"
)



def load_luca_token() -> str:
    """
    Obtiene el JWT de Luca para la PoC.

    Prioridad:
    1. Variable de entorno LUCA_ACCESS_TOKEN (Cloud Run).
    2. results/luca_token.json (desarrollo local).

    No registra ni imprime el token.
    """

    import base64
    import time

    token = os.getenv("LUCA_ACCESS_TOKEN")

    if not token:
        if not TOKEN_FILE.exists():
            raise FileNotFoundError(
                "No existe LUCA_ACCESS_TOKEN ni el archivo local."
            )

        with TOKEN_FILE.open("r", encoding="utf-8") as file:
            token_data = json.load(file)

        token = token_data.get("access_token")

        if token_data.get("token_source") != "api_header":
            raise ValueError(
                "El token local no proviene de la API de Luca."
            )

    if not isinstance(token, str) or not token.strip():
        raise ValueError("No existe un token válido de Luca.")

    token = token.strip()

    try:
        parts = token.split(".")

        if len(parts) != 3:
            raise ValueError("Formato JWT inválido.")

        payload_segment = parts[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)

        payload = json.loads(
            base64.urlsafe_b64decode(padded)
        )

        expires_at = payload.get("exp")

        if not isinstance(expires_at, (int, float)):
            raise ValueError("JWT sin expiración válida.")

        if time.time() >= expires_at:
            raise ValueError(
                "El JWT de Luca expiró. "
                "Debes actualizar el secreto o ejecutar "
                "nuevamente scripts/login.py."
            )

    except (IndexError, ValueError) as exc:
        raise ValueError(
            f"No se pudo utilizar el JWT de Luca: {exc}"
        ) from exc

    return token



def get_luca_sales(
    year: int = 2026,
    month: int = 0,
) -> dict:
    """
    Recupera los movimientos de ingreso desde Luca.

    - businessId fijo en 70
    - month=0: todos los meses
    - linkage=true
    - paginación automática
    - sin normalización de documentos
    """

    if not 1 <= year <= 2100:
        raise ValueError("Año fuera de rango.")

    if not 0 <= month <= 12:
        raise ValueError("month debe estar entre 0 y 12.")

    token = load_luca_token()

    url = (
        f"{LUCA_API_BASE_URL}"
        f"/v1/business/{BUSINESS_ID}"
        "/summary-movements-specific"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    all_documents = []
    page = 0

    with requests.Session() as session:
        while True:
            params = {
                "type": "ingreso",
                "month": month,
                "year": year,
                "max": PAGE_SIZE,
                "page": page,
                "linkage": "true",
            }

            response = session.get(
                url,
                headers=headers,
                params=params,
                timeout=30,
            )

            response.raise_for_status()

            payload = response.json()

            documents = payload.get("libros")

            if not isinstance(documents, list):
                raise ValueError(
                    "Respuesta inesperada: libros no es un array."
                )

            all_documents.extend(documents)

            if len(documents) < PAGE_SIZE:
                break

            page += 1

            # Límite preventivo para evitar bucles indefinidos.
            if page >= 1000:
                raise RuntimeError(
                    "Se alcanzó el límite de paginación."
                )

    return {
        "businessId": BUSINESS_ID,
        "year": year,
        "month": month,
        "totalRecords": len(all_documents),
        "libros": all_documents,
    }