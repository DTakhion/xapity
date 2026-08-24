# luca/sales_query_service.py

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


# ==================================================
# ENV / MONGO
# ==================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)


DEFAULT_ITEMS_COLLECTION = "luca_sales_items"

RECEIVABLE_STATUS = "POR COBRAR"
CREDIT_NOTE_DOCUMENT_CODE = 61


# ==================================================
# MODELOS
# ==================================================

@dataclass(frozen=True)
class SalesQueryContext:
    """
    Contexto común de una consulta comercial determinista.
    """

    business_id: int
    year: int | None = None
    month: int | None = None


# ==================================================
# CONEXIÓN
# ==================================================

def get_mongo_database() -> Database:
    """
    Retorna la base Mongo configurada para Xapity.

    Soporta ambas convenciones de variables para mantener
    compatibilidad con configuraciones anteriores:

        MONGO_URI / MONGO_DB
        MONGODB_URI / MONGODB_DB
    """
    mongo_uri = (
        os.getenv("MONGO_URI")
        or os.getenv("MONGODB_URI")
    )

    mongo_db = (
        os.getenv("MONGO_DB")
        or os.getenv("MONGODB_DB")
    )

    if not mongo_uri:
        raise RuntimeError(
            "Falta MONGO_URI o MONGODB_URI en .env."
        )

    if not mongo_db:
        raise RuntimeError(
            "Falta MONGO_DB o MONGODB_DB en .env."
        )

    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=10_000,
    )

    database = client[mongo_db]

    # Validación temprana de conectividad.
    database.command("ping")

    return database


def get_sales_items_collection(
    database: Database | None = None,
) -> Collection:
    """
    Retorna la colección con el estado vigente de ventas.
    """
    resolved_database = database or get_mongo_database()

    collection_name = os.getenv(
        "LUCA_SALES_ITEMS_COLLECTION",
        DEFAULT_ITEMS_COLLECTION,
    )

    return resolved_database[collection_name]


# ==================================================
# VALIDACIONES
# ==================================================

def _validate_business_id(business_id: int) -> None:
    if not isinstance(business_id, int):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )


def _validate_year(year: int | None) -> None:
    if year is None:
        return

    if not isinstance(year, int):
        raise TypeError(
            "year debe ser un entero o None."
        )

    if year < 2000 or year > 2100:
        raise ValueError(
            f"year fuera de rango permitido: {year}"
        )


def _validate_month(month: int | None) -> None:
    if month is None:
        return

    if not isinstance(month, int):
        raise TypeError(
            "month debe ser un entero o None."
        )

    if month < 1 or month > 12:
        raise ValueError(
            "month debe estar entre 1 y 12."
        )


def _validate_context(
    business_id: int,
    year: int | None,
    month: int | None,
) -> SalesQueryContext:
    _validate_business_id(business_id)
    _validate_year(year)
    _validate_month(month)

    return SalesQueryContext(
        business_id=business_id,
        year=year,
        month=month,
    )


# ==================================================
# NORMALIZACIÓN DE VALORES
# ==================================================

def _safe_int(
    value: Any,
    default: int | None = None,
) -> int | None:
    if value is None:
        return default

    if isinstance(value, bool):
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None:
        return default

    if isinstance(value, str):
        normalized = (
            value.strip()
            .replace("$", "")
            .replace(" ", "")
        )

        # Soporte básico para montos con separadores chilenos.
        if "," in normalized and "." in normalized:
            normalized = (
                normalized
                .replace(".", "")
                .replace(",", ".")
            )
        elif "," in normalized:
            normalized = normalized.replace(",", ".")

        value = normalized

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_string(
    value: Any,
    default: str | None = None,
) -> str | None:
    if value is None:
        return default

    normalized = str(value).strip()

    return normalized or default


def _normalize_status(value: Any) -> str:
    status = _safe_string(value, "SIN ESTADO")

    return str(status).upper()


def _normalize_document_code(value: Any) -> int | None:
    return _safe_int(value)


# ==================================================
# RESOLUCIÓN DE CAMPOS
# ==================================================

def _get_nested_value(
    document: dict[str, Any],
    path: str,
) -> Any:
    """
    Obtiene un valor usando una ruta con puntos.

    Ejemplo:
        _get_nested_value(doc, "current.amount")
    """
    current: Any = document

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        if part not in current:
            return None

        current = current[part]

    return current


def _first_value(
    document: dict[str, Any],
    paths: Iterable[str],
    default: Any = None,
) -> Any:
    """
    Retorna el primer valor no nulo encontrado entre varias rutas.

    Esto permite tolerar distintas versiones del esquema:
        current.amount
        normalized.amount
        raw.montoTotal
    """
    for path in paths:
        value = _get_nested_value(document, path)

        if value is not None:
            return value

    return default


def _extract_business_id(
    document: dict[str, Any],
) -> int | None:
    return _safe_int(
        _first_value(
            document,
            (
                "businessId",
                "metadata.businessId",
                "current.businessId",
                "normalized.businessId",
                "raw.businessId",
            ),
        )
    )


def _extract_year(
    document: dict[str, Any],
) -> int | None:
    direct_year = _safe_int(
        _first_value(
            document,
            (
                "year",
                "current.year",
                "normalized.year",
                "projection.year",
                "metadata.year",
                "raw.year",
            ),
        )
    )

    if direct_year is not None:
        return direct_year

    document_date = _extract_document_date(document)

    return document_date.year if document_date else None


def _extract_month(
    document: dict[str, Any],
) -> int | None:
    """
    Extrae el mes calendario real del documento.

    Prioriza la fecha documental porque el campo top-level
    ``month`` puede representar el scope utilizado durante
    la extracción (por ejemplo, 0 = todos los meses).
    """

    document_date = _extract_document_date(
        document
    )

    if document_date is not None:
        return document_date.month

    direct_month = _safe_int(
        _first_value(
            document,
            (
                "month",
                "current.month",
                "normalized.month",
                "projection.month",
                "metadata.month",
                "raw.month",
            ),
        )
    )

    if (
        direct_month is not None
        and 1 <= direct_month <= 12
    ):
        return direct_month

    return None


def _extract_document_date(
    document: dict[str, Any],
) -> datetime | None:
    value = _first_value(
        document,
        (
            "current.documentDate",
            "current.date",
            "normalized.documentDate",
            "normalized.date",
            "projection.documentDate",
            "projection.date",
            "raw.fecha",
            "raw.fechaDocumento",
            "raw.fechaEmision",
            "raw.fechaEmisión",
            "raw.detFchDoc",
        ),
    )

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    )

    for date_format in formats:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue

    return None

def _extract_due_date(
    document: dict[str, Any],
) -> datetime | None:
    """
    Extrae la fecha de vencimiento del documento.
    """

    value = _first_value(
        document,
        (
            "current.dueDate",
            "normalized.dueDate",
            "projection.dueDate",
            "raw.fechaVencimiento",
            "raw.dueDate",
            "raw.fechaVcto",
        ),
    )

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    )

    for date_format in formats:
        try:
            return datetime.strptime(
                text,
                date_format,
            )
        except ValueError:
            continue

    return None

def _extract_amount(
    document: dict[str, Any],
) -> float:
    value = _first_value(
        document,
        (
            "current.amount",
            "current.totalAmount",
            "normalized.amount",
            "normalized.totalAmount",
            "projection.amount",
            "projection.totalAmount",
            "raw.montoTotal",
            "raw.total",
            "raw.detMntTotal",
        ),
        default=0,
    )

    return _safe_float(value)


def _extract_status(
    document: dict[str, Any],
) -> str:
    value = _first_value(
        document,
        (
            "current.status",
            "normalized.status",
            "projection.status",
            "raw.status",
            "raw.estado",
        ),
        default="SIN ESTADO",
    )

    return _normalize_status(value)


def _extract_document_code(
    document: dict[str, Any],
) -> int | None:
    value = _first_value(
        document,
        (
            "current.documentCode",
            "current.code",
            "normalized.documentCode",
            "normalized.code",
            "projection.documentCode",
            "projection.code",
            "raw.code",
            "raw.documentCode",
            "raw.tipoDocumento",
        ),
    )

    return _normalize_document_code(value)


def _extract_document_name(
    document: dict[str, Any],
) -> str | None:
    return _safe_string(
        _first_value(
            document,
            (
                "current.documentName",
                "normalized.documentName",
                "projection.documentName",
                "raw.nombreFolio",
                "raw.documentName",
                "raw.nombreDocumento",
            ),
        )
    )


def _extract_customer_rut(
    document: dict[str, Any],
) -> str | None:
    return _safe_string(
        _first_value(
            document,
            (
                "current.customerRut",
                "normalized.customerRut",
                "projection.customerRut",
                "raw.rut",
                "raw.customerRut",
                "raw.detRutDoc",
            ),
        )
    )


def _extract_customer_name(
    document: dict[str, Any],
) -> str | None:
    return _safe_string(
        _first_value(
            document,
            (
                "current.customerName",
                "normalized.customerName",
                "projection.customerName",
                "raw.razonSocial",
                "raw.customerName",
                "raw.detRznSoc",
            ),
        )
    )


def _extract_linkages(
    document: dict[str, Any],
) -> list[Any]:
    value = _first_value(
        document,
        (
            "current.linkages",
            "normalized.linkages",
            "projection.linkages",
            "raw.linkageCredito",
            "raw.linkages",
        ),
        default=[],
    )

    return value if isinstance(value, list) else []


def _extract_source_key(
    document: dict[str, Any],
) -> str | None:
    return _safe_string(
        _first_value(
            document,
            (
                "sourceKey",
                "current.sourceKey",
                "normalized.sourceKey",
            ),
        )
    )

def _extract_company_id(
    document: dict[str, Any],
) -> int | None:
    return _safe_int(
        _first_value(
            document,
            (
                "current.companyId",
                "normalized.companyId",
                "projection.companyId",
                "raw.idEmpresa",
                "raw.companyId",
            ),
        )
    )


# ==================================================
# FILTRO BASE
# ==================================================

def _build_mongo_business_filter(
    business_id: int,
) -> dict[str, Any]:
    """
    Filtro compatible con distintas ubicaciones posibles
    del businessId en la persistencia.
    """
    return {
        "$or": [
            {"businessId": business_id},
            {"metadata.businessId": business_id},
            {"current.businessId": business_id},
            {"normalized.businessId": business_id},
            {"raw.businessId": business_id},
        ]
    }


def _document_matches_context(
    document: dict[str, Any],
    context: SalesQueryContext,
) -> bool:
    document_business_id = _extract_business_id(document)

    if document_business_id != context.business_id:
        return False

    if context.year is not None:
        document_year = _extract_year(document)

        if document_year != context.year:
            return False

    if context.month is not None:
        document_month = _extract_month(document)

        if document_month != context.month:
            return False

    return True


def _load_current_documents(
    *,
    collection: Collection,
    context: SalesQueryContext,
) -> list[dict[str, Any]]:
    """
    Consulta los documentos vigentes y aplica el filtro temporal
    de forma segura en Python.

    En esta primera versión privilegiamos compatibilidad con el
    esquema real persistido. Cuando confirmemos los nombres exactos,
    podremos mover year/month completamente al pipeline Mongo.
    """
    mongo_filter = _build_mongo_business_filter(
        context.business_id
    )

    documents = list(
        collection.find(
            mongo_filter,
            {
                "_id": 0,
            },
        )
    )

    return [
        document
        for document in documents
        if _document_matches_context(
            document,
            context,
        )
    ]


# ==================================================
# CLASIFICACIÓN COMERCIAL
# ==================================================

def _is_receivable(
    document: dict[str, Any],
) -> bool:
    return _extract_status(document) == RECEIVABLE_STATUS


def _is_credit_note(
    document: dict[str, Any],
) -> bool:
    return (
        _extract_document_code(document)
        == CREDIT_NOTE_DOCUMENT_CODE
    )


def _is_cancelled(
    document: dict[str, Any],
) -> bool:
    status = _extract_status(document)

    cancellation_tokens = (
        "ANULADO",
        "ANULA ",
        "ANULADA",
        "CANCELADO",
        "CANCELADA",
    )

    return any(
        token in status
        for token in cancellation_tokens
    )


def _has_linkage(
    document: dict[str, Any],
) -> bool:
    return len(_extract_linkages(document)) > 0


# ==================================================
# NORMALIZACIÓN PARA RESULTADOS
# ==================================================

def _normalize_document_result(
    document: dict[str, Any],
) -> dict[str, Any]:
    document_date = _extract_document_date(document)
    due_date = _extract_due_date(document)
    linkages = _extract_linkages(document)

    return {
        "sourceKey": _extract_source_key(document),
        "businessId": _extract_business_id(document),
        "year": _extract_year(document),
        "month": _extract_month(document),
        "documentDate": (
            document_date.isoformat()
            if document_date
            else None
        ),
        "dueDate": (
            due_date.isoformat()
            if due_date
            else None
        ),
        "documentCode": _extract_document_code(document),
        "documentName": _extract_document_name(document),
        "status": _extract_status(document),
        "amount": _extract_amount(document),
        "customerRut": _extract_customer_rut(document),
        "customerName": _extract_customer_name(document),
        "companyId": _extract_company_id(document),
        "linkagesCount": len(linkages),
    }


# ==================================================
# CONSULTA 1: OVERVIEW
# ==================================================

# SALES_OVERVIEW = "sales_overview" # “Dame un resumen de mis ventas”
def get_sales_overview(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Retorna una vista comercial determinista del estado vigente.

    Incluye:

    - documentos totales;
    - monto total;
    - documentos por cobrar;
    - monto por cobrar;
    - clientes únicos;
    - notas de crédito;
    - documentos anulados;
    - documentos con linkage.
    """
    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    total_amount = sum(
        _extract_amount(document)
        for document in documents
    )

    receivable_documents = [
        document
        for document in documents
        if _is_receivable(document)
    ]

    receivable_amount = sum(
        _extract_amount(document)
        for document in receivable_documents
    )

    credit_notes = [
        document
        for document in documents
        if _is_credit_note(document)
    ]

    cancelled_documents = [
        document
        for document in documents
        if _is_cancelled(document)
    ]

    linked_documents = [
        document
        for document in documents
        if _has_linkage(document)
    ]

    unique_customer_keys: set[str] = set()

    for document in documents:
        customer_rut = _extract_customer_rut(document)
        customer_name = _extract_customer_name(document)

        customer_key = (
            customer_rut
            or customer_name
        )

        if customer_key:
            unique_customer_keys.add(
                customer_key.upper()
            )

    statuses: dict[str, dict[str, Any]] = {}

    for document in documents:
        status = _extract_status(document)
        amount = _extract_amount(document)

        if status not in statuses:
            statuses[status] = {
                "status": status,
                "documentsCount": 0,
                "totalAmount": 0.0,
            }

        statuses[status]["documentsCount"] += 1
        statuses[status]["totalAmount"] += amount

    document_types: dict[str, dict[str, Any]] = {}

    for document in documents:
        document_code = _extract_document_code(document)
        document_name = _extract_document_name(document)
        amount = _extract_amount(document)

        key = (
            str(document_code)
            if document_code is not None
            else "unknown"
        )

        if key not in document_types:
            document_types[key] = {
                "documentCode": document_code,
                "documentName": document_name,
                "documentsCount": 0,
                "totalAmount": 0.0,
            }

        document_types[key]["documentsCount"] += 1
        document_types[key]["totalAmount"] += amount

    status_summary = sorted(
        statuses.values(),
        key=lambda item: (
            item["documentsCount"],
            item["totalAmount"],
        ),
        reverse=True,
    )

    document_type_summary = sorted(
        document_types.values(),
        key=lambda item: (
            item["documentsCount"],
            item["totalAmount"],
        ),
        reverse=True,
    )

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "queryType": "sales_overview",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
        },
        "result": {
            "totalDocuments": len(documents),
            "totalAmount": total_amount,
            "receivableDocuments": len(
                receivable_documents
            ),
            "receivableAmount": receivable_amount,
            "uniqueCustomers": len(
                unique_customer_keys
            ),
            "creditNotes": len(credit_notes),
            "cancelledDocuments": len(
                cancelled_documents
            ),
            "linkedDocuments": len(
                linked_documents
            ),
            "totalLinkages": sum(
                len(_extract_linkages(document))
                for document in documents
            ),
            "byStatus": status_summary,
            "byDocumentType": document_type_summary,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": generated_at,
            "deterministic": True,
        },
    }

def get_total_documents(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Responde:
        ¿Cuántos documentos de venta tengo?
        ¿Cuántas facturas tengo?
        ¿Cuál es el total de documentos comerciales?
    """

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    total_amount = sum(
        _extract_amount(document)
        for document in documents
    )

    return {
        "queryType": "total_documents",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
        },
        "result": {
            "documentsCount": len(documents),
            "totalAmount": total_amount,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }


# ==================================================
# CONSULTAS DETERMINISTAS BÁSICAS
# ==================================================

def get_total_receivable(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Responde:
        ¿Cuánto dinero tengo por cobrar?
        ¿Cuántas facturas tengo pendientes?
    """
    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    receivable_documents = [
        document
        for document in documents
        if _is_receivable(document)
    ]

    total_amount = sum(
        _extract_amount(document)
        for document in receivable_documents
    )

    return {
        "queryType": "total_receivable",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
            "status": RECEIVABLE_STATUS,
        },
        "result": {
            "documentsCount": len(
                receivable_documents
            ),
            "totalAmount": total_amount,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }

# ==================================================
# CONSULTA: DOCUMENTOS POR COBRAR
# ==================================================

def get_receivable_documents(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
    limit: int | None = 100,
) -> dict[str, Any]:
    """
    Responde:
        ¿Qué facturas tengo pendientes?
        ¿Qué documentos tengo por cobrar?

    Retorna documentos pendientes de cobro junto con
    sus hechos comerciales básicos.

    ``limit=None`` permite obtener todos los documentos,
    útil para capas analíticas posteriores.
    """

    if limit is not None and limit <= 0:
        raise ValueError(
            "limit debe ser mayor que cero o None."
        )

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    receivable_documents = [
        document
        for document in documents
        if _is_receivable(document)
    ]

    total_amount = sum(
        _extract_amount(document)
        for document in receivable_documents
    )

    # Orden factual:
    # primero los vencimientos más antiguos.
    receivable_documents.sort(
        key=lambda document: (
            _extract_due_date(document)
            or datetime.max.replace(
                tzinfo=timezone.utc
            )
        )
    )

    normalized_documents = [
        _normalize_document_result(document)
        for document in receivable_documents
    ]

    returned_documents = (
        normalized_documents[:limit]
        if limit is not None
        else normalized_documents
    )

    return {
        "queryType": "receivable_documents",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
            "status": RECEIVABLE_STATUS,
            "limit": limit,
        },
        "result": {
            "documentsCount": len(
                receivable_documents
            ),
            "returnedDocumentsCount": len(
                returned_documents
            ),
            "totalAmount": total_amount,
            "documents": returned_documents,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }


def get_credit_notes(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Responde:
        ¿Cuántas notas de crédito existen?
        Muéstrame las notas de crédito.
    """
    if limit <= 0:
        raise ValueError(
            "limit debe ser mayor que cero."
        )

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    credit_notes = [
        document
        for document in documents
        if _is_credit_note(document)
    ]

    credit_notes.sort(
        key=_extract_amount,
        reverse=True,
    )

    return {
        "queryType": "credit_notes",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
            "documentCode": CREDIT_NOTE_DOCUMENT_CODE,
            "limit": limit,
        },
        "result": {
            "documentsCount": len(credit_notes),
            "totalAmount": sum(
                _extract_amount(document)
                for document in credit_notes
            ),
            "documents": [
                _normalize_document_result(document)
                for document in credit_notes[:limit]
            ],
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }


def get_cancelled_documents(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Responde:
        ¿Qué documentos están anulados?
    """
    if limit <= 0:
        raise ValueError(
            "limit debe ser mayor que cero."
        )

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    cancelled_documents = [
        document
        for document in documents
        if _is_cancelled(document)
    ]

    cancelled_documents.sort(
        key=_extract_amount,
        reverse=True,
    )

    return {
        "queryType": "cancelled_documents",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
            "limit": limit,
        },
        "result": {
            "documentsCount": len(
                cancelled_documents
            ),
            "totalAmount": sum(
                _extract_amount(document)
                for document in cancelled_documents
            ),
            "documents": [
                _normalize_document_result(document)
                for document in cancelled_documents[:limit]
            ],
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }

# ==================================================
# CONSULTA: VENTAS MENSUALES
# ==================================================

def get_monthly_sales(
    *,
    business_id: int,
    year: int,
    month: int,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Responde:
        ¿Cuánto vendí en un mes determinado?
        ¿Cuánto vendí el mes pasado?
    """

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    total_amount = sum(
        _extract_amount(document)
        for document in documents
    )

    return {
        "queryType": "monthly_sales",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
        },
        "result": {
            "documentsCount": len(documents),
            "totalAmount": total_amount,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }

# ==================================================
# CONSULTA: TENDENCIA DE VENTAS
# ==================================================

def get_sales_trend(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Responde:
        ¿Cómo vienen evolucionando mis ventas?
        ¿Cuál ha sido la tendencia de mis ventas?

    Retorna una serie cronológica mensual determinista.
    """

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    monthly_groups: dict[
        tuple[int, int],
        dict[str, Any],
    ] = {}

    for document in documents:
        document_year = _extract_year(document)
        document_month = _extract_month(document)

        if (
            document_year is None
            or document_month is None
        ):
            continue

        key = (
            document_year,
            document_month,
        )

        if key not in monthly_groups:
            monthly_groups[key] = {
                "year": document_year,
                "month": document_month,
                "documentsCount": 0,
                "totalAmount": 0.0,
            }

        monthly_groups[key][
            "documentsCount"
        ] += 1

        monthly_groups[key][
            "totalAmount"
        ] += _extract_amount(document)

    periods = sorted(
        monthly_groups.values(),
        key=lambda item: (
            item["year"],
            item["month"],
        ),
    )

    return {
        "queryType": "sales_trend",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
        },
        "result": {
            "periodsCount": len(periods),
            "periods": periods,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }

# ==================================================
# CONSULTA: VENTAS MENSUALES POR CLIENTE
# ==================================================

def get_monthly_sales_by_customer(
    *,
    business_id: int,
    year: int,
    month: int,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Retorna las ventas de un mes agrupadas por cliente.

    Esta consulta entrega hechos deterministas que pueden
    utilizarse posteriormente para explicar variaciones
    y construir propuestas comerciales.
    """

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        or get_sales_items_collection()
    )

    documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    customer_groups: dict[
        str,
        dict[str, Any],
    ] = {}

    for document in documents:
        customer_rut = _extract_customer_rut(
            document
        )

        customer_name = _extract_customer_name(
            document
        )

        customer_key = (
            customer_rut
            or customer_name
        )

        if not customer_key:
            continue

        normalized_key = customer_key.upper()

        if normalized_key not in customer_groups:
            customer_groups[normalized_key] = {
                "customerRut": customer_rut,
                "customerName": customer_name,
                "documentsCount": 0,
                "totalAmount": 0.0,
            }

        customer_groups[normalized_key][
            "documentsCount"
        ] += 1

        customer_groups[normalized_key][
            "totalAmount"
        ] += _extract_amount(document)

    customers = sorted(
        customer_groups.values(),
        key=lambda item: item["totalAmount"],
        reverse=True,
    )

    total_amount = sum(
        item["totalAmount"]
        for item in customers
    )

    return {
        "queryType": "monthly_sales_by_customer",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
        },
        "result": {
            "customersCount": len(customers),
            "documentsCount": len(documents),
            "totalAmount": total_amount,
            "customers": customers,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
        },
    }