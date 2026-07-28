# tests/test_sales_intent_router.py
"""
Prueba manual y validación determinista del router comercial de Luca.

Permite:

- ejecutar una batería predefinida de preguntas;
- probar una pregunta individual desde terminal;
- filtrar casos por intención;
- mostrar únicamente errores;
- validar intenciones y entidades;
- exportar los resultados a JSON;
- terminar con código distinto de cero si una validación falla.

Ejemplos
--------
Ejecutar todos los casos:

    python3 -m tests.test_sales_intent_router

Mostrar solamente errores:

    python3 -m tests.test_sales_intent_router \
        --only-errors

Probar una pregunta libre:

    python3 -m tests.test_sales_intent_router \
        --question "¿Cuánto dinero tengo por cobrar?"

Filtrar por intención:

    python3 -m tests.test_sales_intent_router \
        --intent customer_detail

Guardar los resultados:

    python3 -m tests.test_sales_intent_router \
        --save-json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from luca.sales_intent_router import (
    SalesIntentRouter,
    normalize_question,
    route_sales_intent,
)
from luca.sales_intents import IntentResult, SalesIntent


# ---------------------------------------------------------------------------
# Modelos del test
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RouterTestCase:
    """
    Caso de prueba para el router.

    Attributes
    ----------
    question:
        Pregunta que será enviada al router.

    expected_intent:
        Intención esperada.

    expected_entities:
        Entidades que necesariamente deben estar presentes en el resultado.
        El router puede devolver entidades adicionales sin que el test falle.

    expected_rule:
        Regla esperada. Es opcional porque algunas pruebas sólo necesitan
        validar la intención.

    description:
        Breve explicación del caso.
    """

    question: str
    expected_intent: SalesIntent
    expected_entities: dict[str, Any] = field(default_factory=dict)
    expected_rule: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class RouterTestResult:
    """
    Resultado de la ejecución de un caso.
    """

    index: int
    case: RouterTestCase
    routed: IntentResult
    passed: bool
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """
        Convierte el resultado a un diccionario serializable.
        """

        return {
            "index": self.index,
            "question": self.case.question,
            "description": self.case.description,
            "expected": {
                "intent": self.case.expected_intent.value,
                "entities": self.case.expected_entities,
                "rule": self.case.expected_rule,
            },
            "received": self.routed.to_dict(),
            "passed": self.passed,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Casos de prueba
# ---------------------------------------------------------------------------


TEST_CASES: tuple[RouterTestCase, ...] = (
    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    RouterTestCase(
        question="Dame un resumen general de las ventas.",
        expected_intent=SalesIntent.SALES_OVERVIEW,
        expected_rule="sales_overview",
        description="Resumen general de ventas.",
    ),
    RouterTestCase(
        question="¿Cómo están las ventas?",
        expected_intent=SalesIntent.SALES_OVERVIEW,
        expected_rule="sales_overview",
        description="Pregunta informal por el estado de ventas.",
    ),
    RouterTestCase(
        question="Necesito un resumen comercial.",
        expected_intent=SalesIntent.SALES_OVERVIEW,
        expected_rule="sales_overview",
    ),

    # ------------------------------------------------------------------
    # Totales
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Cuántos documentos tengo?",
        expected_intent=SalesIntent.TOTAL_DOCUMENTS,
        expected_rule="total_documents",
    ),
    RouterTestCase(
        question="¿Cuál es el total de facturas?",
        expected_intent=SalesIntent.TOTAL_DOCUMENTS,
        expected_rule="total_documents",
    ),
    RouterTestCase(
        question="¿Cuánto he vendido?",
        expected_intent=SalesIntent.TOTAL_SALES_AMOUNT,
        expected_rule="total_sales_amount",
    ),
    RouterTestCase(
        question="¿Cuál es el monto total de ventas?",
        expected_intent=SalesIntent.TOTAL_SALES_AMOUNT,
        expected_rule="total_sales_amount",
    ),
    RouterTestCase(
        question="¿Cuántos clientes distintos tengo?",
        expected_intent=SalesIntent.TOTAL_CUSTOMERS,
        expected_rule="total_customers",
    ),
    RouterTestCase(
        question="¿Cuál es el número de clientes?",
        expected_intent=SalesIntent.TOTAL_CUSTOMERS,
        expected_rule="total_customers",
    ),

    # ------------------------------------------------------------------
    # Cuentas por cobrar
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Cuánto dinero tengo por cobrar?",
        expected_intent=SalesIntent.TOTAL_RECEIVABLE,
        expected_rule="total_receivable",
    ),
    RouterTestCase(
        question="¿Cuánto me deben?",
        expected_intent=SalesIntent.TOTAL_RECEIVABLE,
        expected_rule="total_receivable",
    ),
    RouterTestCase(
        question="¿Cuál es el saldo pendiente?",
        expected_intent=SalesIntent.TOTAL_RECEIVABLE,
        expected_rule="total_receivable",
    ),
    RouterTestCase(
        question="Muéstrame los documentos por cobrar.",
        expected_intent=SalesIntent.RECEIVABLE_DOCUMENTS,
        expected_rule="receivable_documents",
    ),
    RouterTestCase(
        question="¿Cuáles son las facturas pendientes?",
        expected_intent=SalesIntent.RECEIVABLE_DOCUMENTS,
        expected_rule="receivable_documents",
    ),

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Cuáles son mis 10 principales clientes?",
        expected_intent=SalesIntent.TOP_CUSTOMERS,
        expected_entities={
            "limit": 10,
        },
        expected_rule="top_customers",
    ),
    RouterTestCase(
        question="Muéstrame el top 5 clientes.",
        expected_intent=SalesIntent.TOP_CUSTOMERS,
        expected_entities={
            "limit": 5,
        },
        expected_rule="top_customers",
    ),
    RouterTestCase(
        question="¿Quién es mi mejor cliente?",
        expected_intent=SalesIntent.TOP_CUSTOMERS,
        expected_entities={
            "limit": 10,
        },
        expected_rule="top_customers",
    ),
    RouterTestCase(
        question="¿Qué clientes tienen más de una factura?",
        expected_intent=SalesIntent.CUSTOMERS_WITH_MULTIPLE_DOCUMENTS,
        expected_rule="customers_with_multiple_documents",
    ),
    RouterTestCase(
        question="Muéstrame los clientes con varias facturas.",
        expected_intent=SalesIntent.CUSTOMERS_WITH_MULTIPLE_DOCUMENTS,
        expected_rule="customers_with_multiple_documents",
    ),

    # ------------------------------------------------------------------
    # Cliente específico
    # ------------------------------------------------------------------

    RouterTestCase(
        question="Muéstrame las facturas de Frogmi.",
        expected_intent=SalesIntent.CUSTOMER_DETAIL,
        expected_entities={
            "customer": "frogmi",
        },
        expected_rule="customer_sales_detail",
    ),
    RouterTestCase(
        question="¿Cuánto le he vendido a OSHER?",
        expected_intent=SalesIntent.CUSTOMER_DETAIL,
        expected_entities={
            "customer": "osher",
        },
        expected_rule="customer_sales_detail",
    ),
    RouterTestCase(
        question="¿Cuánto vendí a Acme en enero de 2026?",
        expected_intent=SalesIntent.CUSTOMER_DETAIL,
        expected_entities={
            "customer": "acme",
            "year": 2026,
            "month": 1,
        },
        expected_rule="customer_sales_detail",
        description="Debe priorizar cliente específico sobre venta mensual.",
    ),
    RouterTestCase(
        question="¿Cuánto me debe Empresa ABC?",
        expected_intent=SalesIntent.CUSTOMER_DETAIL,
        expected_entities={
            "customer": "empresa abc",
        },
        expected_rule="customer_receivable_detail",
    ),
    RouterTestCase(
        question="Muéstrame los documentos del cliente Comercial Andes.",
        expected_intent=SalesIntent.CUSTOMER_DETAIL,
        expected_entities={
            "customer": "comercial andes",
        },
        expected_rule="customer_sales_detail",
    ),

    # ------------------------------------------------------------------
    # Notas de crédito, anulaciones y linkage
    # ------------------------------------------------------------------

    RouterTestCase(
        question="Muéstrame las notas de crédito.",
        expected_intent=SalesIntent.CREDIT_NOTES,
        expected_rule="credit_notes",
    ),
    RouterTestCase(
        question="¿Cuántas notas de crédito existen?",
        expected_intent=SalesIntent.CREDIT_NOTES,
        expected_rule="credit_notes",
    ),
    RouterTestCase(
        question="¿Qué documentos fueron anulados?",
        expected_intent=SalesIntent.CANCELLED_DOCUMENTS,
        expected_rule="cancelled_documents",
    ),
    RouterTestCase(
        question="Muéstrame las facturas anuladas.",
        expected_intent=SalesIntent.CANCELLED_DOCUMENTS,
        expected_rule="cancelled_documents",
    ),
    RouterTestCase(
        question="¿Hay documentos vinculados?",
        expected_intent=SalesIntent.LINKED_DOCUMENTS,
        expected_rule="linked_documents",
    ),
    RouterTestCase(
        question="¿Cuántos documentos tienen linkage?",
        expected_intent=SalesIntent.LINKED_DOCUMENTS,
        expected_rule="linked_documents",
    ),

    # ------------------------------------------------------------------
    # Montos extremos
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Cuál fue la factura de mayor monto?",
        expected_intent=SalesIntent.LARGEST_DOCUMENT,
        expected_rule="largest_document",
    ),
    RouterTestCase(
        question="¿Cuál fue la factura más grande?",
        expected_intent=SalesIntent.LARGEST_DOCUMENT,
        expected_rule="largest_document",
    ),
    RouterTestCase(
        question="¿Cuál fue la factura de menor monto?",
        expected_intent=SalesIntent.SMALLEST_DOCUMENT,
        expected_rule="smallest_document",
    ),
    RouterTestCase(
        question="¿Cuál fue la venta más baja?",
        expected_intent=SalesIntent.SMALLEST_DOCUMENT,
        expected_rule="smallest_document",
    ),

    # ------------------------------------------------------------------
    # Tipos y estados
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Qué tipos de documentos existen?",
        expected_intent=SalesIntent.DOCUMENT_TYPES,
        expected_rule="document_types",
    ),
    RouterTestCase(
        question="¿Cuánto representa cada tipo de documento?",
        expected_intent=SalesIntent.DOCUMENT_TYPES,
        expected_rule="document_types",
    ),
    RouterTestCase(
        question="¿Cuántas facturas exentas existen?",
        expected_intent=SalesIntent.DOCUMENT_TYPES,
        expected_rule="document_types",
    ),
    RouterTestCase(
        question="¿Qué estados existen?",
        expected_intent=SalesIntent.DOCUMENT_STATUS,
        expected_rule="document_status",
    ),
    RouterTestCase(
        question="Muéstrame los documentos por estado.",
        expected_intent=SalesIntent.DOCUMENT_STATUS,
        expected_rule="document_status",
    ),
    RouterTestCase(
        question="¿Cuánto dinero hay por estado?",
        expected_intent=SalesIntent.DOCUMENT_STATUS,
        expected_rule="document_status",
    ),

    # ------------------------------------------------------------------
    # Fechas y vencimientos
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Qué documentos vencen hoy?",
        expected_intent=SalesIntent.DOCUMENTS_DUE_TODAY,
        expected_rule="documents_due_today",
    ),
    RouterTestCase(
        question="¿Qué facturas vencen esta semana?",
        expected_intent=SalesIntent.DOCUMENTS_DUE_THIS_WEEK,
        expected_rule="documents_due_this_week",
    ),
    RouterTestCase(
        question="¿Qué documentos vencen este mes?",
        expected_intent=SalesIntent.DOCUMENTS_DUE_THIS_MONTH,
        expected_rule="documents_due_this_month",
    ),
    RouterTestCase(
        question="Muéstrame las facturas vencidas.",
        expected_intent=SalesIntent.OVERDUE_DOCUMENTS,
        expected_rule="overdue_documents",
    ),
    RouterTestCase(
        question="¿Existen clientes morosos?",
        expected_intent=SalesIntent.OVERDUE_DOCUMENTS,
        expected_rule="overdue_documents",
    ),
    RouterTestCase(
        question="¿Qué documentos no tienen fecha de vencimiento?",
        expected_intent=SalesIntent.DOCUMENTS_WITHOUT_DUE_DATE,
        expected_rule="documents_without_due_date",
    ),

    # ------------------------------------------------------------------
    # Períodos
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Cuánto vendí en enero de 2026?",
        expected_intent=SalesIntent.MONTHLY_SALES,
        expected_entities={
            "year": 2026,
            "month": 1,
        },
        expected_rule="monthly_sales",
    ),
    RouterTestCase(
        question="Muéstrame las ventas de marzo de 2025.",
        expected_intent=SalesIntent.MONTHLY_SALES,
        expected_entities={
            "year": 2025,
            "month": 3,
        },
        expected_rule="monthly_sales",
    ),
    RouterTestCase(
        question="¿Cuál fue el total vendido en octubre de 2026?",
        expected_intent=SalesIntent.TOTAL_SALES_AMOUNT,
        expected_entities={
            "year": 2026,
            "month": 10,
        },
        expected_rule="total_sales_amount",
        description=(
            "El router actual reconoce 'total vendido' como total_sales_amount "
            "y extrae el período."
        ),
    ),

    # ------------------------------------------------------------------
    # Comparaciones y tendencias
    # ------------------------------------------------------------------

    RouterTestCase(
        question="¿Vendimos más que el mes pasado?",
        expected_intent=SalesIntent.SALES_COMPARISON,
        expected_rule="sales_comparison",
    ),
    RouterTestCase(
        question="Quiero una comparación de ventas.",
        expected_intent=SalesIntent.SALES_COMPARISON,
        expected_rule="sales_comparison",
    ),
    RouterTestCase(
        question="¿Cómo ha sido la evolución de las ventas?",
        expected_intent=SalesIntent.SALES_TREND,
        expected_rule="sales_trend",
    ),
    RouterTestCase(
        question="Muéstrame la tendencia de las ventas.",
        expected_intent=SalesIntent.SALES_TREND,
        expected_rule="sales_trend",
    ),

    # ------------------------------------------------------------------
    # Unknown
    # ------------------------------------------------------------------

    RouterTestCase(
        question="Cuéntame una historia sobre dragones.",
        expected_intent=SalesIntent.UNKNOWN,
        expected_rule="no_matching_rule",
    ),
    RouterTestCase(
        question="¿Cuál será el clima de mañana?",
        expected_intent=SalesIntent.UNKNOWN,
        expected_rule="no_matching_rule",
    ),
    RouterTestCase(
        question="",
        expected_intent=SalesIntent.UNKNOWN,
        expected_rule="empty_question",
    ),
)


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------


def normalize_entity_value(value: Any) -> Any:
    """
    Normaliza valores para evitar diferencias irrelevantes en el test.
    """

    if isinstance(value, str):
        return normalize_question(value)

    return value


def validate_case(
    index: int,
    case: RouterTestCase,
    router: SalesIntentRouter,
) -> RouterTestResult:
    """
    Ejecuta y valida un caso individual.
    """

    routed = router.route(case.question)
    errors: list[str] = []

    if routed.intent is not case.expected_intent:
        errors.append(
            "Intent incorrecto: "
            f"esperado={case.expected_intent.value}, "
            f"recibido={routed.intent.value}"
        )

    if (
        case.expected_rule is not None
        and routed.matched_rule != case.expected_rule
    ):
        errors.append(
            "Regla incorrecta: "
            f"esperada={case.expected_rule}, "
            f"recibida={routed.matched_rule}"
        )

    for entity_name, expected_value in case.expected_entities.items():
        if entity_name not in routed.entities:
            errors.append(
                f"Entidad ausente: {entity_name!r}"
            )
            continue

        received_value = routed.entities[entity_name]

        normalized_expected = normalize_entity_value(
            expected_value
        )
        normalized_received = normalize_entity_value(
            received_value
        )

        if normalized_received != normalized_expected:
            errors.append(
                f"Entidad incorrecta {entity_name!r}: "
                f"esperada={expected_value!r}, "
                f"recibida={received_value!r}"
            )

    return RouterTestResult(
        index=index,
        case=case,
        routed=routed,
        passed=not errors,
        errors=tuple(errors),
    )


def run_cases(
    cases: Iterable[RouterTestCase],
    router: SalesIntentRouter,
) -> list[RouterTestResult]:
    """
    Ejecuta una colección de casos.
    """

    return [
        validate_case(
            index=index,
            case=case,
            router=router,
        )
        for index, case in enumerate(cases, start=1)
    ]


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------


def print_result(
    result: RouterTestResult,
    *,
    compact: bool = False,
) -> None:
    """
    Imprime un resultado individual.
    """

    status = "OK" if result.passed else "ERROR"

    if compact:
        print(
            f"[{status:5}] "
            f"{result.index:02d} | "
            f"{result.case.expected_intent.value:35} | "
            f"{result.case.question}"
        )
        return

    print("=" * 88)
    print(f"Caso       : {result.index}")
    print(f"Estado     : {status}")
    print(f"Pregunta   : {result.case.question}")
    print(f"Normalizada: {result.routed.normalized_question}")
    print(
        "Intent     : "
        f"{result.routed.intent.value} "
        f"(esperado: {result.case.expected_intent.value})"
    )
    print(
        "Regla      : "
        f"{result.routed.matched_rule} "
        f"(esperada: {result.case.expected_rule})"
    )
    print(f"Confianza  : {result.routed.confidence}")
    print(f"Entidades  : {result.routed.entities}")

    if result.case.description:
        print(f"Descripción: {result.case.description}")

    if result.errors:
        print("Errores:")

        for error in result.errors:
            print(f"  - {error}")


def print_summary(
    results: list[RouterTestResult],
) -> None:
    """
    Imprime el resumen global.
    """

    total = len(results)
    passed = sum(result.passed for result in results)
    failed = total - passed

    success_rate = (
        (passed / total) * 100
        if total
        else 0.0
    )

    print()
    print("=" * 88)
    print("RESUMEN TEST SALES INTENT ROUTER")
    print("=" * 88)
    print(f"Casos ejecutados : {total}")
    print(f"Casos correctos  : {passed}")
    print(f"Casos fallidos   : {failed}")
    print(f"Tasa de éxito    : {success_rate:.2f}%")

    if failed == 0:
        print()
        print("Resultado: VALIDACIÓN EXITOSA")
    else:
        print()
        print("Resultado: VALIDACIÓN CON ERRORES")


def print_free_question_result(
    question: str,
    result: IntentResult,
) -> None:
    """
    Imprime el resultado de una pregunta libre.
    """

    print()
    print("=" * 88)
    print("PRUEBA LIBRE SALES INTENT ROUTER")
    print("=" * 88)
    print(f"Pregunta   : {question}")
    print(f"Normalizada: {result.normalized_question}")
    print(f"Intent     : {result.intent.value}")
    print(f"Confianza  : {result.confidence}")
    print(f"Regla      : {result.matched_rule}")
    print(f"Entidades  : {result.entities}")
    print(f"Unknown    : {result.is_unknown}")
    print()
    print("JSON:")
    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------


def save_results_json(
    results: list[RouterTestResult],
    *,
    results_dir: str,
) -> Path:
    """
    Guarda los resultados de la batería en JSON.
    """

    output_dir = Path(results_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = output_dir / (
        f"sales_intent_router_{timestamp}.json"
    )

    payload = {
        "generatedAt": datetime.now().isoformat(),
        "summary": {
            "total": len(results),
            "passed": sum(
                result.passed
                for result in results
            ),
            "failed": sum(
                not result.passed
                for result in results
            ),
        },
        "results": [
            result.to_dict()
            for result in results
        ],
    }

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return output_path


def save_free_question_json(
    question: str,
    result: IntentResult,
    *,
    results_dir: str,
) -> Path:
    """
    Guarda el resultado de una pregunta libre.
    """

    output_dir = Path(results_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = output_dir / (
        f"sales_intent_router_question_{timestamp}.json"
    )

    payload = {
        "generatedAt": datetime.now().isoformat(),
        "question": question,
        "result": result.to_dict(),
    }

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return output_path


# ---------------------------------------------------------------------------
# Selección de casos
# ---------------------------------------------------------------------------


def parse_intent(
    value: str,
) -> SalesIntent:
    """
    Convierte un argumento CLI en SalesIntent.
    """

    try:
        return SalesIntent(value)
    except ValueError as error:
        valid_values = ", ".join(
            intent.value
            for intent in SalesIntent
        )

        raise argparse.ArgumentTypeError(
            f"Intent inválido: {value!r}. "
            f"Valores permitidos: {valid_values}"
        ) from error


def filter_cases(
    cases: tuple[RouterTestCase, ...],
    *,
    intent: SalesIntent | None,
) -> tuple[RouterTestCase, ...]:
    """
    Filtra casos por intención esperada.
    """

    if intent is None:
        return cases

    return tuple(
        case
        for case in cases
        if case.expected_intent is intent
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """
    Construye el parser de argumentos.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Prueba determinista del router de intenciones "
            "comerciales de Luca."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python3 -m tests.test_sales_intent_router

  python3 -m tests.test_sales_intent_router \\
      --only-errors

  python3 -m tests.test_sales_intent_router \\
      --compact

  python3 -m tests.test_sales_intent_router \\
      --intent customer_detail

  python3 -m tests.test_sales_intent_router \\
      --question "¿Cuánto dinero tengo por cobrar?"

  python3 -m tests.test_sales_intent_router \\
      --question "Muéstrame las facturas de Frogmi en enero de 2026" \\
      --save-json
""",
    )

    parser.add_argument(
        "--question",
        type=str,
        default=None,
        help=(
            "Ejecuta una pregunta libre y omite la batería "
            "predefinida."
        ),
    )

    parser.add_argument(
        "--intent",
        type=parse_intent,
        default=None,
        help=(
            "Ejecuta solamente los casos cuya intención esperada "
            "coincida con el valor indicado."
        ),
    )

    parser.add_argument(
        "--only-errors",
        action="store_true",
        help="Muestra solamente los casos fallidos.",
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        help="Utiliza una salida resumida de una línea por caso.",
    )

    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Guarda los resultados completos en un archivo JSON.",
    )

    parser.add_argument(
        "--results-dir",
        type=str,
        default="results",
        help=(
            "Directorio para archivos JSON. "
            "Por defecto: results"
        ),
    )

    parser.add_argument(
        "--no-fail",
        action="store_true",
        help=(
            "Devuelve código de salida 0 incluso cuando existen "
            "casos fallidos."
        ),
    )

    parser.add_argument(
        "--list-intents",
        action="store_true",
        help="Muestra todas las intenciones disponibles y termina.",
    )

    return parser


def main() -> None:
    """
    Punto de entrada del script.
    """

    parser = build_parser()
    args = parser.parse_args()

    if args.list_intents:
        print("Intenciones disponibles:")

        for intent in SalesIntent:
            print(f"  - {intent.value}")

        return

    # ------------------------------------------------------------------
    # Pregunta libre
    # ------------------------------------------------------------------

    if args.question is not None:
        result = route_sales_intent(
            args.question
        )

        print_free_question_result(
            args.question,
            result,
        )

        if args.save_json:
            output_path = save_free_question_json(
                args.question,
                result,
                results_dir=args.results_dir,
            )

            print(f"Resultado guardado: {output_path}")

        return

    # ------------------------------------------------------------------
    # Batería de pruebas
    # ------------------------------------------------------------------

    selected_cases = filter_cases(
        TEST_CASES,
        intent=args.intent,
    )

    if not selected_cases:
        print(
            "No existen casos para los filtros seleccionados.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    router = SalesIntentRouter()

    results = run_cases(
        selected_cases,
        router,
    )

    for result in results:
        if args.only_errors and result.passed:
            continue

        print_result(
            result,
            compact=args.compact,
        )

    print_summary(results)

    if args.save_json:
        output_path = save_results_json(
            results,
            results_dir=args.results_dir,
        )

        print()
        print(f"Resultados guardados: {output_path}")

    has_failures = any(
        not result.passed
        for result in results
    )

    if has_failures and not args.no_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()