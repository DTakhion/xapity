# tests/test_sales_query_service.py

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from luca.sales_query_service import (
    get_cancelled_documents,
    get_credit_notes,
    get_sales_overview,
    get_total_receivable,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = ROOT_DIR / "results"


# ==================================================
# ARGUMENTOS
# ==================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prueba determinista del servicio de consultas "
            "comerciales de Luca."
        )
    )

    parser.add_argument(
        "--business-id",
        type=int,
        default=70,
        help="Business ID de Luca. Default: 70.",
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Año consultado. Default: 2026.",
    )

    parser.add_argument(
        "--month",
        type=int,
        default=1,
        help="Mes consultado entre 1 y 12. Default: 1.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=(
            "Máximo de documentos retornados en consultas "
            "de detalle. Default: 100."
        ),
    )

    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Guarda el resultado completo dentro de results/.",
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directorio de salida. Default: results/.",
    )

    parser.add_argument(
        "--validate-known-january",
        action="store_true",
        help=(
            "Valida los valores conocidos del loader para "
            "businessId=70, enero de 2026."
        ),
    )

    return parser


# ==================================================
# UTILIDADES
# ==================================================

def json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return str(value)


def format_clp(value: Any) -> str:
    try:
        numeric_value = round(float(value))
    except (TypeError, ValueError):
        numeric_value = 0

    return f"${numeric_value:,.0f}".replace(",", ".")


def save_result_json(
    *,
    payload: dict[str, Any],
    results_dir: Path,
    business_id: int,
    year: int,
    month: int,
) -> Path:
    results_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = results_dir / (
        f"sales_query_service_"
        f"business_{business_id}_"
        f"{year}_"
        f"month_{month}_"
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
# ASSERTIONS
# ==================================================

def assert_equal(
    *,
    label: str,
    actual: Any,
    expected: Any,
) -> None:
    if actual != expected:
        raise AssertionError(
            f"{label}: esperado={expected!r}, "
            f"obtenido={actual!r}"
        )

    print(
        f"[OK] {label}: {actual}"
    )


def assert_amount_equal(
    *,
    label: str,
    actual: Any,
    expected: float,
    tolerance: float = 0.01,
) -> None:
    actual_float = float(actual or 0)

    difference = abs(
        actual_float - expected
    )

    if difference > tolerance:
        raise AssertionError(
            f"{label}: esperado={expected}, "
            f"obtenido={actual_float}, "
            f"diferencia={difference}"
        )

    print(
        f"[OK] {label}: "
        f"{format_clp(actual_float)}"
    )


def validate_known_january_results(
    *,
    overview: dict[str, Any],
    receivable: dict[str, Any],
    credit_notes: dict[str, Any],
    cancelled_documents: dict[str, Any],
) -> None:
    """
    Valida los resultados conocidos obtenidos previamente
    desde el loader para:

        businessId = 70
        year = 2026
        month = 1
    """
    overview_result = overview["result"]
    receivable_result = receivable["result"]
    credit_notes_result = credit_notes["result"]
    cancelled_result = cancelled_documents["result"]

    print()
    print("--- VALIDACIÓN ENERO 2026 ---")

    assert_equal(
        label="documentos totales",
        actual=overview_result["totalDocuments"],
        expected=121,
    )

    assert_amount_equal(
        label="monto total",
        actual=overview_result["totalAmount"],
        expected=47_739_414.0,
    )

    assert_equal(
        label="documentos por cobrar",
        actual=overview_result["receivableDocuments"],
        expected=119,
    )

    assert_amount_equal(
        label="monto por cobrar",
        actual=overview_result["receivableAmount"],
        expected=47_428_676.0,
    )

    assert_equal(
        label="clientes únicos",
        actual=overview_result["uniqueCustomers"],
        expected=116,
    )

    assert_equal(
        label="notas de crédito",
        actual=overview_result["creditNotes"],
        expected=1,
    )

    assert_equal(
        label="documentos anulados",
        actual=overview_result["cancelledDocuments"],
        expected=2,
    )

    assert_equal(
        label="documentos vinculados",
        actual=overview_result["linkedDocuments"],
        expected=1,
    )

    assert_equal(
        label="vinculaciones totales",
        actual=overview_result["totalLinkages"],
        expected=1,
    )

    assert_equal(
        label="consulta documentos por cobrar",
        actual=receivable_result["documentsCount"],
        expected=119,
    )

    assert_amount_equal(
        label="consulta monto por cobrar",
        actual=receivable_result["totalAmount"],
        expected=47_428_676.0,
    )

    assert_equal(
        label="consulta notas de crédito",
        actual=credit_notes_result["documentsCount"],
        expected=1,
    )

    assert_amount_equal(
        label="monto notas de crédito",
        actual=credit_notes_result["totalAmount"],
        expected=155_369.0,
    )

    assert_equal(
        label="consulta documentos anulados",
        actual=cancelled_result["documentsCount"],
        expected=2,
    )

    assert_amount_equal(
        label="monto documentos anulados",
        actual=cancelled_result["totalAmount"],
        expected=310_738.0,
    )

    print()
    print(
        "Validación conocida completada correctamente."
    )


# ==================================================
# IMPRESIÓN
# ==================================================

def print_header(
    args: argparse.Namespace,
) -> None:
    print()
    print("=== TEST SALES QUERY SERVICE ===")
    print(f"businessId : {args.business_id}")
    print(f"year       : {args.year}")
    print(f"month      : {args.month}")
    print(f"limit      : {args.limit}")
    print()


def print_overview(
    overview: dict[str, Any],
) -> None:
    result = overview["result"]

    print("--- OVERVIEW ---")
    print(
        f"documentos totales       : "
        f"{result.get('totalDocuments')}"
    )
    print(
        f"monto total              : "
        f"{format_clp(result.get('totalAmount'))}"
    )
    print(
        f"documentos por cobrar    : "
        f"{result.get('receivableDocuments')}"
    )
    print(
        f"monto por cobrar         : "
        f"{format_clp(result.get('receivableAmount'))}"
    )
    print(
        f"clientes únicos          : "
        f"{result.get('uniqueCustomers')}"
    )
    print(
        f"notas de crédito         : "
        f"{result.get('creditNotes')}"
    )
    print(
        f"documentos anulados      : "
        f"{result.get('cancelledDocuments')}"
    )
    print(
        f"documentos vinculados    : "
        f"{result.get('linkedDocuments')}"
    )
    print(
        f"vinculaciones totales    : "
        f"{result.get('totalLinkages')}"
    )

    print()
    print("--- ESTADOS ---")

    for status in result.get("byStatus", []):
        print(
            f"{status.get('status')}: "
            f"{status.get('documentsCount')} documentos | "
            f"{format_clp(status.get('totalAmount'))}"
        )

    print()
    print("--- TIPOS DE DOCUMENTO ---")

    for document_type in result.get(
        "byDocumentType",
        [],
    ):
        print(
            f"code={document_type.get('documentCode')} | "
            f"{document_type.get('documentName')} | "
            f"{document_type.get('documentsCount')} documentos | "
            f"{format_clp(document_type.get('totalAmount'))}"
        )


def print_receivable(
    receivable: dict[str, Any],
) -> None:
    result = receivable["result"]

    print()
    print("--- POR COBRAR ---")
    print(
        f"documentos : "
        f"{result.get('documentsCount')}"
    )
    print(
        f"monto      : "
        f"{format_clp(result.get('totalAmount'))}"
    )


def print_credit_notes(
    credit_notes: dict[str, Any],
) -> None:
    result = credit_notes["result"]

    print()
    print("--- NOTAS DE CRÉDITO ---")
    print(
        f"documentos : "
        f"{result.get('documentsCount')}"
    )
    print(
        f"monto      : "
        f"{format_clp(result.get('totalAmount'))}"
    )

    for document in result.get("documents", []):
        print(
            f"- {document.get('documentName')} | "
            f"status={document.get('status')} | "
            f"cliente={document.get('customerName')} | "
            f"{format_clp(document.get('amount'))}"
        )


def print_cancelled_documents(
    cancelled_documents: dict[str, Any],
) -> None:
    result = cancelled_documents["result"]

    print()
    print("--- DOCUMENTOS ANULADOS ---")
    print(
        f"documentos : "
        f"{result.get('documentsCount')}"
    )
    print(
        f"monto      : "
        f"{format_clp(result.get('totalAmount'))}"
    )

    for document in result.get("documents", []):
        print(
            f"- {document.get('documentName')} | "
            f"status={document.get('status')} | "
            f"cliente={document.get('customerName')} | "
            f"{format_clp(document.get('amount'))}"
        )


# ==================================================
# EJECUCIÓN
# ==================================================

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.business_id <= 0:
        parser.error(
            "--business-id debe ser mayor que cero."
        )

    if args.year < 2000 or args.year > 2100:
        parser.error(
            "--year está fuera del rango permitido."
        )

    if args.month < 1 or args.month > 12:
        parser.error(
            "--month debe estar entre 1 y 12."
        )

    if args.limit <= 0:
        parser.error(
            "--limit debe ser mayor que cero."
        )

    print_header(args)

    overview = get_sales_overview(
        business_id=args.business_id,
        year=args.year,
        month=args.month,
    )

    receivable = get_total_receivable(
        business_id=args.business_id,
        year=args.year,
        month=args.month,
    )

    credit_notes = get_credit_notes(
        business_id=args.business_id,
        year=args.year,
        month=args.month,
        limit=args.limit,
    )

    cancelled_documents = get_cancelled_documents(
        business_id=args.business_id,
        year=args.year,
        month=args.month,
        limit=args.limit,
    )

    print_overview(overview)
    print_receivable(receivable)
    print_credit_notes(credit_notes)
    print_cancelled_documents(
        cancelled_documents
    )

    if args.validate_known_january:
        if (
            args.business_id != 70
            or args.year != 2026
            or args.month != 1
        ):
            parser.error(
                "--validate-known-january sólo aplica para "
                "businessId=70, year=2026 y month=1."
            )

        validate_known_january_results(
            overview=overview,
            receivable=receivable,
            credit_notes=credit_notes,
            cancelled_documents=cancelled_documents,
        )

    payload = {
        "overview": overview,
        "receivable": receivable,
        "creditNotes": credit_notes,
        "cancelledDocuments": cancelled_documents,
    }

    if args.save_json:
        output_path = save_result_json(
            payload=payload,
            results_dir=args.results_dir,
            business_id=args.business_id,
            year=args.year,
            month=args.month,
        )

        print()
        print(
            f"Resultado JSON guardado en: "
            f"{output_path}"
        )

    print()
    print("=== TEST FINALIZADO CORRECTAMENTE ===")


if __name__ == "__main__":
    main()