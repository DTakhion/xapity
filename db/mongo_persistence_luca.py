# db/mongo_persistence_luca.py

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


load_dotenv()


_client: MongoClient | None = None


# ---------------------------------------------------------------------------
# Configuración general
# ---------------------------------------------------------------------------

DEFAULT_SOURCE = "luca-api"
DEFAULT_ENDPOINT = "summary-movements-specific"

# Campos que pueden cambiar por la fecha de consulta, pero no representan
# necesariamente un cambio real en el documento comercial.
HASH_IGNORED_FIELDS = {
    "diasHastaVencimiento",
}


def utc_now() -> datetime:
    """
    Retorna la fecha y hora actual en UTC con timezone explícita.
    """
    return datetime.now(timezone.utc)


def get_mongo_client() -> MongoClient:
    """
    Obtiene una instancia reutilizable de MongoClient.

    Variables requeridas:
        MONGO_URI
    """
    global _client

    if _client is None:
        mongo_uri = os.getenv("MONGO_URI")

        if not mongo_uri:
            raise RuntimeError("Falta variable MONGO_URI en .env")

        _client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=10_000,
            connectTimeoutMS=10_000,
        )

    return _client


def close_mongo_client() -> None:
    """
    Cierra explícitamente la conexión global de Mongo.
    """
    global _client

    if _client is not None:
        _client.close()
        _client = None


def get_luca_db() -> Database:
    """
    Obtiene la base de datos configurada para Xapity.

    Variables requeridas:
        MONGO_DB

    Ejemplo:
        MONGO_DB=clientRecommender
    """
    mongo_db = os.getenv("MONGO_DB")

    if not mongo_db:
        raise RuntimeError("Falta variable MONGO_DB en .env")

    return get_mongo_client()[mongo_db]


def check_mongo_connection() -> bool:
    """
    Verifica la conexión con MongoDB.
    """
    get_mongo_client().admin.command("ping")
    return True


# ---------------------------------------------------------------------------
# Colecciones
# ---------------------------------------------------------------------------

def get_luca_sales_runs_collection() -> Collection:
    """
    Registra cada ejecución del proceso de sincronización.
    """
    collection = get_luca_db()["luca_sales_runs"]

    collection.create_index(
        [("runId", ASCENDING)],
        unique=True,
        name="uq_luca_sales_run_id",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("year", ASCENDING),
            ("month", ASCENDING),
            ("type", ASCENDING),
            ("startedAt", DESCENDING),
        ],
        name="idx_luca_sales_runs_scope",
    )

    collection.create_index(
        [("status", ASCENDING), ("startedAt", DESCENDING)],
        name="idx_luca_sales_runs_status",
    )

    return collection


def get_luca_sales_items_collection() -> Collection:
    """
    Contiene el estado vigente de cada documento obtenido desde Luca.
    """
    collection = get_luca_db()["luca_sales_items"]

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("sourceKey", ASCENDING),
        ],
        unique=True,
        name="uq_luca_sales_item_source_key",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("year", ASCENDING),
            ("month", ASCENDING),
            ("type", ASCENDING),
        ],
        name="idx_luca_sales_items_period",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("customer.rut", ASCENDING),
        ],
        name="idx_luca_sales_items_customer_rut",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("status.raw", ASCENDING),
        ],
        name="idx_luca_sales_items_status",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("document.folio", ASCENDING),
        ],
        name="idx_luca_sales_items_folio",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("dates.issuedAt", DESCENDING),
        ],
        name="idx_luca_sales_items_issued_at",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("dates.dueAt", ASCENDING),
        ],
        name="idx_luca_sales_items_due_at",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("contentHash", ASCENDING),
        ],
        name="idx_luca_sales_items_hash",
    )

    return collection


def get_luca_sales_versions_collection() -> Collection:
    """
    Contiene el historial inmutable de versiones de cada documento.
    """
    collection = get_luca_db()["luca_sales_item_versions"]

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("sourceKey", ASCENDING),
            ("version", ASCENDING),
        ],
        unique=True,
        name="uq_luca_sales_item_version",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("sourceKey", ASCENDING),
            ("createdAt", DESCENDING),
        ],
        name="idx_luca_sales_versions_history",
    )

    collection.create_index(
        [("runId", ASCENDING)],
        name="idx_luca_sales_versions_run_id",
    )

    collection.create_index(
        [("snapshotId", ASCENDING)],
        name="idx_luca_sales_versions_snapshot_id",
    )

    return collection


def get_luca_sales_snapshots_collection() -> Collection:
    """
    Contiene una fotografía lógica completa por ejecución.
    """
    collection = get_luca_db()["luca_sales_snapshots"]

    collection.create_index(
        [("snapshotId", ASCENDING)],
        unique=True,
        name="uq_luca_sales_snapshot_id",
    )

    collection.create_index(
        [("runId", ASCENDING)],
        unique=True,
        name="uq_luca_sales_snapshot_run_id",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("year", ASCENDING),
            ("month", ASCENDING),
            ("type", ASCENDING),
            ("linkage", ASCENDING),
            ("createdAt", DESCENDING),
        ],
        name="idx_luca_sales_snapshot_scope",
    )

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("year", ASCENDING),
            ("month", ASCENDING),
            ("type", ASCENDING),
            ("linkage", ASCENDING),
            ("isActive", ASCENDING),
        ],
        name="idx_luca_sales_snapshot_active",
    )

    collection.create_index(
        [("snapshotHash", ASCENDING)],
        name="idx_luca_sales_snapshot_hash",
    )

    return collection


def get_luca_sales_summary_collection() -> Collection:
    """
    Contiene resúmenes calculados sobre los documentos sincronizados.
    """
    collection = get_luca_db()["luca_sales_summaries"]

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("year", ASCENDING),
            ("month", ASCENDING),
            ("type", ASCENDING),
            ("createdAt", DESCENDING),
        ],
        name="idx_luca_sales_summary_period",
    )

    collection.create_index(
        [("runId", ASCENDING)],
        name="idx_luca_sales_summary_run_id",
    )

    collection.create_index(
        [("snapshotId", ASCENDING)],
        name="idx_luca_sales_summary_snapshot_id",
    )

    return collection


def get_luca_reports_collection() -> Collection:
    """
    Contiene metadatos de reportes generados por Xapity.
    """
    collection = get_luca_db()["luca_reports"]

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("createdAt", DESCENDING),
        ],
        name="idx_luca_reports_business",
    )

    collection.create_index(
        [("runId", ASCENDING)],
        name="idx_luca_reports_run_id",
    )

    return collection


# ---------------------------------------------------------------------------
# Hash y serialización canónica
# ---------------------------------------------------------------------------

def _remove_ignored_fields(
    value: Any,
    ignored_fields: set[str] | None = None,
) -> Any:
    """
    Elimina recursivamente campos dinámicos que no deben afectar el hash.
    """
    ignored = ignored_fields or HASH_IGNORED_FIELDS

    if isinstance(value, dict):
        return {
            key: _remove_ignored_fields(item, ignored)
            for key, item in value.items()
            if key not in ignored
        }

    if isinstance(value, list):
        return [
            _remove_ignored_fields(item, ignored)
            for item in value
        ]

    return value


def canonical_json(value: Any) -> str:
    """
    Serializa una estructura de forma estable para calcular hashes.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def calculate_hash(value: Any) -> str:
    """
    Calcula SHA-256 sobre una estructura serializada canónicamente.
    """
    serialized = canonical_json(value)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def calculate_record_hash(record: dict[str, Any]) -> str:
    """
    Calcula el hash lógico de un documento comercial.

    Se excluyen campos dinámicos como diasHastaVencimiento.
    """
    stable_record = _remove_ignored_fields(record)
    return calculate_hash(stable_record)


def calculate_snapshot_hash(
    items: Iterable[dict[str, str]],
) -> str:
    """
    Calcula el hash global de un snapshot.

    Cada elemento debe contener:
        sourceKey
        contentHash
    """
    normalized_items = sorted(
        (
            {
                "sourceKey": item["sourceKey"],
                "contentHash": item["contentHash"],
            }
            for item in items
        ),
        key=lambda item: item["sourceKey"],
    )

    return calculate_hash(normalized_items)


# ---------------------------------------------------------------------------
# Claves e identificación
# ---------------------------------------------------------------------------

def build_source_key(
    business_id: int,
    record: dict[str, Any],
) -> str:
    """
    Construye una clave estable para un documento de Luca.

    Prioridad:
        1. idPrincipal
        2. id
        3. combinación de atributos de negocio
    """
    principal_id = record.get("idPrincipal")

    if principal_id is not None:
        return f"{business_id}|principal|{principal_id}"

    record_id = record.get("id")

    if record_id is not None:
        return f"{business_id}|id|{record_id}"

    document_code = record.get("code", "unknown")
    folio = record.get("folio") or record.get("numeroFolio") or "unknown"
    rut = record.get("rut", "unknown")
    issued_at = record.get("fecha", "unknown")

    fallback = {
        "businessId": business_id,
        "code": document_code,
        "folio": folio,
        "rut": rut,
        "fecha": issued_at,
    }

    fallback_hash = calculate_hash(fallback)[:24]

    return f"{business_id}|fallback|{fallback_hash}"


# ---------------------------------------------------------------------------
# Validaciones y transformaciones auxiliares
# ---------------------------------------------------------------------------

def _require_metadata(
    metadata: dict[str, Any],
    key: str,
) -> Any:
    value = metadata.get(key)

    if value is None:
        raise ValueError(f"Falta metadata requerida: {key}")

    return value


def _extract_item_projection(
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Extrae campos indexables y consultables sin eliminar el objeto raw.

    Esta proyección no reemplaza al registro original.
    """
    return {
        "document": {
            "id": record.get("id"),
            "principalId": record.get("idPrincipal"),
            "originId": record.get("idOrigin"),
            "folio": record.get("folio") or record.get("numeroFolio"),
            "code": record.get("code"),
            "name": record.get("nombreFolio"),
            "origin": record.get("nombreOrigen"),
            "query": record.get("query"),
        },
        "customer": {
            "id": record.get("idEmpresa"),
            "rut": record.get("rut"),
            "name": record.get("razonSocial"),
        },
        "dates": {
            "issuedAt": record.get("fecha"),
            "dueAt": record.get("fechaVencimiento") or None,
            "paidAt": record.get("fechaPago"),
        },
        "amounts": {
            "total": record.get("montoTotal"),
            "debit": record.get("debe"),
            "credit": record.get("haber"),
            "auxiliary": record.get("auxiliar"),
            "net": record.get("montoNetoLiquido"),
            "exempt": record.get("montoExento"),
            "withheldVat": record.get("montoIvaRetenido"),
        },
        "accounting": {
            "accountName": record.get("nombreCuenta"),
            "accountCode": record.get("codigoCuenta"),
            "processId": record.get("processId"),
            "voucher": record.get("comprobante"),
            "voucherType": record.get("tipoComprobante"),
            "originTable": record.get("origenTabla"),
        },
        "status": {
            "raw": record.get("status"),
        },
        "linkages": {
            "count": len(record.get("linkageCredito") or []),
            "hasLinkages": bool(record.get("linkageCredito")),
        },
    }


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def find_luca_sales_snapshot(
    business_id: int,
    year: int,
    month: int,
    type_: str,
    linkage: bool,
) -> dict[str, Any] | None:
    """
    Obtiene el último snapshot activo para un alcance determinado.
    """
    collection = get_luca_sales_snapshots_collection()

    return collection.find_one(
        {
            "businessId": business_id,
            "year": year,
            "month": month,
            "type": type_,
            "linkage": linkage,
            "isActive": True,
        },
        sort=[("createdAt", DESCENDING)],
    )


def find_luca_sales_item(
    business_id: int,
    source_key: str,
) -> dict[str, Any] | None:
    """
    Obtiene el estado vigente de un documento.
    """
    collection = get_luca_sales_items_collection()

    return collection.find_one(
        {
            "businessId": business_id,
            "sourceKey": source_key,
        }
    )


def find_luca_sales_item_history(
    business_id: int,
    source_key: str,
) -> list[dict[str, Any]]:
    """
    Obtiene el historial de versiones de un documento.
    """
    collection = get_luca_sales_versions_collection()

    return list(
        collection.find(
            {
                "businessId": business_id,
                "sourceKey": source_key,
            }
        ).sort("version", ASCENDING)
    )


# ---------------------------------------------------------------------------
# Persistencia principal
# ---------------------------------------------------------------------------

def persist_luca_sales_sync(
    *,
    metadata: dict[str, Any],
    records: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
    trace: dict[str, Any] | None = None,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """
    Persiste una ejecución completa de sincronización desde Luca.

    Espera metadata con al menos:
        businessId
        year
        month
        type
        linkage

    Opcionalmente:
        source
        endpoint
        max
        pagesCount

    Comportamiento:
        1. Crea un run.
        2. Calcula sourceKey y hash por registro.
        3. Actualiza el estado vigente.
        4. Inserta una versión solo cuando el documento cambia.
        5. Calcula e inserta el snapshot.
        6. Marca el run como completado.
    """
    business_id = int(_require_metadata(metadata, "businessId"))
    year = int(_require_metadata(metadata, "year"))
    month = int(_require_metadata(metadata, "month"))
    type_ = str(_require_metadata(metadata, "type"))
    linkage = bool(_require_metadata(metadata, "linkage"))

    source = metadata.get("source", DEFAULT_SOURCE)
    endpoint = metadata.get("endpoint", DEFAULT_ENDPOINT)

    run_id = str(uuid4())
    snapshot_id = str(uuid4())
    started_at = utc_now()

    runs_collection = get_luca_sales_runs_collection()
    items_collection = get_luca_sales_items_collection()
    versions_collection = get_luca_sales_versions_collection()
    snapshots_collection = get_luca_sales_snapshots_collection()

    scope = {
        "businessId": business_id,
        "year": year,
        "month": month,
        "type": type_,
        "linkage": linkage,
    }

    run_document = {
        "runId": run_id,
        "snapshotId": snapshot_id,
        **scope,
        "source": source,
        "endpoint": endpoint,
        "requestedBy": requested_by,
        "status": "running",
        "startedAt": started_at,
        "finishedAt": None,
        "recordsReceived": len(records),
        "recordsProcessed": 0,
        "recordsInserted": 0,
        "recordsUpdated": 0,
        "recordsUnchanged": 0,
        "versionsCreated": 0,
        "metadata": metadata,
        "trace": trace or {},
        "error": None,
        "createdAt": started_at,
        "updatedAt": started_at,
    }

    runs_collection.insert_one(run_document)

    inserted_count = 0
    updated_count = 0
    unchanged_count = 0
    versions_created = 0

    snapshot_items: list[dict[str, str]] = []

    try:
        for record in records:
            if not isinstance(record, dict):
                raise TypeError(
                    "Cada elemento de records debe ser un diccionario."
                )

            now = utc_now()
            source_key = build_source_key(business_id, record)
            content_hash = calculate_record_hash(record)

            existing = items_collection.find_one(
                {
                    "businessId": business_id,
                    "sourceKey": source_key,
                },
                {
                    "contentHash": 1,
                    "version": 1,
                    "firstSeenAt": 1,
                },
            )

            changed = (
                existing is None
                or existing.get("contentHash") != content_hash
            )

            if existing is None:
                version = 1
                inserted_count += 1
            elif changed:
                version = int(existing.get("version", 1)) + 1
                updated_count += 1
            else:
                version = int(existing.get("version", 1))
                unchanged_count += 1

            projection = _extract_item_projection(record)

            item_document = {
                "businessId": business_id,
                "sourceKey": source_key,
                "year": year,
                "month": month,
                "type": type_,
                "linkage": linkage,
                "source": source,
                "endpoint": endpoint,
                "runId": run_id,
                "snapshotId": snapshot_id,
                "contentHash": content_hash,
                "version": version,
                "lastSeenAt": now,
                "updatedAt": now,
                "isActive": True,
                **projection,
                "raw": record,
            }

            items_collection.update_one(
                {
                    "businessId": business_id,
                    "sourceKey": source_key,
                },
                {
                    "$set": item_document,
                    "$setOnInsert": {
                        "firstSeenAt": now,
                        "createdAt": now,
                    },
                    "$addToSet": {
                        "observedScopes": {
                            "year": year,
                            "month": month,
                            "type": type_,
                            "linkage": linkage,
                        }
                    },
                },
                upsert=True,
            )

            if changed:
                previous_hash = (
                    existing.get("contentHash")
                    if existing is not None
                    else None
                )

                version_document = {
                    "businessId": business_id,
                    "sourceKey": source_key,
                    "version": version,
                    "runId": run_id,
                    "snapshotId": snapshot_id,
                    "contentHash": content_hash,
                    "previousContentHash": previous_hash,
                    "changeType": (
                        "inserted"
                        if existing is None
                        else "updated"
                    ),
                    "source": source,
                    "endpoint": endpoint,
                    **scope,
                    **projection,
                    "raw": record,
                    "createdAt": now,
                }

                versions_collection.insert_one(version_document)
                versions_created += 1

            snapshot_items.append(
                {
                    "sourceKey": source_key,
                    "contentHash": content_hash,
                }
            )

        snapshot_hash = calculate_snapshot_hash(snapshot_items)
        finished_at = utc_now()

        previous_snapshot = snapshots_collection.find_one(
            {
                **scope,
                "isActive": True,
            },
            sort=[("createdAt", DESCENDING)],
        )

        previous_snapshot_hash = (
            previous_snapshot.get("snapshotHash")
            if previous_snapshot
            else None
        )

        snapshot_changed = previous_snapshot_hash != snapshot_hash

        snapshots_collection.update_many(
            {
                **scope,
                "isActive": True,
            },
            {
                "$set": {
                    "isActive": False,
                    "updatedAt": finished_at,
                    "deactivatedAt": finished_at,
                }
            },
        )

        snapshot_document = {
            "snapshotId": snapshot_id,
            "runId": run_id,
            **scope,
            "source": source,
            "endpoint": endpoint,
            "snapshotHash": snapshot_hash,
            "previousSnapshotHash": previous_snapshot_hash,
            "hasChanges": snapshot_changed,
            "recordsCount": len(records),
            "pagesCount": metadata.get("pagesCount"),
            "maxPerPage": metadata.get("max"),
            "sourceItems": snapshot_items,
            "summary": summary or {},
            "trace": trace or {},
            "requestedBy": requested_by,
            "requestedAt": started_at,
            "createdAt": finished_at,
            "updatedAt": finished_at,
            "isActive": True,
        }

        snapshots_collection.insert_one(snapshot_document)

        if summary is not None:
            insert_luca_sales_summary(
                {
                    **scope,
                    "runId": run_id,
                    "snapshotId": snapshot_id,
                    "snapshotHash": snapshot_hash,
                    "summary": summary,
                    "source": source,
                }
            )

        runs_collection.update_one(
            {"runId": run_id},
            {
                "$set": {
                    "status": "completed",
                    "finishedAt": finished_at,
                    "updatedAt": finished_at,
                    "recordsProcessed": len(records),
                    "recordsInserted": inserted_count,
                    "recordsUpdated": updated_count,
                    "recordsUnchanged": unchanged_count,
                    "versionsCreated": versions_created,
                    "snapshotHash": snapshot_hash,
                    "previousSnapshotHash": previous_snapshot_hash,
                    "hasChanges": snapshot_changed,
                }
            },
        )

        return {
            "runId": run_id,
            "snapshotId": snapshot_id,
            "snapshotHash": snapshot_hash,
            "previousSnapshotHash": previous_snapshot_hash,
            "hasChanges": snapshot_changed,
            "recordsReceived": len(records),
            "recordsProcessed": len(records),
            "recordsInserted": inserted_count,
            "recordsUpdated": updated_count,
            "recordsUnchanged": unchanged_count,
            "versionsCreated": versions_created,
        }

    except Exception as exc:
        failed_at = utc_now()

        runs_collection.update_one(
            {"runId": run_id},
            {
                "$set": {
                    "status": "failed",
                    "finishedAt": failed_at,
                    "updatedAt": failed_at,
                    "recordsProcessed": (
                        inserted_count
                        + updated_count
                        + unchanged_count
                    ),
                    "recordsInserted": inserted_count,
                    "recordsUpdated": updated_count,
                    "recordsUnchanged": unchanged_count,
                    "versionsCreated": versions_created,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            },
        )

        raise


# ---------------------------------------------------------------------------
# Persistencias complementarias
# ---------------------------------------------------------------------------

def insert_luca_sales_summary(
    summary: dict[str, Any],
) -> str:
    """
    Persiste un resumen derivado de una ejecución o snapshot.
    """
    collection = get_luca_sales_summary_collection()
    now = utc_now()

    document = {
        **summary,
        "createdAt": now,
        "updatedAt": now,
        "isActive": True,
    }

    result = collection.insert_one(document)

    return str(result.inserted_id)


def insert_luca_report_metadata(
    report: dict[str, Any],
) -> str:
    """
    Persiste los metadatos de un reporte generado por Xapity.
    """
    collection = get_luca_reports_collection()
    now = utc_now()

    document = {
        **report,
        "createdAt": now,
        "updatedAt": now,
        "isActive": True,
    }

    result = collection.insert_one(document)

    return str(result.inserted_id)