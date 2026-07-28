# luca/sales_response_builder.py
"""
Construcción determinista de respuestas comerciales para Luca.

Este módulo recibe:

- la intención comercial detectada;
- el resultado estructurado de sales_query_service.py;

y devuelve una respuesta natural para el usuario.

No realiza:

- consultas a Mongo;
- detección de intenciones;
- cálculos comerciales adicionales;
- llamadas a modelos de lenguaje.

La información numérica siempre proviene del servicio determinista
de consultas comerciales.

Capacidades actualmente implementadas:

- SALES_OVERVIEW
- TOTAL_RECEIVABLE
- CREDIT_NOTES
- CANCELLED_DOCUMENTS
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from luca.sales_intents import SalesIntent


# ==================================================
# TIPOS
# ==================================================


ResponseBuilderHandler = Callable[
    [Mapping[str, Any]],
    str,
]


@dataclass(frozen=True, slots=True)
class SalesResponseBuildResult:
    """
    Resultado estructurado del constructor de respuestas.

    Attributes
    ----------
    answer:
        Texto natural que será mostrado al usuario.

    intent:
        Intención utilizada para construir la respuesta.

    builder:
        Nombre del constructor ejecutado.

    deterministic:
        Indica que el texto fue generado mediante reglas
        deterministas, sin participación de un LLM.
    """

    answer: str
    intent: str
    builder: str
    deterministic: bool = True

    def to_dict(self) -> dict[str, Any]:
        """
        Convierte el resultado a un diccionario serializable.
        """

        return {
            "answer": self.answer,
            "intent": self.intent,
            "builder": self.builder,
            "deterministic": self.deterministic,
        }


# ==================================================
# VALIDACIONES
# ==================================================


def _validate_query_result(
    query_result: Mapping[str, Any],
) -> None:
    """
    Valida la estructura mínima de una consulta comercial.
    """

    if not isinstance(query_result, Mapping):
        raise TypeError(
            "query_result debe ser un mapping."
        )

    result = query_result.get("result")

    if result is None:
        raise ValueError(
            "query_result no contiene la clave 'result'."
        )

    if not isinstance(result, Mapping):
        raise TypeError(
            "query_result['result'] debe ser un mapping."
        )

    filters = query_result.get("filters")

    if (
        filters is not None
        and not isinstance(filters, Mapping)
    ):
        raise TypeError(
            "query_result['filters'] debe ser un mapping "
            "o None."
        )


def _validate_intent(
    intent: SalesIntent,
) -> None:
    if not isinstance(intent, SalesIntent):
        raise TypeError(
            "intent debe ser una instancia de SalesIntent."
        )


# ==================================================
# ACCESO SEGURO
# ==================================================


def _get_result(
    query_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    result = query_result.get(
        "result",
        {},
    )

    return (
        result
        if isinstance(result, Mapping)
        else {}
    )


def _get_filters(
    query_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    filters = query_result.get(
        "filters",
        {},
    )

    return (
        filters
        if isinstance(filters, Mapping)
        else {}
    )


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
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

        if (
            "." in normalized
            and "," in normalized
        ):
            normalized = (
                normalized
                .replace(".", "")
                .replace(",", ".")
            )

        elif "," in normalized:
            normalized = normalized.replace(
                ",",
                ".",
            )

        value = normalized

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ==================================================
# FORMATO DE VALORES
# ==================================================


def format_clp(
    value: Any,
) -> str:
    """
    Formatea un monto como peso chileno.

    Ejemplos
    --------
    1250000
        -> $1.250.000

    -45000
        -> -$45.000
    """

    amount = round(
        _safe_float(value)
    )

    absolute_amount = abs(amount)

    formatted = (
        f"{absolute_amount:,}"
        .replace(",", ".")
    )

    sign = "-" if amount < 0 else ""

    return f"{sign}${formatted}"


def format_number(
    value: Any,
) -> str:
    """
    Formatea un entero usando separador de miles chileno.
    """

    number = _safe_int(value)

    return f"{number:,}".replace(
        ",",
        ".",
    )


def format_period(
    *,
    year: Any = None,
    month: Any = None,
) -> str:
    """
    Construye una frase temporal breve.

    Ejemplos
    --------
    year=2026, month=1
        -> " durante enero de 2026"

    year=2026
        -> " durante 2026"

    year=None, month=None
        -> ""
    """

    resolved_year = (
        _safe_int(year)
        if year is not None
        else None
    )

    resolved_month = (
        _safe_int(month)
        if month is not None
        else None
    )

    month_names = {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "septiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre",
    }

    month_name = month_names.get(
        resolved_month
    )

    if (
        resolved_year is not None
        and month_name is not None
    ):
        return (
            f" durante {month_name} "
            f"de {resolved_year}"
        )

    if resolved_year is not None:
        return f" durante {resolved_year}"

    if month_name is not None:
        return f" durante {month_name}"

    return ""


def _singular_or_plural(
    amount: int,
    *,
    singular: str,
    plural: str,
) -> str:
    return (
        singular
        if amount == 1
        else plural
    )


# ==================================================
# OVERVIEW
# ==================================================


def build_sales_overview_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para SALES_OVERVIEW.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    total_documents = _safe_int(
        result.get("totalDocuments")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    receivable_documents = _safe_int(
        result.get("receivableDocuments")
    )

    receivable_amount = _safe_float(
        result.get("receivableAmount")
    )

    unique_customers = _safe_int(
        result.get("uniqueCustomers")
    )

    credit_notes = _safe_int(
        result.get("creditNotes")
    )

    cancelled_documents = _safe_int(
        result.get("cancelledDocuments")
    )

    linked_documents = _safe_int(
        result.get("linkedDocuments")
    )

    if total_documents == 0:
        return (
            f"No encontré documentos de venta"
            f"{period}."
        )

    document_word = _singular_or_plural(
        total_documents,
        singular="documento",
        plural="documentos",
    )

    customer_word = _singular_or_plural(
        unique_customers,
        singular="cliente único",
        plural="clientes únicos",
    )

    parts = [
        (
            f"El resumen comercial{period} registra "
            f"{format_number(total_documents)} "
            f"{document_word} por un total de "
            f"{format_clp(total_amount)}."
        ),
        (
            f"Actualmente hay "
            f"{format_number(receivable_documents)} "
            f"documentos por cobrar, equivalentes a "
            f"{format_clp(receivable_amount)}."
        ),
        (
            f"Los documentos corresponden a "
            f"{format_number(unique_customers)} "
            f"{customer_word}."
        ),
    ]

    additional_details: list[str] = []

    if credit_notes > 0:
        credit_note_word = _singular_or_plural(
            credit_notes,
            singular="nota de crédito",
            plural="notas de crédito",
        )

        additional_details.append(
            f"{format_number(credit_notes)} "
            f"{credit_note_word}"
        )

    if cancelled_documents > 0:
        cancelled_word = _singular_or_plural(
            cancelled_documents,
            singular="documento anulado",
            plural="documentos anulados",
        )

        additional_details.append(
            f"{format_number(cancelled_documents)} "
            f"{cancelled_word}"
        )

    if linked_documents > 0:
        linked_word = _singular_or_plural(
            linked_documents,
            singular="documento vinculado",
            plural="documentos vinculados",
        )

        additional_details.append(
            f"{format_number(linked_documents)} "
            f"{linked_word}"
        )

    if additional_details:
        parts.append(
            "Además, se identificaron "
            + ", ".join(additional_details)
            + "."
        )

    return " ".join(parts)


# ==================================================
# TOTAL POR COBRAR
# ==================================================


def build_total_receivable_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para TOTAL_RECEIVABLE.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré documentos por cobrar"
            f"{period}."
        )

    document_word = _singular_or_plural(
        documents_count,
        singular="documento",
        plural="documentos",
    )

    return (
        f"Tienes {format_clp(total_amount)} "
        f"por cobrar{period}, distribuidos en "
        f"{format_number(documents_count)} "
        f"{document_word}."
    )


# ==================================================
# NOTAS DE CRÉDITO
# ==================================================


def build_credit_notes_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para CREDIT_NOTES.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré notas de crédito"
            f"{period}."
        )

    note_word = _singular_or_plural(
        documents_count,
        singular="nota de crédito",
        plural="notas de crédito",
    )

    return (
        f"Encontré "
        f"{format_number(documents_count)} "
        f"{note_word}{period}, por un monto total de "
        f"{format_clp(total_amount)}."
    )


# ==================================================
# DOCUMENTOS ANULADOS
# ==================================================


def build_cancelled_documents_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para CANCELLED_DOCUMENTS.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré documentos anulados"
            f"{period}."
        )

    document_word = _singular_or_plural(
        documents_count,
        singular="documento anulado",
        plural="documentos anulados",
    )

    return (
        f"Encontré "
        f"{format_number(documents_count)} "
        f"{document_word}{period}, por un monto total de "
        f"{format_clp(total_amount)}."
    )


# ==================================================
# REGISTRO DE CONSTRUCTORES
# ==================================================


RESPONSE_BUILDERS: dict[
    SalesIntent,
    ResponseBuilderHandler,
] = {
    SalesIntent.SALES_OVERVIEW: (
        build_sales_overview_response
    ),
    SalesIntent.TOTAL_RECEIVABLE: (
        build_total_receivable_response
    ),
    SalesIntent.CREDIT_NOTES: (
        build_credit_notes_response
    ),
    SalesIntent.CANCELLED_DOCUMENTS: (
        build_cancelled_documents_response
    ),
}


# ==================================================
# CONSTRUCTOR PRINCIPAL
# ==================================================


class SalesResponseBuilder:
    """
    Constructor determinista de respuestas comerciales.
    """

    def __init__(
        self,
        *,
        builders: Mapping[
            SalesIntent,
            ResponseBuilderHandler,
        ] | None = None,
    ) -> None:
        """
        Permite inyectar constructores durante pruebas.
        """

        self._builders = dict(
            builders or RESPONSE_BUILDERS
        )

    def supports(
        self,
        intent: SalesIntent,
    ) -> bool:
        """
        Indica si existe un constructor para la intención.
        """

        _validate_intent(intent)

        return intent in self._builders

    def build(
        self,
        *,
        intent: SalesIntent,
        query_result: Mapping[str, Any],
    ) -> SalesResponseBuildResult:
        """
        Construye una respuesta natural para una intención.

        Raises
        ------
        NotImplementedError:
            Cuando no existe un constructor registrado.

        ValueError:
            Cuando la estructura del resultado es inválida.
        """

        _validate_intent(intent)
        _validate_query_result(query_result)

        builder = self._builders.get(intent)

        if builder is None:
            raise NotImplementedError(
                "No existe un constructor de respuesta "
                f"para la intención: {intent.value}"
            )

        answer = builder(
            query_result
        )

        if not isinstance(answer, str):
            raise TypeError(
                "El constructor debe retornar un string."
            )

        normalized_answer = answer.strip()

        if not normalized_answer:
            raise ValueError(
                "El constructor generó una respuesta vacía."
            )

        return SalesResponseBuildResult(
            answer=normalized_answer,
            intent=intent.value,
            builder=builder.__name__,
            deterministic=True,
        )


# ==================================================
# INTERFAZ PÚBLICA
# ==================================================


_default_builder = SalesResponseBuilder()


def build_sales_response(
    *,
    intent: SalesIntent,
    query_result: Mapping[str, Any],
) -> str:
    """
    Interfaz simplificada para sales_agent.py.

    Retorna solamente el texto final.
    """

    result = _default_builder.build(
        intent=intent,
        query_result=query_result,
    )

    return result.answer


def build_sales_response_result(
    *,
    intent: SalesIntent,
    query_result: Mapping[str, Any],
) -> SalesResponseBuildResult:
    """
    Interfaz que retorna información adicional del constructor.

    Es útil cuando se quiere incorporar al trace:

    - nombre del builder;
    - intención;
    - origen determinista.
    """

    return _default_builder.build(
        intent=intent,
        query_result=query_result,
    )


# ==================================================
# PRUEBA MANUAL
# ==================================================


def main() -> None:
    """
    Prueba manual sin Mongo ni FastAPI.
    """

    examples: tuple[
        tuple[
            SalesIntent,
            dict[str, Any],
        ],
        ...,
    ] = (
        (
            SalesIntent.TOTAL_RECEIVABLE,
            {
                "queryType": "total_receivable",
                "businessId": 5,
                "filters": {
                    "year": 2026,
                    "month": 1,
                    "status": "POR COBRAR",
                },
                "result": {
                    "documentsCount": 18,
                    "totalAmount": 12_450_000,
                },
            },
        ),
        (
            SalesIntent.CREDIT_NOTES,
            {
                "queryType": "credit_notes",
                "businessId": 5,
                "filters": {
                    "year": None,
                    "month": None,
                    "documentCode": 61,
                    "limit": 10,
                },
                "result": {
                    "documentsCount": 3,
                    "totalAmount": 825_500,
                    "documents": [],
                },
            },
        ),
        (
            SalesIntent.CANCELLED_DOCUMENTS,
            {
                "queryType": "cancelled_documents",
                "businessId": 5,
                "filters": {
                    "year": None,
                    "month": None,
                    "limit": 10,
                },
                "result": {
                    "documentsCount": 0,
                    "totalAmount": 0,
                    "documents": [],
                },
            },
        ),
        (
            SalesIntent.SALES_OVERVIEW,
            {
                "queryType": "sales_overview",
                "businessId": 5,
                "filters": {
                    "year": 2026,
                    "month": None,
                },
                "result": {
                    "totalDocuments": 120,
                    "totalAmount": 98_700_000,
                    "receivableDocuments": 18,
                    "receivableAmount": 12_450_000,
                    "uniqueCustomers": 34,
                    "creditNotes": 3,
                    "cancelledDocuments": 2,
                    "linkedDocuments": 15,
                },
            },
        ),
    )

    print()
    print("=" * 88)
    print("PRUEBA SALES RESPONSE BUILDER")
    print("=" * 88)

    for intent, query_result in examples:
        result = build_sales_response_result(
            intent=intent,
            query_result=query_result,
        )

        print()
        print(f"Intent  : {result.intent}")
        print(f"Builder : {result.builder}")
        print(f"Answer  : {result.answer}")


if __name__ == "__main__":
    main()