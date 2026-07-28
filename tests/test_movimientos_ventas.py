# tests/test_movimientos_ventas.py

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from data_loader.movimientos_ventas import (
    LucaSalesPageTrace,
    load_luca_sales_movements,
    sync_luca_sales_movements,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = ROOT_DIR / "results"


# ==================================================
# ARGUMENTOS
# ==================================================

def parse_bool(value: str) -> bool:
    """
    Convierte valores CLI comunes a booleano.
    """
    normalized = value.strip().lower()

    if normalized in {"true", "1", "yes", "y", "si", "sí"}:
        return True

    if normalized in {"false", "0", "no", "n"}:
        return False

    raise argparse.ArgumentTypeError(
        f"Valor booleano inválido: {value}. "
        "Usa true o false."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prueba E2E del loader de movimientos de ventas de Luca."
        )
    )

    parser.add_argument(
        "--business-id",
        type=int,
        default=None,
        help=(
            "Business ID de Luca. "
            "Si se omite, se usa LUCA_BUSINESS_ID desde .env."
        ),
    )

    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Año de consulta. Ejemplo: 2026.",
    )

    parser.add_argument(
        "--month",
        type=int,
        default=0,
        help=(
            "Mes de consulta: 1-12. "
            "Usa 0 para consultar todos los meses del año."
        ),
    )

    parser.add_argument(
        "--type",
        dest="type_",
        type=str,
        default="ingreso",
        help="Tipo de movimiento. Default: ingreso.",
    )

    parser.add_argument(
        "--linkage",
        type=parse_bool,
        default=True,
        help=(
            "Solicita relaciones con otros documentos. "
            "Default: true."
        ),
    )

    parser.add_argument(
        "--max",
        dest="max_per_page",
        type=int,
        default=30,
        help="Cantidad máxima de registros por página. Default: 30.",
    )

    parser.add_argument(
        "--start-page",
        type=int,
        default=0,
        help="Página inicial. Default: 0.",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=10_000,
        help=(
            "Seguro máximo de páginas para evitar ciclos infinitos. "
            "Default: 10000."
        ),
    )

    parser.add_argument(
        "--timeout",
        dest="timeout_seconds",
        type=int,
        default=60,
        help="Timeout HTTP por solicitud en segundos. Default: 60.",
    )

    parser.add_argument(
        "--persist",
        action="store_true",
        help=(
            "Persiste los movimientos, versiones, snapshot y run "
            "en MongoDB."
        ),
    )

    parser.add_argument(
        "--requested-by",
        type=str,
        default="tests/test_movimientos_ventas.py",
        help="Identificador del ejecutor para la trazabilidad.",
    )

    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Guarda el resultado de la prueba en results/.",
    )

    parser.add_argument(
        "--include-records",
        action="store_true",
        help=(
            "Incluye todos los registros en el JSON exportado. "
            "Puede generar un archivo grande."
        ),
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directorio de salida. Default: results/.",
    )

    return parser


# ==================================================
# SERIALIZACIÓN
# ==================================================

def json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return str(value)


def save_result_json(
    *,
    payload: dict[str, Any],
    results_dir: Path,
    business_id: int,
    year: int,
    month: int,
    persist: bool,
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "persisted" if persist else "load_only"

    output_path = results_dir / (
        f"movimientos_ventas_"
        f"business_{business_id}_"
        f"{year}_"
        f"month_{month}_"
        f"{mode}_"
        f"{timestamp}.json"
    )

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )

    return output_path


# ==================================================
# IMPRESIÓN
# ==================================================

def format_clp(value: Any) -> str:
    """
    Formatea un monto usando separador de miles.
    """
    try:
        numeric_value = round(float(value))
    except (TypeError, ValueError):
        numeric_value = 0

    return f"${numeric_value:,.0f}".replace(",", ".")


def print_page_progress(trace: LucaSalesPageTrace) -> None:
    """
    Callback ejecutado después de cargar cada página.
    """
    print(
        f"Página {trace.page:>4} | "
        f"count={trace.response_count:>3} | "
        f"registros={trace.records_received:>3} | "
        f"{trace.elapsed_ms:>6} ms"
    )


def print_header(args: argparse.Namespace) -> None:
    print()
    print("=== TEST MOVIMIENTOS VENTAS LUCA ===")
    print(f"businessId      : {args.business_id or 'ENV'}")
    print(f"year            : {args.year}")
    print(f"month           : {args.month}")
    print(f"type            : {args.type_}")
    print(f"linkage         : {args.linkage}")
    print(f"max por página  : {args.max_per_page}")
    print(f"página inicial  : {args.start_page}")
    print(f"persistir       : {args.persist}")
    print()


def print_load_summary(load_data: dict[str, Any]) -> None:
    metadata = load_data.get("metadata", {})
    summary = load_data.get("summary", {})
    trace = load_data.get("trace", {})
    deduplication = trace.get("deduplication", {})

    print()
    print("--- CARGA ---")
    print(f"businessId              : {metadata.get('businessId')}")
    print(f"páginas con registros   : {metadata.get('pagesCount')}")
    print(f"páginas solicitadas     : {metadata.get('pagesRequested')}")
    print(f"última página solicitada: {trace.get('lastPageRequested')}")
    print(f"página vacía            : {trace.get('emptyPage')}")
    print(f"término                  : {trace.get('terminationReason')}")
    print(f"tiempo total             : {trace.get('elapsedMs')} ms")

    print()
    print("--- REGISTROS ---")
    print(
        "recibidos desde API     : "
        f"{trace.get('recordsReceivedFromApi')}"
    )
    print(
        "antes de deduplicar     : "
        f"{deduplication.get('recordsBeforeDeduplication')}"
    )
    print(
        "después de deduplicar   : "
        f"{deduplication.get('recordsAfterDeduplication')}"
    )
    print(
        "duplicados detectados   : "
        f"{deduplication.get('duplicatesDetected')}"
    )
    print(
        "duplicados iguales      : "
        f"{deduplication.get('repeatedSameContent')}"
    )
    print(
        "duplicados distintos    : "
        f"{deduplication.get('repeatedDifferentContent')}"
    )

    print()
    print("--- RESUMEN COMERCIAL ---")
    print(f"documentos               : {summary.get('totalRecords')}")
    print(
        "monto total             : "
        f"{format_clp(summary.get('totalAmount'))}"
    )
    print(f"clientes únicos          : {summary.get('uniqueCustomers')}")
    print(
        "documentos vinculados   : "
        f"{summary.get('recordsWithLinkages')}"
    )
    print(f"vinculaciones totales    : {summary.get('totalLinkages')}")
    print(
        "sin fecha vencimiento   : "
        f"{summary.get('recordsWithoutDueDate')}"
    )
    print(
        "con fecha de pago       : "
        f"{summary.get('recordsWithPaidDate')}"
    )

    print()
    print("--- ESTADOS ---")

    statuses = summary.get("byStatus") or []

    if not statuses:
        print("Sin estados.")
    else:
        for status in statuses:
            print(
                f"{status.get('status', 'SIN ESTADO')}: "
                f"{status.get('count', 0)} documentos | "
                f"{format_clp(status.get('totalAmount'))}"
            )

    print()
    print("--- TIPOS DE DOCUMENTO ---")

    document_types = summary.get("byDocumentType") or []

    if not document_types:
        print("Sin tipos de documento.")
    else:
        for document_type in document_types:
            print(
                f"code={document_type.get('documentCode')} | "
                f"{document_type.get('documentName')} | "
                f"{document_type.get('count', 0)} documentos | "
                f"{format_clp(document_type.get('totalAmount'))}"
            )

    print()
    print("--- TOP CLIENTES POR MONTO ---")

    top_customers = summary.get("topCustomersByAmount") or []

    if not top_customers:
        print("Sin clientes.")
    else:
        for index, customer in enumerate(
            top_customers[:10],
            start=1,
        ):
            print(
                f"{index:>2}. "
                f"{customer.get('name')} | "
                f"RUT={customer.get('rut')} | "
                f"documentos={customer.get('documentsCount')} | "
                f"{format_clp(customer.get('totalAmount'))}"
            )


def print_persistence_summary(
    persistence: dict[str, Any],
) -> None:
    print()
    print("--- PERSISTENCIA MONGO ---")
    print(f"runId                  : {persistence.get('runId')}")
    print(f"snapshotId             : {persistence.get('snapshotId')}")
    print(f"snapshotHash           : {persistence.get('snapshotHash')}")
    print(
        "previousSnapshotHash   : "
        f"{persistence.get('previousSnapshotHash')}"
    )
    print(f"hasChanges             : {persistence.get('hasChanges')}")
    print(
        "registros recibidos    : "
        f"{persistence.get('recordsReceived')}"
    )
    print(
        "registros procesados   : "
        f"{persistence.get('recordsProcessed')}"
    )
    print(
        "registros insertados   : "
        f"{persistence.get('recordsInserted')}"
    )
    print(
        "registros actualizados : "
        f"{persistence.get('recordsUpdated')}"
    )
    print(
        "registros sin cambios  : "
        f"{persistence.get('recordsUnchanged')}"
    )
    print(
        "versiones creadas      : "
        f"{persistence.get('versionsCreated')}"
    )


# ==================================================
# EJECUCIÓN
# ==================================================

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.business_id is not None and args.business_id <= 0:
        parser.error("--business-id debe ser mayor que cero.")

    if args.month < 0 or args.month > 12:
        parser.error("--month debe estar entre 0 y 12.")

    if args.max_per_page <= 0:
        parser.error("--max debe ser mayor que cero.")

    if args.start_page < 0:
        parser.error("--start-page no puede ser negativo.")

    if args.max_pages <= 0:
        parser.error("--max-pages debe ser mayor que cero.")

    if args.timeout_seconds <= 0:
        parser.error("--timeout debe ser mayor que cero.")

    print_header(args)

    if args.persist:
        result = sync_luca_sales_movements(
            business_id=args.business_id,
            year=args.year,
            month=args.month,
            type_=args.type_,
            linkage=args.linkage,
            max_per_page=args.max_per_page,
            start_page=args.start_page,
            max_pages=args.max_pages,
            timeout_seconds=args.timeout_seconds,
            requested_by=args.requested_by,
            on_page_loaded=print_page_progress,
        )

        load_data = result["load"]
        persistence_data = result["persistence"]

        print_load_summary(load_data)
        print_persistence_summary(persistence_data)

        business_id = int(
            load_data["metadata"]["businessId"]
        )

        output_payload: dict[str, Any] = {
            "load": load_data,
            "persistence": persistence_data,
        }

    else:
        load_result = load_luca_sales_movements(
            business_id=args.business_id,
            year=args.year,
            month=args.month,
            type_=args.type_,
            linkage=args.linkage,
            max_per_page=args.max_per_page,
            start_page=args.start_page,
            max_pages=args.max_pages,
            timeout_seconds=args.timeout_seconds,
            on_page_loaded=print_page_progress,
        )

        load_data = {
            "metadata": load_result.metadata,
            "summary": load_result.summary,
            "trace": load_result.trace,
        }

        print_load_summary(load_data)

        business_id = int(
            load_result.metadata["businessId"]
        )

        output_payload = {
            **load_data,
        }

        if args.include_records:
            output_payload["records"] = load_result.records

    if args.save_json:
        output_path = save_result_json(
            payload=output_payload,
            results_dir=args.results_dir,
            business_id=business_id,
            year=args.year,
            month=args.month,
            persist=args.persist,
        )

        print()
        print(f"Resultado JSON guardado en: {output_path}")

    print()
    print("=== TEST FINALIZADO CORRECTAMENTE ===")


if __name__ == "__main__":
    main()