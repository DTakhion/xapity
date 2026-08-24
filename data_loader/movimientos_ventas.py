# data_loader/movimientos_ventas.py

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import hashlib

import requests
from dotenv import load_dotenv
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from db.mongo_persistence_luca import (
    build_source_key,
    calculate_record_hash,
    persist_luca_sales_sync,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)


DEFAULT_LUCA_API_BASE_URL = (
    "https://luca-api-dev-bvxil9xk.ue.gateway.dev"
)

DEFAULT_ENDPOINT_PATH = (
    "/v1/business/{business_id}/summary-movements-specific"
)

DEFAULT_TYPE = "ingreso"
DEFAULT_MONTH = 0
DEFAULT_MAX_PER_PAGE = 30
DEFAULT_LINKAGE = True

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_PAGES = 10_000
DEFAULT_TOKEN_FILE = ROOT_DIR / "results" / "luca_token.json"


# ---------------------------------------------------------------------------
# Modelos de resultado
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LucaSalesPageTrace:
    """
    Trazabilidad de una página consultada en Luca.
    """

    page: int
    requested_max: int
    response_count: int
    records_received: int
    elapsed_ms: int


@dataclass
class LucaSalesLoadResult:
    """
    Resultado completo de una carga paginada desde Luca.
    """

    metadata: dict[str, Any]
    records: list[dict[str, Any]]
    summary: dict[str, Any]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "records": self.records,
            "summary": self.summary,
            "trace": self.trace,
        }


# ---------------------------------------------------------------------------
# Fechas y utilidades
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_optional_string(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()

    return normalized or None


def _validate_month(month: int) -> None:
    if month < 0 or month > 12:
        raise ValueError(
            "month debe estar entre 0 y 12. "
            "Usa 0 para consultar todos los meses."
        )


def _validate_year(year: int) -> None:
    if year < 2000 or year > 2100:
        raise ValueError(
            f"year fuera de rango permitido: {year}"
        )


def _validate_positive_integer(
    value: int,
    name: str,
) -> None:
    if value <= 0:
        raise ValueError(
            f"{name} debe ser mayor que cero."
        )


# ---------------------------------------------------------------------------
# Configuración y token
# ---------------------------------------------------------------------------

def get_luca_business_id(
    business_id: int | None = None,
) -> int:
    """
    Obtiene el businessId desde argumento o desde LUCA_BUSINESS_ID.
    """
    if business_id is not None:
        if business_id <= 0:
            raise ValueError(
                "business_id debe ser mayor que cero."
            )

        return business_id

    raw_business_id = os.getenv("LUCA_BUSINESS_ID")

    if not raw_business_id:
        raise RuntimeError(
            "Falta LUCA_BUSINESS_ID en .env "
            "y no se proporcionó business_id."
        )

    try:
        parsed_business_id = int(raw_business_id)
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


def _extract_token_from_payload(
    payload: Any,
) -> str | None:
    """
    Busca un token en distintas estructuras posibles.

    Soporta, entre otras:
        {"accessToken": "..."}
        {"token": "..."}
        {"bearerToken": "..."}
        {"data": {"accessToken": "..."}}
    """
    if isinstance(payload, str):
        token = payload.strip()
        return token or None

    if not isinstance(payload, dict):
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
        value = payload.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    nested_keys = (
        "data",
        "result",
        "auth",
        "session",
        "user",
    )

    for key in nested_keys:
        nested_value = payload.get(key)
        token = _extract_token_from_payload(nested_value)

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
    4. archivo results/luca_token.json.
    """
    if token and token.strip():
        return token.strip().removeprefix("Bearer ").strip()

    env_token = (
        os.getenv("LUCA_ACCESS_TOKEN")
        or os.getenv("LUCA_BEARER_TOKEN")
    )

    if env_token and env_token.strip():
        return env_token.strip().removeprefix("Bearer ").strip()

    token_path = Path(token_file)

    if not token_path.exists():
        raise RuntimeError(
            "No se encontró token de Luca. "
            "Ejecuta scripts/login.py o define LUCA_ACCESS_TOKEN. "
            f"Archivo esperado: {token_path}"
        )

    try:
        with token_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"El archivo de token no contiene JSON válido: {token_path}"
        ) from exc

    extracted_token = _extract_token_from_payload(payload)

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
            normalized_token.encode("utf-8")
        ).hexdigest()[:12],
    )

    return normalized_token


# ---------------------------------------------------------------------------
# Sesión HTTP
# ---------------------------------------------------------------------------

def create_luca_http_session(
    token: str,
    total_retries: int = 3,
    backoff_factor: float = 0.5,
) -> Session:
    """
    Crea una sesión requests con autenticación y reintentos.

    Los reintentos se aplican a errores temporales:
        429
        500
        502
        503
        504
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
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
    )

    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "xapity-luca-sales-loader/1.0",
        }
    )

    return session


# ---------------------------------------------------------------------------
# Validación de respuesta
# ---------------------------------------------------------------------------

def _raise_for_luca_response(
    response: Response,
    page: int,
) -> None:
    """
    Genera errores descriptivos para respuestas inválidas.
    """
    if response.status_code == 401:
        raise RuntimeError(
            "Luca respondió 401 Unauthorized. "
            "El bearer token puede haber expirado."
        )

    if response.status_code == 403:
        raise RuntimeError(
            "Luca respondió 403 Forbidden. "
            "El usuario no tiene permisos para esta consulta."
        )

    if response.status_code == 404:
        raise RuntimeError(
            "Luca respondió 404 Not Found. "
            "Revisa la URL, endpoint o businessId."
        )

    if response.status_code >= 400:
        response_preview = response.text[:1_000]

        raise RuntimeError(
            "Error consultando Luca. "
            f"page={page}, "
            f"status={response.status_code}, "
            f"response={response_preview}"
        )


def _parse_luca_page_response(
    response: Response,
    page: int,
) -> tuple[int, list[dict[str, Any]]]:
    """
    Valida y extrae count/libros desde la respuesta.
    """
    _raise_for_luca_response(response, page)

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Luca no retornó JSON válido. "
            f"page={page}, response={response.text[:1_000]}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "La respuesta de Luca debe ser un objeto JSON. "
            f"page={page}"
        )

    if "libros" not in payload:
        raise RuntimeError(
            "La respuesta de Luca no contiene el atributo 'libros'. "
            f"page={page}"
        )

    libros = payload.get("libros")
    count = payload.get("count")

    if not isinstance(libros, list):
        raise RuntimeError(
            "El atributo 'libros' debe ser una lista. "
            f"page={page}"
        )

    if count is None:
        response_count = len(libros)
    else:
        try:
            response_count = int(count)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "El atributo 'count' debe ser numérico. "
                f"page={page}, count={count!r}"
            ) from exc

    for index, item in enumerate(libros):
        if not isinstance(item, dict):
            raise RuntimeError(
                "Cada elemento de 'libros' debe ser un objeto. "
                f"page={page}, index={index}"
            )

    return response_count, libros


# ---------------------------------------------------------------------------
# Consulta de una página
# ---------------------------------------------------------------------------

def fetch_luca_sales_page(
    *,
    session: Session,
    business_id: int,
    year: int,
    month: int,
    page: int,
    max_per_page: int = DEFAULT_MAX_PER_PAGE,
    type_: str = DEFAULT_TYPE,
    linkage: bool = DEFAULT_LINKAGE,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    api_base_url: str | None = None,
) -> tuple[list[dict[str, Any]], LucaSalesPageTrace]:
    """
    Consulta una página del endpoint de ventas/clientes.
    """
    _validate_year(year)
    _validate_month(month)
    _validate_positive_integer(max_per_page, "max_per_page")

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    if page < 0:
        raise ValueError(
            "page no puede ser negativo."
        )

    if not type_:
        raise ValueError(
            "type_ no puede estar vacío."
        )

    base_url = (
        api_base_url.rstrip("/")
        if api_base_url
        else get_luca_api_base_url()
    )

    endpoint_path = DEFAULT_ENDPOINT_PATH.format(
        business_id=business_id
    )

    url = f"{base_url}{endpoint_path}"

    params = {
        "type": type_,
        "month": month,
        "year": year,
        "max": max_per_page,
        "page": page,
        "linkage": str(linkage).lower(),
    }

    request_started = time.perf_counter()

    response = session.get(
        url,
        params=params,
        timeout=timeout_seconds,
    )

    elapsed_ms = round(
        (time.perf_counter() - request_started) * 1_000
    )

    response_count, libros = _parse_luca_page_response(
        response=response,
        page=page,
    )

    page_trace = LucaSalesPageTrace(
        page=page,
        requested_max=max_per_page,
        response_count=response_count,
        records_received=len(libros),
        elapsed_ms=elapsed_ms,
    )

    return libros, page_trace


# ---------------------------------------------------------------------------
# Deduplicación
# ---------------------------------------------------------------------------

def deduplicate_luca_sales_records(
    *,
    business_id: int,
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Deduplica por sourceKey.

    Si se encuentra la misma sourceKey con diferente contenido,
    conserva la última aparición y registra el conflicto.
    """
    records_by_key: dict[str, dict[str, Any]] = {}
    hashes_by_key: dict[str, str] = {}

    repeated_same_content = 0
    repeated_different_content = 0
    duplicate_keys: list[str] = []

    for record in records:
        source_key = build_source_key(
            business_id=business_id,
            record=record,
        )

        content_hash = calculate_record_hash(record)

        previous_hash = hashes_by_key.get(source_key)

        if previous_hash is not None:
            duplicate_keys.append(source_key)

            if previous_hash == content_hash:
                repeated_same_content += 1
            else:
                repeated_different_content += 1

        records_by_key[source_key] = record
        hashes_by_key[source_key] = content_hash

    deduplicated_records = list(records_by_key.values())

    deduplication_trace = {
        "recordsBeforeDeduplication": len(records),
        "recordsAfterDeduplication": len(deduplicated_records),
        "duplicatesDetected": (
            repeated_same_content
            + repeated_different_content
        ),
        "repeatedSameContent": repeated_same_content,
        "repeatedDifferentContent": repeated_different_content,
        "duplicateSourceKeys": sorted(set(duplicate_keys)),
    }

    return deduplicated_records, deduplication_trace


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

def build_luca_sales_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Construye un resumen determinista del universo cargado.

    No interpreta todavía conciliaciones ni todos los tipos posibles
    de linkageCredito. Conserva una clasificación segura y general.
    """
    total_amount = 0.0
    total_debit = 0.0
    total_credit = 0.0

    records_with_linkages = 0
    total_linkages = 0

    by_status: dict[str, dict[str, Any]] = {}
    by_document_type: dict[str, dict[str, Any]] = {}
    by_customer: dict[str, dict[str, Any]] = {}

    empty_due_date_count = 0
    paid_date_count = 0

    for record in records:
        amount = _safe_float(record.get("montoTotal"))
        debit = _safe_float(record.get("debe"))
        credit = _safe_float(record.get("haber"))

        total_amount += amount
        total_debit += debit
        total_credit += credit

        status = (
            _normalize_optional_string(record.get("status"))
            or "SIN ESTADO"
        )

        if status not in by_status:
            by_status[status] = {
                "status": status,
                "count": 0,
                "totalAmount": 0.0,
            }

        by_status[status]["count"] += 1
        by_status[status]["totalAmount"] += amount

        document_code = str(
            record.get("code")
            if record.get("code") is not None
            else "unknown"
        )

        if document_code not in by_document_type:
            by_document_type[document_code] = {
                "documentCode": record.get("code"),
                "documentName": record.get("nombreFolio"),
                "count": 0,
                "totalAmount": 0.0,
            }

        by_document_type[document_code]["count"] += 1
        by_document_type[document_code]["totalAmount"] += amount

        customer_rut = (
            _normalize_optional_string(record.get("rut"))
            or "SIN_RUT"
        )

        if customer_rut not in by_customer:
            by_customer[customer_rut] = {
                "customerId": record.get("idEmpresa"),
                "rut": record.get("rut"),
                "name": record.get("razonSocial"),
                "documentsCount": 0,
                "totalAmount": 0.0,
            }

        by_customer[customer_rut]["documentsCount"] += 1
        by_customer[customer_rut]["totalAmount"] += amount

        linkages = record.get("linkageCredito") or []

        if isinstance(linkages, list):
            linkage_count = len(linkages)
        else:
            linkage_count = 0

        if linkage_count > 0:
            records_with_linkages += 1
            total_linkages += linkage_count

        if not _normalize_optional_string(
            record.get("fechaVencimiento")
        ):
            empty_due_date_count += 1

        if _normalize_optional_string(record.get("fechaPago")):
            paid_date_count += 1

    customers = list(by_customer.values())

    customers.sort(
        key=lambda customer: customer["totalAmount"],
        reverse=True,
    )

    statuses = list(by_status.values())
    statuses.sort(
        key=lambda item: item["count"],
        reverse=True,
    )

    document_types = list(by_document_type.values())
    document_types.sort(
        key=lambda item: item["count"],
        reverse=True,
    )

    return {
        "totalRecords": len(records),
        "totalAmount": total_amount,
        "totalDebit": total_debit,
        "totalCredit": total_credit,
        "uniqueCustomers": len(by_customer),
        "recordsWithLinkages": records_with_linkages,
        "totalLinkages": total_linkages,
        "recordsWithoutDueDate": empty_due_date_count,
        "recordsWithPaidDate": paid_date_count,
        "byStatus": statuses,
        "byDocumentType": document_types,
        "topCustomersByAmount": customers[:20],
    }


# ---------------------------------------------------------------------------
# Carga paginada completa
# ---------------------------------------------------------------------------

def load_luca_sales_movements(
    *,
    business_id: int | None = None,
    year: int,
    month: int = DEFAULT_MONTH,
    type_: str = DEFAULT_TYPE,
    linkage: bool = DEFAULT_LINKAGE,
    max_per_page: int = DEFAULT_MAX_PER_PAGE,
    start_page: int = 0,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    token: str | None = None,
    token_file: str | Path = DEFAULT_TOKEN_FILE,
    api_base_url: str | None = None,
    session: Session | None = None,
    on_page_loaded: (
        Callable[[LucaSalesPageTrace], None] | None
    ) = None,
) -> LucaSalesLoadResult:
    """
    Carga todas las páginas de movimientos de ingreso desde Luca.

    La paginación termina cuando Luca retorna:

        {
            "count": 0,
            "libros": []
        }

    Se utiliza `libros == []` como criterio definitivo.
    """
    resolved_business_id = get_luca_business_id(business_id)

    _validate_year(year)
    _validate_month(month)
    _validate_positive_integer(max_per_page, "max_per_page")
    _validate_positive_integer(max_pages, "max_pages")

    if start_page < 0:
        raise ValueError(
            "start_page no puede ser negativo."
        )

    access_token: str | None = None
    owns_session = session is None

    if session is None:
        access_token = load_luca_access_token(
            token=token,
            token_file=token_file,
        )

        session = create_luca_http_session(
            token=access_token,
        )

    load_started_at = utc_now()
    load_started_perf = time.perf_counter()

    page_traces: list[LucaSalesPageTrace] = []
    collected_records: list[dict[str, Any]] = []

    current_page = start_page
    termination_reason: str | None = None
    empty_page: int | None = None

    try:
        for _ in range(max_pages):
            page_records, page_trace = fetch_luca_sales_page(
                session=session,
                business_id=resolved_business_id,
                year=year,
                month=month,
                page=current_page,
                max_per_page=max_per_page,
                type_=type_,
                linkage=linkage,
                timeout_seconds=timeout_seconds,
                api_base_url=api_base_url,
            )

            page_traces.append(page_trace)

            if on_page_loaded is not None:
                on_page_loaded(page_trace)

            if not page_records:
                termination_reason = "empty_page"
                empty_page = current_page
                break

            collected_records.extend(page_records)
            current_page += 1

        else:
            termination_reason = "max_pages_reached"

            raise RuntimeError(
                "Se alcanzó max_pages sin recibir una página vacía. "
                f"max_pages={max_pages}, "
                f"last_page={current_page}. "
                "La carga se detuvo para evitar un ciclo infinito."
            )

        (
            deduplicated_records,
            deduplication_trace,
        ) = deduplicate_luca_sales_records(
            business_id=resolved_business_id,
            records=collected_records,
        )

        summary = build_luca_sales_summary(
            deduplicated_records
        )

        load_finished_at = utc_now()
        elapsed_ms = round(
            (time.perf_counter() - load_started_perf) * 1_000
        )

        pages_with_records = sum(
            1
            for page_trace in page_traces
            if page_trace.records_received > 0
        )

        total_api_records = sum(
            page_trace.records_received
            for page_trace in page_traces
        )

        metadata = {
            "businessId": resolved_business_id,
            "year": year,
            "month": month,
            "type": type_,
            "linkage": linkage,
            "max": max_per_page,
            "startPage": start_page,
            "pagesCount": pages_with_records,
            "pagesRequested": len(page_traces),
            "source": "luca-api",
            "endpoint": "summary-movements-specific",
            "apiBaseUrl": (
                api_base_url.rstrip("/")
                if api_base_url
                else get_luca_api_base_url()
            ),
            "loadedAt": load_finished_at.isoformat(),
        }

        trace = {
            "startedAt": load_started_at.isoformat(),
            "finishedAt": load_finished_at.isoformat(),
            "elapsedMs": elapsed_ms,
            "terminationReason": termination_reason,
            "emptyPage": empty_page,
            "lastPageRequested": (
                page_traces[-1].page
                if page_traces
                else None
            ),
            "recordsReceivedFromApi": total_api_records,
            "recordsReturned": len(deduplicated_records),
            "deduplication": deduplication_trace,
            "pages": [
                asdict(page_trace)
                for page_trace in page_traces
            ],
        }

        return LucaSalesLoadResult(
            metadata=metadata,
            records=deduplicated_records,
            summary=summary,
            trace=trace,
        )

    finally:
        if owns_session and session is not None:
            session.close()


# ---------------------------------------------------------------------------
# Carga + persistencia
# ---------------------------------------------------------------------------

def sync_luca_sales_movements(
    *,
    business_id: int | None = None,
    year: int,
    month: int = DEFAULT_MONTH,
    type_: str = DEFAULT_TYPE,
    linkage: bool = DEFAULT_LINKAGE,
    max_per_page: int = DEFAULT_MAX_PER_PAGE,
    start_page: int = 0,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    token: str | None = None,
    token_file: str | Path = DEFAULT_TOKEN_FILE,
    api_base_url: str | None = None,
    requested_by: str | None = "xapity-sales-loader",
    on_page_loaded: (
        Callable[[LucaSalesPageTrace], None] | None
    ) = None,
) -> dict[str, Any]:
    """
    Ejecuta el flujo completo:

        Luca API
        → paginación
        → validación
        → deduplicación
        → resumen
        → persistencia Mongo
    """
    load_result = load_luca_sales_movements(
        business_id=business_id,
        year=year,
        month=month,
        type_=type_,
        linkage=linkage,
        max_per_page=max_per_page,
        start_page=start_page,
        max_pages=max_pages,
        timeout_seconds=timeout_seconds,
        token=token,
        token_file=token_file,
        api_base_url=api_base_url,
        on_page_loaded=on_page_loaded,
    )

    persistence_result = persist_luca_sales_sync(
        metadata=load_result.metadata,
        records=load_result.records,
        summary=load_result.summary,
        trace=load_result.trace,
        requested_by=requested_by,
    )

    return {
        "load": {
            "metadata": load_result.metadata,
            "summary": load_result.summary,
            "trace": load_result.trace,
        },
        "persistence": persistence_result,
    }