# data_loader/reportes_luca.py

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from dotenv import load_dotenv
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from db.mongo_persistence_luca import (
    persist_luca_report_snapshot,
)


# ==================================================
# CONFIGURACIÓN
# ==================================================


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)


DEFAULT_LUCA_API_BASE_URL = (
    "https://luca-api-dev-bvxil9xk.ue.gateway.dev"
)

GENERAL_BALANCE_ENDPOINT_PATH = (
    "/v1/business/{business_id}/balance"
)

DEFAULT_TIMEOUT_SECONDS = 60

DEFAULT_TOKEN_FILE = (
    ROOT_DIR
    / "results"
    / "luca_token.json"
)


SUMMARY_ROW_SUBTOTAL = "Sub Totales"
SUMMARY_ROW_RESULT = "Resultado"
SUMMARY_ROW_TOTALS = "Totales"


SUMMARY_ROW_NAMES = {
    SUMMARY_ROW_SUBTOTAL,
    SUMMARY_ROW_RESULT,
    SUMMARY_ROW_TOTALS,
}


# ==================================================
# MODELOS DE RESULTADO
# ==================================================


@dataclass
class LucaReportLoadResult:
    """
    Resultado estructurado de una carga de reporte desde Luca.
    """

    metadata: dict[str, Any]
    report: dict[str, Any]
    summary: dict[str, Any]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "report": self.report,
            "summary": self.summary,
            "trace": self.trace,
        }


# ==================================================
# UTILIDADES
# ==================================================


def utc_now() -> datetime:
    """
    Fecha y hora UTC actual.
    """

    return datetime.now(
        timezone.utc
    )


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convierte un valor numérico de forma segura.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Convierte un valor a entero de forma segura.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_optional_string(
    value: Any,
) -> str | None:
    """
    Normaliza strings opcionales.
    """

    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    return normalized or None


def _parse_iso_date(
    value: str | date,
    field_name: str,
) -> date:
    """
    Convierte YYYY-MM-DD o date a date.
    """

    if isinstance(
        value,
        datetime,
    ):
        return value.date()

    if isinstance(
        value,
        date,
    ):
        return value

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} debe ser date o string YYYY-MM-DD."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} no puede estar vacío."
        )

    try:
        return date.fromisoformat(
            normalized
        )
    except ValueError as exc:
        raise ValueError(
            f"{field_name} debe tener formato YYYY-MM-DD. "
            f"Valor recibido: {value!r}"
        ) from exc


def _validate_date_range(
    *,
    query_from: str | date,
    query_to: str | date,
) -> tuple[date, date]:
    """
    Valida y normaliza un rango de fechas.
    """

    parsed_from = _parse_iso_date(
        query_from,
        "query_from",
    )

    parsed_to = _parse_iso_date(
        query_to,
        "query_to",
    )

    if parsed_from > parsed_to:
        raise ValueError(
            "query_from no puede ser posterior a query_to."
        )

    return (
        parsed_from,
        parsed_to,
    )


# ==================================================
# CONFIGURACIÓN LUCA
# ==================================================


def get_luca_business_id(
    business_id: int | None = None,
) -> int:
    """
    Obtiene businessId desde argumento o LUCA_BUSINESS_ID.
    """

    if business_id is not None:
        if isinstance(
            business_id,
            bool,
        ) or not isinstance(
            business_id,
            int,
        ):
            raise TypeError(
                "business_id debe ser un entero."
            )

        if business_id <= 0:
            raise ValueError(
                "business_id debe ser mayor que cero."
            )

        return business_id

    raw_business_id = os.getenv(
        "LUCA_BUSINESS_ID"
    )

    if not raw_business_id:
        raise RuntimeError(
            "Falta LUCA_BUSINESS_ID en .env "
            "y no se proporcionó business_id."
        )

    try:
        parsed_business_id = int(
            raw_business_id
        )
    except ValueError as exc:
        raise RuntimeError(
            "LUCA_BUSINESS_ID debe ser un entero."
        ) from exc

    if parsed_business_id <= 0:
        raise RuntimeError(
            "LUCA_BUSINESS_ID debe ser mayor que cero."
        )

    return parsed_business_id


def get_luca_api_base_url() -> str:
    """
    Permite sobrescribir la URL base mediante LUCA_API_BASE_URL.
    """

    base_url = os.getenv(
        "LUCA_API_BASE_URL",
        DEFAULT_LUCA_API_BASE_URL,
    )

    return base_url.rstrip("/")


# ==================================================
# TOKEN
# ==================================================


def _extract_token_from_payload(
    payload: Any,
) -> str | None:
    """
    Busca un token dentro de distintas estructuras JSON posibles.
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
        nested_value = payload.get(
            key
        )

        token = _extract_token_from_payload(
            nested_value
        )

        if token:
            return token

    return None


def load_luca_access_token(
    token: str | None = None,
    token_file: str | Path = DEFAULT_TOKEN_FILE,
) -> str:
    """
    Obtiene el bearer token siguiendo esta prioridad:

    1. argumento token;
    2. LUCA_ACCESS_TOKEN;
    3. LUCA_BEARER_TOKEN;
    4. results/luca_token.json.
    """

    if token and token.strip():
        return (
            token
            .strip()
            .removeprefix("Bearer ")
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
        env_token
        and env_token.strip()
    ):
        return (
            env_token
            .strip()
            .removeprefix("Bearer ")
            .strip()
        )

    token_path = Path(
        token_file
    )

    if not token_path.exists():
        raise RuntimeError(
            "No se encontró token de Luca. "
            "Ejecuta scripts/login.py o define "
            "LUCA_ACCESS_TOKEN. "
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
            "El archivo de token no contiene JSON válido: "
            f"{token_path}"
        ) from exc

    extracted_token = (
        _extract_token_from_payload(
            payload
        )
    )

    if not extracted_token:
        raise RuntimeError(
            "No fue posible extraer el token desde "
            f"{token_path}."
        )

    normalized_token = (
        extracted_token
        .removeprefix("Bearer ")
        .strip()
    )

    print(
        "[auth] Token desde archivo:",
        token_path,
    )

    print(
        "[auth] Fingerprint:",
        hashlib.sha256(
            normalized_token.encode(
                "utf-8"
            )
        ).hexdigest()[:12],
    )

    return normalized_token


# ==================================================
# SESIÓN HTTP
# ==================================================


def create_luca_http_session(
    token: str,
    total_retries: int = 3,
    backoff_factor: float = 0.5,
) -> Session:
    """
    Crea una sesión HTTP autenticada con reintentos.
    """

    if not token:
        raise ValueError(
            "Se requiere token para crear la sesión HTTP."
        )

    retry_strategy = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        status=total_retries,
        backoff_factor=backoff_factor,
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
        pool_connections=10,
        pool_maxsize=10,
    )

    session = requests.Session()

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
            "Accept": "application/json",
            "User-Agent": (
                "xapity-luca-reports-loader/1.0"
            ),
        }
    )

    return session


# ==================================================
# RESPUESTAS HTTP LUCA
# ==================================================


def _raise_for_luca_response(
    response: Response,
    *,
    report_type: str,
) -> None:
    """
    Genera errores descriptivos para respuestas inválidas de Luca.
    """

    if response.status_code == 401:
        raise RuntimeError(
            "Luca respondió 401 Unauthorized. "
            "El bearer token puede haber expirado."
        )

    if response.status_code == 403:
        raise RuntimeError(
            "Luca respondió 403 Forbidden. "
            "El usuario no tiene permisos para este reporte."
        )

    if response.status_code == 404:
        raise RuntimeError(
            "Luca respondió 404 Not Found. "
            "Revisa la URL, endpoint o businessId."
        )

    if response.status_code >= 400:
        response_preview = (
            response.text[:1_000]
        )

        raise RuntimeError(
            "Error consultando reporte en Luca. "
            f"report_type={report_type}, "
            f"status={response.status_code}, "
            f"response={response_preview}"
        )


# ==================================================
# BALANCE GENERAL — PARSEO
# ==================================================


def _normalize_general_balance_row(
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    Normaliza una fila del Balance General.

    Mantiene el contrato funcional entregado por Luca,
    pero asegura tipos homogéneos.
    """

    normalized: dict[str, Any] = {
        "nameCuenta": (
            _normalize_optional_string(
                row.get(
                    "nameCuenta"
                )
            )
        ),
        "numCuenta": (
            _normalize_optional_string(
                row.get(
                    "numCuenta"
                )
            )
        ),
        "debe": _safe_int(
            row.get(
                "debe"
            )
        ),
        "haber": _safe_int(
            row.get(
                "haber"
            )
        ),
        "deudor": _safe_int(
            row.get(
                "deudor"
            )
        ),
        "acreedor": _safe_int(
            row.get(
                "acreedor"
            )
        ),
        "activo": _safe_int(
            row.get(
                "activo"
            )
        ),
        "pasivo": _safe_int(
            row.get(
                "pasivo"
            )
        ),
        "perdida": _safe_int(
            row.get(
                "perdida"
            )
        ),
        "ganancia": _safe_int(
            row.get(
                "ganancia"
            )
        ),
    }

    return normalized


def _parse_general_balance_response(
    response: Response,
) -> list[dict[str, Any]]:
    """
    Valida y normaliza la respuesta del endpoint Balance General.
    """

    _raise_for_luca_response(
        response,
        report_type="general_balance",
    )

    try:
        payload = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Luca no retornó JSON válido para Balance General. "
            f"response={response.text[:1_000]}"
        ) from exc

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "La respuesta del Balance General debe ser "
            "una lista JSON."
        )

    normalized_rows: list[
        dict[str, Any]
    ] = []

    for index, row in enumerate(
        payload
    ):
        if not isinstance(
            row,
            dict,
        ):
            raise RuntimeError(
                "Cada fila del Balance General debe ser "
                "un objeto JSON. "
                f"index={index}"
            )

        normalized_rows.append(
            _normalize_general_balance_row(
                row
            )
        )

    return normalized_rows


# ==================================================
# BALANCE GENERAL — ESTRUCTURA
# ==================================================


def split_general_balance_rows(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Separa las cuentas contables de las filas resumen de Luca.

    Salida:

        accounts
        subtotal
        result
        totals
    """

    accounts: list[
        dict[str, Any]
    ] = []

    subtotal: dict[
        str,
        Any,
    ] | None = None

    result: dict[
        str,
        Any,
    ] | None = None

    totals: dict[
        str,
        Any,
    ] | None = None

    for row in rows:
        name = (
            _normalize_optional_string(
                row.get(
                    "nameCuenta"
                )
            )
        )

        if name == SUMMARY_ROW_SUBTOTAL:
            subtotal = dict(
                row
            )

            continue

        if name == SUMMARY_ROW_RESULT:
            result = dict(
                row
            )

            continue

        if name == SUMMARY_ROW_TOTALS:
            totals = dict(
                row
            )

            continue

        accounts.append(
            dict(
                row
            )
        )

    if subtotal is None:
        raise RuntimeError(
            "El Balance General no contiene la fila "
            "'Sub Totales'."
        )

    if result is None:
        raise RuntimeError(
            "El Balance General no contiene la fila "
            "'Resultado'."
        )

    if totals is None:
        raise RuntimeError(
            "El Balance General no contiene la fila "
            "'Totales'."
        )

    return {
        "accounts": accounts,
        "subtotal": subtotal,
        "result": result,
        "totals": totals,
    }


# ==================================================
# BALANCE GENERAL — SUMMARY
# ==================================================


def _top_accounts_by_field(
    *,
    accounts: list[dict[str, Any]],
    field: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Obtiene las cuentas con mayor valor para un campo determinado.
    """

    candidates: list[
        dict[str, Any]
    ] = []

    for account in accounts:
        amount = _safe_int(
            account.get(
                field
            )
        )

        if amount <= 0:
            continue

        candidates.append(
            {
                "numCuenta": account.get(
                    "numCuenta"
                ),
                "nameCuenta": account.get(
                    "nameCuenta"
                ),
                "amount": amount,
            }
        )

    candidates.sort(
        key=lambda item: item[
            "amount"
        ],
        reverse=True,
    )

    return candidates[:limit]


def build_general_balance_summary(
    report: dict[str, Any],
) -> dict[str, Any]:
    """
    Construye un resumen determinista del Balance General.

    No utiliza LLM ni interpreta semánticamente cuentas.

    Se limita a:

    - totales provistos por Luca;
    - validaciones matemáticas;
    - rankings simples por monto;
    - resultado calculado a partir de subtotal
      ganancia - pérdida.
    """

    accounts = report.get(
        "accounts"
    ) or []

    subtotal = report.get(
        "subtotal"
    ) or {}

    result = report.get(
        "result"
    ) or {}

    totals = report.get(
        "totals"
    ) or {}

    if not isinstance(
        accounts,
        list,
    ):
        raise TypeError(
            "report.accounts debe ser una lista."
        )

    if not isinstance(
        subtotal,
        dict,
    ):
        raise TypeError(
            "report.subtotal debe ser un objeto."
        )

    if not isinstance(
        result,
        dict,
    ):
        raise TypeError(
            "report.result debe ser un objeto."
        )

    if not isinstance(
        totals,
        dict,
    ):
        raise TypeError(
            "report.totals debe ser un objeto."
        )

    total_debit = _safe_int(
        totals.get(
            "debe"
        )
    )

    total_credit = _safe_int(
        totals.get(
            "haber"
        )
    )

    total_debtor = _safe_int(
        totals.get(
            "deudor"
        )
    )

    total_creditor = _safe_int(
        totals.get(
            "acreedor"
        )
    )

    total_assets = _safe_int(
        totals.get(
            "activo"
        )
    )

    total_liabilities = _safe_int(
        totals.get(
            "pasivo"
        )
    )

    total_loss = _safe_int(
        totals.get(
            "perdida"
        )
    )

    total_gain = _safe_int(
        totals.get(
            "ganancia"
        )
    )

    subtotal_gain = _safe_int(
        subtotal.get(
            "ganancia"
        )
    )

    subtotal_loss = _safe_int(
        subtotal.get(
            "perdida"
        )
    )

    calculated_period_result = (
        subtotal_gain
        - subtotal_loss
    )

    reported_result = {
        "debe": _safe_int(
            result.get(
                "debe"
            )
        ),
        "haber": _safe_int(
            result.get(
                "haber"
            )
        ),
        "deudor": _safe_int(
            result.get(
                "deudor"
            )
        ),
        "acreedor": _safe_int(
            result.get(
                "acreedor"
            )
        ),
        "activo": _safe_int(
            result.get(
                "activo"
            )
        ),
        "pasivo": _safe_int(
            result.get(
                "pasivo"
            )
        ),
        "perdida": _safe_int(
            result.get(
                "perdida"
            )
        ),
        "ganancia": _safe_int(
            result.get(
                "ganancia"
            )
        ),
    }

    balance_checks = {
        "debitEqualsCredit": (
            total_debit
            == total_credit
        ),
        "debtorEqualsCreditor": (
            total_debtor
            == total_creditor
        ),
        "assetsEqualLiabilities": (
            total_assets
            == total_liabilities
        ),
        "lossEqualsGain": (
            total_loss
            == total_gain
        ),
    }

    return {
        "accountsCount": len(
            accounts
        ),

        "totals": {
            "debit": total_debit,
            "credit": total_credit,
            "debtor": total_debtor,
            "creditor": total_creditor,
            "assets": total_assets,
            "liabilities": total_liabilities,
            "loss": total_loss,
            "gain": total_gain,
        },

        "subtotal": {
            "debit": _safe_int(
                subtotal.get(
                    "debe"
                )
            ),
            "credit": _safe_int(
                subtotal.get(
                    "haber"
                )
            ),
            "debtor": _safe_int(
                subtotal.get(
                    "deudor"
                )
            ),
            "creditor": _safe_int(
                subtotal.get(
                    "acreedor"
                )
            ),
            "assets": _safe_int(
                subtotal.get(
                    "activo"
                )
            ),
            "liabilities": _safe_int(
                subtotal.get(
                    "pasivo"
                )
            ),
            "loss": subtotal_loss,
            "gain": subtotal_gain,
        },

        "reportedResult": (
            reported_result
        ),

        "calculatedPeriodResult": (
            calculated_period_result
        ),

        "balanceChecks": (
            balance_checks
        ),

        "topAssets": (
            _top_accounts_by_field(
                accounts=accounts,
                field="activo",
            )
        ),

        "topLiabilities": (
            _top_accounts_by_field(
                accounts=accounts,
                field="pasivo",
            )
        ),

        "topLosses": (
            _top_accounts_by_field(
                accounts=accounts,
                field="perdida",
            )
        ),

        "topGains": (
            _top_accounts_by_field(
                accounts=accounts,
                field="ganancia",
            )
        ),

        "topDebtorBalances": (
            _top_accounts_by_field(
                accounts=accounts,
                field="deudor",
            )
        ),

        "topCreditorBalances": (
            _top_accounts_by_field(
                accounts=accounts,
                field="acreedor",
            )
        ),
    }


# ==================================================
# BALANCE GENERAL — FETCH
# ==================================================


def fetch_luca_general_balance(
    *,
    session: Session,
    business_id: int,
    query_from: str | date,
    query_to: str | date,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    api_base_url: str | None = None,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    """
    Consulta el Balance General de Luca para un rango de fechas.
    """

    if isinstance(
        business_id,
        bool,
    ) or not isinstance(
        business_id,
        int,
    ):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    (
        parsed_from,
        parsed_to,
    ) = _validate_date_range(
        query_from=query_from,
        query_to=query_to,
    )

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds debe ser mayor que cero."
        )

    base_url = (
        api_base_url.rstrip("/")
        if api_base_url
        else get_luca_api_base_url()
    )

    endpoint_path = (
        GENERAL_BALANCE_ENDPOINT_PATH.format(
            business_id=business_id
        )
    )

    url = (
        f"{base_url}{endpoint_path}"
    )

    params = {
        "queryFrom": (
            parsed_from.isoformat()
        ),
        "queryTo": (
            parsed_to.isoformat()
        ),
    }

    request_started = (
        time.perf_counter()
    )

    response = session.get(
        url,
        params=params,
        timeout=timeout_seconds,
    )

    elapsed_ms = round(
        (
            time.perf_counter()
            - request_started
        )
        * 1_000
    )

    rows = (
        _parse_general_balance_response(
            response
        )
    )

    trace = {
        "statusCode": (
            response.status_code
        ),
        "elapsedMs": elapsed_ms,
        "rowsReceived": len(
            rows
        ),
    }

    return (
        rows,
        trace,
    )


# ==================================================
# BALANCE GENERAL — LOAD
# ==================================================


def load_luca_general_balance(
    *,
    business_id: int | None = None,
    query_from: str | date,
    query_to: str | date,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    token: str | None = None,
    token_file: str | Path = DEFAULT_TOKEN_FILE,
    api_base_url: str | None = None,
    session: Session | None = None,
) -> LucaReportLoadResult:
    """
    Ejecuta la carga completa del Balance General:

        Luca API
        → validación
        → normalización
        → separación cuentas/resúmenes
        → summary determinista
        → resultado estructurado

    Esta función todavía NO persiste en Mongo.
    """

    resolved_business_id = (
        get_luca_business_id(
            business_id
        )
    )

    (
        parsed_from,
        parsed_to,
    ) = _validate_date_range(
        query_from=query_from,
        query_to=query_to,
    )

    owns_session = (
        session is None
    )

    if session is None:
        access_token = (
            load_luca_access_token(
                token=token,
                token_file=token_file,
            )
        )

        session = (
            create_luca_http_session(
                token=access_token
            )
        )

    load_started_at = (
        utc_now()
    )

    load_started_perf = (
        time.perf_counter()
    )

    try:
        (
            rows,
            request_trace,
        ) = fetch_luca_general_balance(
            session=session,
            business_id=resolved_business_id,
            query_from=parsed_from,
            query_to=parsed_to,
            timeout_seconds=timeout_seconds,
            api_base_url=api_base_url,
        )

        report = (
            split_general_balance_rows(
                rows
            )
        )

        summary = (
            build_general_balance_summary(
                report
            )
        )

        load_finished_at = (
            utc_now()
        )

        elapsed_ms = round(
            (
                time.perf_counter()
                - load_started_perf
            )
            * 1_000
        )

        metadata = {
            "businessId": (
                resolved_business_id
            ),
            "reportType": (
                "general_balance"
            ),
            "queryFrom": (
                parsed_from.isoformat()
            ),
            "queryTo": (
                parsed_to.isoformat()
            ),
            "source": (
                "luca-api"
            ),
            "endpoint": (
                "balance"
            ),
            "apiBaseUrl": (
                api_base_url.rstrip("/")
                if api_base_url
                else get_luca_api_base_url()
            ),
            "loadedAt": (
                load_finished_at.isoformat()
            ),
        }

        trace = {
            "startedAt": (
                load_started_at.isoformat()
            ),
            "finishedAt": (
                load_finished_at.isoformat()
            ),
            "elapsedMs": (
                elapsed_ms
            ),
            "rowsReceivedFromApi": (
                len(
                    rows
                )
            ),
            "accountsCount": (
                len(
                    report[
                        "accounts"
                    ]
                )
            ),
            "summaryRowsDetected": {
                "subtotal": (
                    report[
                        "subtotal"
                    ]
                    is not None
                ),
                "result": (
                    report[
                        "result"
                    ]
                    is not None
                ),
                "totals": (
                    report[
                        "totals"
                    ]
                    is not None
                ),
            },
            "request": (
                request_trace
            ),
        }

        return LucaReportLoadResult(
            metadata=metadata,
            report=report,
            summary=summary,
            trace=trace,
        )

    finally:
        if (
            owns_session
            and session is not None
        ):
            session.close()

# ==================================================
# BALANCE GENERAL — SYNC + MONGO
# ==================================================


def sync_luca_general_balance(
    *,
    business_id: int | None = None,
    query_from: str | date,
    query_to: str | date,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    token: str | None = None,
    token_file: str | Path = DEFAULT_TOKEN_FILE,
    api_base_url: str | None = None,
    requested_by: str | None = (
        "xapity-reports-loader"
    ),
) -> dict[str, Any]:
    """
    Ejecuta el flujo completo del Balance General:

        Luca API
        → validación
        → normalización
        → summary determinista
        → persistencia Mongo
    """

    load_result = (
        load_luca_general_balance(
            business_id=business_id,
            query_from=query_from,
            query_to=query_to,
            timeout_seconds=timeout_seconds,
            token=token,
            token_file=token_file,
            api_base_url=api_base_url,
        )
    )

    persistence_result = (
        persist_luca_report_snapshot(
            metadata=load_result.metadata,
            report=load_result.report,
            summary=load_result.summary,
            trace=load_result.trace,
            requested_by=requested_by,
        )
    )

    return {
        "load": {
            "metadata": (
                load_result.metadata
            ),
            "summary": (
                load_result.summary
            ),
            "trace": (
                load_result.trace
            ),
        },
        "persistence": (
            persistence_result
        ),
    }

# ==================================================
# CLI
# ==================================================


def build_parser() -> argparse.ArgumentParser:
    """
    Parser para pruebas manuales desde terminal.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Carga reportes contables desde Luca."
        ),
        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),
        epilog="""
Ejemplo:

  python3 -m data_loader.reportes_luca \\
      --business-id 70 \\
      --query-from 2026-01-01 \\
      --query-to 2026-09-04

Solo summary:

  python3 -m data_loader.reportes_luca \\
      --business-id 70 \\
      --query-from 2026-01-01 \\
      --query-to 2026-09-04 \\
      --summary
""",
    )

    parser.add_argument(
        "--business-id",
        type=int,
        required=False,
        default=None,
        help=(
            "Identificador de la empresa. "
            "Si se omite utiliza LUCA_BUSINESS_ID."
        ),
    )

    parser.add_argument(
        "--query-from",
        type=str,
        required=True,
        help=(
            "Fecha inicial YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--query-to",
        type=str,
        required=True,
        help=(
            "Fecha final YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help=(
            "Muestra solamente el summary determinista."
        ),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Mantiene salida JSON estructurada."
        ),
    )
    
    parser.add_argument(
        "--persist",
        action="store_true",
        help=(
            "Persiste el reporte sincronizado en MongoDB."
        ),
    )

    return parser


def main() -> None:
    """
    Punto de entrada para pruebas manuales.
    """

    parser = build_parser()

    args = parser.parse_args()

    if args.persist:
        result = sync_luca_general_balance(
            business_id=args.business_id,
            query_from=args.query_from,
            query_to=args.query_to,
        )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        return


    result = load_luca_general_balance(
        business_id=args.business_id,
        query_from=args.query_from,
        query_to=args.query_to,
    )

    if args.summary:
        payload: Any = (
            result.summary
        )

    else:
        payload = (
            result.to_dict()
        )

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()