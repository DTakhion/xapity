# luca/sales_reconciliation_service.py

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


# ==================================================
# MODELOS
# ==================================================

@dataclass(frozen=True)
class SalesReconciliationContext:
    """
    Contexto común para consultas deterministas
    de conciliación comercial.
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

    Soporta ambas convenciones:

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
    Retorna la colección con el estado vigente
    de documentos de venta de Luca.
    """

    resolved_database = (
        database
        or get_mongo_database()
    )

    collection_name = os.getenv(
        "LUCA_SALES_ITEMS_COLLECTION",
        DEFAULT_ITEMS_COLLECTION,
    )

    return resolved_database[collection_name]


# ==================================================
# VALIDACIONES
# ==================================================

def _validate_business_id(
    business_id: int,
) -> None:
    if not isinstance(business_id, int):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )


def _validate_year(
    year: int | None,
) -> None:
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


def _validate_month(
    month: int | None,
) -> None:
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
) -> SalesReconciliationContext:
    _validate_business_id(business_id)
    _validate_year(year)
    _validate_month(month)

    return SalesReconciliationContext(
        business_id=business_id,
        year=year,
        month=month,
    )


# ==================================================
# NORMALIZACIÓN BÁSICA
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


# ==================================================
# RESOLUCIÓN DE CAMPOS
# ==================================================

def _get_nested_value(
    document: dict[str, Any],
    path: str,
) -> Any:
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
    for path in paths:
        value = _get_nested_value(
            document,
            path,
        )

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
            return datetime.strptime(
                text,
                date_format,
            )
        except ValueError:
            continue

    return None


def _extract_year(
    document: dict[str, Any],
) -> int | None:
    document_date = _extract_document_date(
        document
    )

    if document_date is not None:
        return document_date.year

    return _safe_int(
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


def _extract_month(
    document: dict[str, Any],
) -> int | None:
    """
    Extrae el mes calendario real del documento.

    Se privilegia fecha documental porque el month
    top-level puede corresponder al scope de extracción
    (por ejemplo, month=0).
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


def _extract_amount(
    document: dict[str, Any],
) -> float:
    return _safe_float(
        _first_value(
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


def _extract_folio(
    document: dict[str, Any],
) -> str | None:
    return _safe_string(
        _first_value(
            document,
            (
                "current.folio",
                "normalized.folio",
                "projection.folio",
                "raw.folio",
                "raw.numeroFolio",
            ),
        )
    )


def _extract_document_code(
    document: dict[str, Any],
) -> int | None:
    return _safe_int(
        _first_value(
            document,
            (
                "current.documentCode",
                "normalized.documentCode",
                "projection.documentCode",
                "raw.code",
                "raw.documentCode",
                "raw.tipoDocumento",
            ),
        )
    )


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


def _extract_status(
    document: dict[str, Any],
) -> str | None:
    """
    Estado comercial de Luca.

    Importante:
    este campo NO determina por sí mismo
    el estado de conciliación.
    """

    return _safe_string(
        _first_value(
            document,
            (
                "current.status",
                "normalized.status",
                "projection.status",
                "raw.status",
                "raw.estado",
            ),
        )
    )


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


# ==================================================
# LINKAGES DE CONCILIACIÓN
# ==================================================

def _normalize_linkage_list(
    value: Any,
) -> list[Any]:
    """
    Normaliza un campo linkage.

    Para esta primera versión:
    - lista con elementos => posee conciliación;
    - lista vacía / None / valor inválido => sin linkage.
    """

    if isinstance(value, list):
        return value

    return []


def _extract_linkage(
    document: dict[str, Any],
) -> list[Any]:
    """
    Extrae específicamente el linkage normal de Luca.
    """

    value = _first_value(
        document,
        (
            "raw.linkage",
            "current.linkage",
            "normalized.linkage",
        ),
        default=[],
    )

    return _normalize_linkage_list(value)


def _extract_linkage_credito(
    document: dict[str, Any],
) -> list[Any]:
    """
    Extrae específicamente linkageCredito de Luca.

    Se mantiene separado de linkage porque ambos
    participan en la definición de conciliación.
    """

    value = _first_value(
        document,
        (
            "raw.linkageCredito",
            "current.linkageCredito",
            "normalized.linkageCredito",
        ),
        default=[],
    )

    return _normalize_linkage_list(value)


def _is_document_unreconciled(
    document: dict[str, Any],
) -> bool:
    """
    Un documento está NO CONCILIADO cuando no posee
    información ni en linkage ni en linkageCredito.

    Esta condición es independiente del status comercial
    POR COBRAR / COBRADO.
    """

    linkage = _extract_linkage(document)
    linkage_credito = _extract_linkage_credito(
        document
    )

    return (
        len(linkage) == 0
        and len(linkage_credito) == 0
    )


# ==================================================
# FILTRO BASE
# ==================================================

def _build_mongo_business_filter(
    business_id: int,
) -> dict[str, Any]:
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
    context: SalesReconciliationContext,
) -> bool:
    document_business_id = _extract_business_id(
        document
    )

    if document_business_id != context.business_id:
        return False

    if context.year is not None:
        if _extract_year(document) != context.year:
            return False

    if context.month is not None:
        if _extract_month(document) != context.month:
            return False

    return True


def _load_current_documents(
    *,
    collection: Collection,
    context: SalesReconciliationContext,
) -> list[dict[str, Any]]:
    """
    Carga el estado vigente de documentos de venta
    para el businessId solicitado.
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
# NORMALIZACIÓN DE RESULTADOS
# ==================================================

def _normalize_document_result(
    document: dict[str, Any],
) -> dict[str, Any]:
    document_date = _extract_document_date(
        document
    )

    linkage = _extract_linkage(document)
    linkage_credito = _extract_linkage_credito(
        document
    )

    return {
        "sourceKey": _extract_source_key(document),
        "folio": _extract_folio(document),
        "documentCode": _extract_document_code(
            document
        ),
        "documentName": _extract_document_name(
            document
        ),
        "documentDate": (
            document_date.isoformat()
            if document_date
            else None
        ),
        "amount": _extract_amount(document),
        "status": _extract_status(document),
        "linkageCount": len(linkage),
        "linkageCreditoCount": len(
            linkage_credito
        ),
        "reconciliationStatus": "NO CONCILIADO",
    }


# ==================================================
# CONSULTA: CLIENTES NO CONCILIADOS
# ==================================================

def get_unreconciled_customers(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
    limit: int | None = 100,
) -> dict[str, Any]:
    """
    Responde preguntas como:

        ¿Qué clientes no tengo conciliados?
        ¿A quién no tengo conciliado?
        ¿Quiénes me faltan por conciliar?
        Muéstrame los clientes sin conciliar.

    Definición utilizada en esta primera capacidad:

    1. Un documento está NO CONCILIADO cuando:

           linkage == []
           AND
           linkageCredito == []

    2. Un cliente está NO CONCILIADO cuando TODOS los
       documentos considerados para ese cliente cumplen
       la condición anterior.

    Si al menos un documento del cliente posee información
    en linkage o linkageCredito, el cliente queda fuera de
    esta consulta.

    Esto evita clasificar como NO CONCILIADO a un cliente
    que podría encontrarse PARCIALMENTE CONCILIADO.

    El campo comercial status (POR COBRAR / COBRADO) no
    determina esta clasificación.
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

    # --------------------------------------------------
    # Agrupamos primero TODOS los documentos por cliente.
    #
    # Esto es importante:
    # no filtramos primero los documentos sin linkage,
    # porque podríamos clasificar incorrectamente como
    # NO CONCILIADO a un cliente parcialmente conciliado.
    # --------------------------------------------------

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

        normalized_key = (
            customer_key
            .strip()
            .upper()
        )

        if normalized_key not in customer_groups:
            customer_groups[normalized_key] = {
                "customerRut": customer_rut,
                "customerName": customer_name,
                "documents": [],
            }

        customer_groups[
            normalized_key
        ]["documents"].append(document)

    # --------------------------------------------------
    # Clasificación por cliente
    # --------------------------------------------------

    unreconciled_customers: list[
        dict[str, Any]
    ] = []

    for customer in customer_groups.values():
        customer_documents = customer[
            "documents"
        ]

        if not customer_documents:
            continue

        # CLAVE:
        # TODOS los documentos del cliente deben estar
        # completamente sin linkage.
        all_documents_unreconciled = all(
            _is_document_unreconciled(document)
            for document in customer_documents
        )

        if not all_documents_unreconciled:
            continue

        total_amount = sum(
            _extract_amount(document)
            for document in customer_documents
        )

        normalized_documents = [
            _normalize_document_result(document)
            for document in customer_documents
        ]

        # Orden determinista por fecha y folio.
        normalized_documents.sort(
            key=lambda item: (
                item["documentDate"] or "",
                item["folio"] or "",
            )
        )

        unreconciled_customers.append(
            {
                "customerRut": customer[
                    "customerRut"
                ],
                "customerName": customer[
                    "customerName"
                ],
                "reconciliationStatus": (
                    "NO CONCILIADO"
                ),
                "documentsCount": len(
                    customer_documents
                ),
                "totalAmount": total_amount,
                "documents": normalized_documents,
            }
        )

    # --------------------------------------------------
    # Orden:
    # mayor monto no conciliado primero.
    # --------------------------------------------------

    unreconciled_customers.sort(
        key=lambda item: (
            item["totalAmount"],
            item["documentsCount"],
        ),
        reverse=True,
    )

    total_customers_count = len(
        unreconciled_customers
    )

    total_documents_count = sum(
        customer["documentsCount"]
        for customer in unreconciled_customers
    )

    total_amount = sum(
        customer["totalAmount"]
        for customer in unreconciled_customers
    )

    returned_customers = (
        unreconciled_customers[:limit]
        if limit is not None
        else unreconciled_customers
    )

    return {
        "queryType": "unreconciled_customers",
        "businessId": context.business_id,
        "filters": {
            "year": context.year,
            "month": context.month,
            "limit": limit,
        },
        "result": {
            "customersCount": total_customers_count,
            "returnedCustomersCount": len(
                returned_customers
            ),
            "documentsCount": total_documents_count,
            "totalAmount": total_amount,
            "customers": returned_customers,
        },
        "metadata": {
            "source": DEFAULT_ITEMS_COLLECTION,
            "generatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "deterministic": True,
            "classification": {
                "unreconciledDocument": (
                    "linkage vacío AND linkageCredito vacío"
                ),
                "unreconciledCustomer": (
                    "todos los documentos del cliente "
                    "están no conciliados"
                ),
            },
        },
    }


# ==================================================
# CONSULTA: DOCUMENTOS PARA PROPOSE
# ==================================================

def get_unreconciled_documents_for_proposal(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    customer_rut: str | None = None,
    customer_name: str | None = None,
    collection: Collection | None = None,
) -> list[dict[str, Any]]:
    """
    Recupera documentos completos para el motor PROPOSE.

    Conserva la definición actual de cliente no conciliado:
    TODOS sus documentos deben tener linkage y
    linkageCredito vacíos dentro del período consultado.

    No aplica límites de presentación ni genera IDs.
    """

    context = _validate_context(
        business_id=business_id,
        year=year,
        month=month,
    )

    resolved_collection = (
        collection
        if collection is not None
        else get_sales_items_collection()
    )

    source_documents = _load_current_documents(
        collection=resolved_collection,
        context=context,
    )

    # Agrupación idéntica a la consulta existente.
    groups: dict[str, list[dict[str, Any]]] = {}

    for document in source_documents:
        rut = _extract_customer_rut(document)
        name = _extract_customer_name(document)

        key = (rut or name or "").strip().upper()

        if not key:
            continue

        groups.setdefault(key, []).append(document)

    selected: list[dict[str, Any]] = []

    requested_rut = (
        customer_rut.strip().upper()
        if customer_rut
        else None
    )

    requested_name = (
        customer_name.strip().upper()
        if customer_name
        else None
    )

    for group in groups.values():
        # No incorporar clientes parcialmente conciliados.
        if not all(
            _is_document_unreconciled(document)
            for document in group
        ):
            continue

        group_rut = _extract_customer_rut(group[0])
        group_name = _extract_customer_name(group[0])

        if requested_rut and (
            (group_rut or "").strip().upper()
            != requested_rut
        ):
            continue

        if requested_name and (
            (group_name or "").strip().upper()
            != requested_name
        ):
            continue

        for document in group:
            raw = document.get("raw")
            raw = raw if isinstance(raw, dict) else {}

            document_id = _first_value(
                document,
                (
                    "raw.idPrincipal",
                    "current.idPrincipal",
                    "normalized.idPrincipal",
                    "idPrincipal",
                ),
            )

            document_date = _extract_document_date(
                document
            )

            # Sin identificador real no podemos construir
            # una propuesta vinculable a Luca.
            if document_id is None or document_date is None:
                continue

            selected.append({
                "idPrincipal": document_id,
                "folio": _extract_folio(document),
                "fecha": document_date.isoformat(),
                "fechaVencimiento": _first_value(
                    document,
                    (
                        "raw.fechaVencimiento",
                        "current.dueDate",
                        "normalized.dueDate",
                    ),
                ),
                "rut": _extract_customer_rut(document),
                "razonSocial": _extract_customer_name(document),
                "montoTotal": _extract_amount(document),
                "code": _extract_document_code(document),
                "nombreFolio": _extract_document_name(document),
                "linkage": _extract_linkage(document),
                "linkageCredito": _extract_linkage_credito(
                    document
                ),
            })

    selected.sort(
        key=lambda item: (
            item["fecha"],
            str(item["folio"] or ""),
        )
    )

    return selected


# ==================================================
# PRUEBA MANUAL
# ==================================================

if __name__ == "__main__":
    import json

    result = get_unreconciled_customers(
        business_id=70,
        year=2026,
        limit=20,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )