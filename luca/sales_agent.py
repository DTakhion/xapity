# luca/sales_agent.py
"""
Agente comercial determinista de Luca.

Flujo principal:

    pregunta del usuario
        ↓
    sales_intent_router.py
        ↓
    sales_query_service.py
        ↓
    construcción de respuesta
        ↓
    resultado estructurado

Esta primera versión permite ejecutar el agente directamente
desde terminal y deja preparado el contrato para FastAPI.

Capacidades actualmente conectadas:

- SALES_OVERVIEW
- TOTAL_RECEIVABLE
- CREDIT_NOTES
- CANCELLED_DOCUMENTS

Las demás intenciones reconocidas por el router retornan un estado
"not_implemented" hasta que su consulta determinista sea incorporada
en sales_query_service.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

from pymongo.collection import Collection

from luca.sales_intent_router import route_sales_intent
from luca.sales_intents import IntentResult, SalesIntent
from luca.sales_query_service import (
    get_cancelled_documents,
    get_credit_notes,
    get_sales_overview,
    get_total_receivable,
)

from luca.sales_response_builder import (
    build_sales_response_result,
)

# ==================================================
# TIPOS
# ==================================================


SalesQueryHandler = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class SalesAgentRequest:
    """
    Solicitud recibida por el agente comercial.
    """

    question: str
    business_id: int
    year: int | None = None
    month: int | None = None
    limit: int = 10


@dataclass(frozen=True, slots=True)
class SalesAgentResponse:
    """
    Respuesta estructurada del agente.

    Este contrato puede utilizarse directamente desde FastAPI.
    """

    status: str
    answer: str
    intent: str
    confidence: float
    entities: dict[str, Any]
    data: dict[str, Any] | None
    trace: dict[str, Any]
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convierte la respuesta a un diccionario serializable.
        """

        payload: dict[str, Any] = {
            "status": self.status,
            "answer": self.answer,
            "intent": self.intent,
            "confidence": self.confidence,
            "entities": dict(self.entities),
            "data": self.data,
            "trace": dict(self.trace),
        }

        if self.error is not None:
            payload["error"] = dict(self.error)

        return payload


# ==================================================
# REGISTRO DE CAPACIDADES
# ==================================================


QUERY_HANDLERS: dict[SalesIntent, SalesQueryHandler] = {
    SalesIntent.SALES_OVERVIEW: get_sales_overview,
    SalesIntent.TOTAL_RECEIVABLE: get_total_receivable,
    SalesIntent.CREDIT_NOTES: get_credit_notes,
    SalesIntent.CANCELLED_DOCUMENTS: get_cancelled_documents,
}


# ==================================================
# VALIDACIONES
# ==================================================


def _validate_request(
    request: SalesAgentRequest,
) -> None:
    if not isinstance(request.question, str):
        raise TypeError(
            "question debe ser un string."
        )

    if not request.question.strip():
        raise ValueError(
            "question no puede estar vacía."
        )

    if not isinstance(request.business_id, int):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if request.business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    if request.year is not None:
        if not isinstance(request.year, int):
            raise TypeError(
                "year debe ser un entero o None."
            )

        if request.year < 2000 or request.year > 2100:
            raise ValueError(
                "year debe estar entre 2000 y 2100."
            )

    if request.month is not None:
        if not isinstance(request.month, int):
            raise TypeError(
                "month debe ser un entero o None."
            )

        if request.month < 1 or request.month > 12:
            raise ValueError(
                "month debe estar entre 1 y 12."
            )

    if not isinstance(request.limit, int):
        raise TypeError(
            "limit debe ser un entero."
        )

    if request.limit <= 0:
        raise ValueError(
            "limit debe ser mayor que cero."
        )


# ==================================================
# FORMATO DE VALORES
# ==================================================


# def _format_clp(
#     value: Any,
# ) -> str:
#     """
#     Formatea un monto como peso chileno.

#     Ejemplo:
#         1250000 -> $1.250.000
#     """

#     try:
#         amount = round(float(value))
#     except (TypeError, ValueError):
#         amount = 0

#     formatted = f"{abs(amount):,}".replace(
#         ",",
#         ".",
#     )

#     sign = "-" if amount < 0 else ""

#     return f"{sign}${formatted}"


# def _format_period(
#     *,
#     year: int | None,
#     month: int | None,
# ) -> str:
#     """
#     Construye una descripción breve del período consultado.
#     """

#     month_names = {
#         1: "enero",
#         2: "febrero",
#         3: "marzo",
#         4: "abril",
#         5: "mayo",
#         6: "junio",
#         7: "julio",
#         8: "agosto",
#         9: "septiembre",
#         10: "octubre",
#         11: "noviembre",
#         12: "diciembre",
#     }

#     if year is not None and month is not None:
#         return (
#             f" durante {month_names[month]} "
#             f"de {year}"
#         )

#     if year is not None:
#         return f" durante {year}"

#     if month is not None:
#         return f" durante {month_names[month]}"

#     return ""


# ==================================================
# RESOLUCIÓN DE CONTEXTO
# ==================================================


def _resolve_query_parameters(
    *,
    request: SalesAgentRequest,
    intent_result: IntentResult,
) -> dict[str, Any]:
    """
    Combina parámetros explícitos con entidades del router.

    Prioridad:

    1. Parámetros explícitos del request.
    2. Entidades extraídas desde la pregunta.
    3. Valores por defecto.
    """

    entity_year = intent_result.get_entity(
        "year"
    )
    entity_month = intent_result.get_entity(
        "month"
    )
    entity_limit = intent_result.get_entity(
        "limit"
    )

    year = (
        request.year
        if request.year is not None
        else entity_year
    )

    month = (
        request.month
        if request.month is not None
        else entity_month
    )

    limit = (
        entity_limit
        if entity_limit is not None
        else request.limit
    )

    return {
        "business_id": request.business_id,
        "year": year,
        "month": month,
        "limit": limit,
    }


def _build_handler_kwargs(
    *,
    intent: SalesIntent,
    query_parameters: dict[str, Any],
    collection: Collection | None,
) -> dict[str, Any]:
    """
    Construye únicamente los argumentos aceptados por cada handler.
    """

    kwargs: dict[str, Any] = {
        "business_id": query_parameters[
            "business_id"
        ],
        "year": query_parameters["year"],
        "month": query_parameters["month"],
    }

    if collection is not None:
        kwargs["collection"] = collection

    intents_with_limit = {
        SalesIntent.CREDIT_NOTES,
        SalesIntent.CANCELLED_DOCUMENTS,
    }

    if intent in intents_with_limit:
        kwargs["limit"] = query_parameters[
            "limit"
        ]

    return kwargs


# ==================================================
# CONSTRUCCIÓN DE RESPUESTAS
# ==================================================


# def _build_sales_overview_answer(
#     query_result: dict[str, Any],
# ) -> str:
#     result = query_result.get(
#         "result",
#         {},
#     )

#     filters = query_result.get(
#         "filters",
#         {},
#     )

#     period = _format_period(
#         year=filters.get("year"),
#         month=filters.get("month"),
#     )

#     total_documents = result.get(
#         "totalDocuments",
#         0,
#     )

#     total_amount = result.get(
#         "totalAmount",
#         0,
#     )

#     receivable_documents = result.get(
#         "receivableDocuments",
#         0,
#     )

#     receivable_amount = result.get(
#         "receivableAmount",
#         0,
#     )

#     unique_customers = result.get(
#         "uniqueCustomers",
#         0,
#     )

#     credit_notes = result.get(
#         "creditNotes",
#         0,
#     )

#     return (
#         f"El resumen comercial{period} registra "
#         f"{total_documents} documentos por un total de "
#         f"{_format_clp(total_amount)}. "
#         f"Actualmente hay {receivable_documents} documentos "
#         f"por cobrar, equivalentes a "
#         f"{_format_clp(receivable_amount)}. "
#         f"Los documentos corresponden a "
#         f"{unique_customers} clientes únicos y existen "
#         f"{credit_notes} notas de crédito."
#     )


# def _build_total_receivable_answer(
#     query_result: dict[str, Any],
# ) -> str:
#     result = query_result.get(
#         "result",
#         {},
#     )

#     filters = query_result.get(
#         "filters",
#         {},
#     )

#     period = _format_period(
#         year=filters.get("year"),
#         month=filters.get("month"),
#     )

#     documents_count = result.get(
#         "documentsCount",
#         0,
#     )

#     total_amount = result.get(
#         "totalAmount",
#         0,
#     )

#     if documents_count == 0:
#         return (
#             f"No encontré documentos por cobrar"
#             f"{period}."
#         )

#     document_word = (
#         "documento"
#         if documents_count == 1
#         else "documentos"
#     )

#     return (
#         f"Tienes {_format_clp(total_amount)} por cobrar"
#         f"{period}, distribuidos en "
#         f"{documents_count} {document_word}."
#     )


# def _build_credit_notes_answer(
#     query_result: dict[str, Any],
# ) -> str:
#     result = query_result.get(
#         "result",
#         {},
#     )

#     filters = query_result.get(
#         "filters",
#         {},
#     )

#     period = _format_period(
#         year=filters.get("year"),
#         month=filters.get("month"),
#     )

#     documents_count = result.get(
#         "documentsCount",
#         0,
#     )

#     total_amount = result.get(
#         "totalAmount",
#         0,
#     )

#     if documents_count == 0:
#         return (
#             f"No encontré notas de crédito"
#             f"{period}."
#         )

#     note_word = (
#         "nota de crédito"
#         if documents_count == 1
#         else "notas de crédito"
#     )

#     return (
#         f"Encontré {documents_count} {note_word}"
#         f"{period}, por un monto total de "
#         f"{_format_clp(total_amount)}."
#     )


# def _build_cancelled_documents_answer(
#     query_result: dict[str, Any],
# ) -> str:
#     result = query_result.get(
#         "result",
#         {},
#     )

#     filters = query_result.get(
#         "filters",
#         {},
#     )

#     period = _format_period(
#         year=filters.get("year"),
#         month=filters.get("month"),
#     )

#     documents_count = result.get(
#         "documentsCount",
#         0,
#     )

#     total_amount = result.get(
#         "totalAmount",
#         0,
#     )

#     if documents_count == 0:
#         return (
#             f"No encontré documentos anulados"
#             f"{period}."
#         )

#     document_word = (
#         "documento anulado"
#         if documents_count == 1
#         else "documentos anulados"
#     )

#     return (
#         f"Encontré {documents_count} {document_word}"
#         f"{period}, por un monto total de "
#         f"{_format_clp(total_amount)}."
#     )


# def _build_answer(
#     *,
#     intent: SalesIntent,
#     query_result: dict[str, Any],
# ) -> str:
#     """
#     Construye una respuesta natural determinista.
#     """

#     builders: dict[
#         SalesIntent,
#         Callable[[dict[str, Any]], str],
#     ] = {
#         SalesIntent.SALES_OVERVIEW: (
#             _build_sales_overview_answer
#         ),
#         SalesIntent.TOTAL_RECEIVABLE: (
#             _build_total_receivable_answer
#         ),
#         SalesIntent.CREDIT_NOTES: (
#             _build_credit_notes_answer
#         ),
#         SalesIntent.CANCELLED_DOCUMENTS: (
#             _build_cancelled_documents_answer
#         ),
#     }

#     builder = builders.get(intent)

#     if builder is None:
#         return (
#             "La consulta fue reconocida, pero todavía no "
#             "dispone de un constructor de respuesta."
#         )

#     return builder(query_result)


# ==================================================
# RESPUESTAS DE CONTROL
# ==================================================


def _unknown_response(
    *,
    intent_result: IntentResult,
    elapsed_ms: float,
) -> SalesAgentResponse:
    return SalesAgentResponse(
        status="unknown_intent",
        answer=(
            "No pude identificar con seguridad la consulta "
            "comercial. Puedes preguntarme, por ejemplo, "
            "cuánto dinero tienes por cobrar, solicitar un "
            "resumen de ventas o consultar las notas de crédito."
        ),
        intent=SalesIntent.UNKNOWN.value,
        confidence=intent_result.confidence,
        entities=dict(intent_result.entities),
        data=None,
        trace={
            "matchedRule": intent_result.matched_rule,
            "source": "sales_intent_router",
            "deterministic": True,
            "elapsedMs": elapsed_ms,
        },
    )


def _not_implemented_response(
    *,
    intent_result: IntentResult,
    query_parameters: dict[str, Any],
    elapsed_ms: float,
) -> SalesAgentResponse:
    return SalesAgentResponse(
        status="not_implemented",
        answer=(
            "Entendí la consulta, pero esta capacidad comercial "
            "todavía no está conectada al servicio de datos."
        ),
        intent=intent_result.intent.value,
        confidence=intent_result.confidence,
        entities={
            **intent_result.entities,
            "year": query_parameters["year"],
            "month": query_parameters["month"],
        },
        data=None,
        trace={
            "matchedRule": intent_result.matched_rule,
            "source": "sales_intent_router",
            "deterministic": True,
            "implemented": False,
            "elapsedMs": elapsed_ms,
        },
    )


def _error_response(
    *,
    intent_result: IntentResult,
    error: Exception,
    elapsed_ms: float,
) -> SalesAgentResponse:
    return SalesAgentResponse(
        status="error",
        answer=(
            "No pude completar la consulta comercial debido "
            "a un error al acceder o procesar los datos."
        ),
        intent=intent_result.intent.value,
        confidence=intent_result.confidence,
        entities=dict(intent_result.entities),
        data=None,
        trace={
            "matchedRule": intent_result.matched_rule,
            "source": "sales_agent",
            "deterministic": True,
            "elapsedMs": elapsed_ms,
        },
        error={
            "type": type(error).__name__,
            "message": str(error),
        },
    )


# ==================================================
# AGENTE
# ==================================================


class SalesAgent:
    """
    Orquestador del agente comercial determinista.
    """

    def __init__(
        self,
        *,
        collection: Collection | None = None,
    ) -> None:
        """
        collection permite inyectar una colección Mongo durante tests.
        """

        self._collection = collection

    def ask(
        self,
        *,
        question: str,
        business_id: int,
        year: int | None = None,
        month: int | None = None,
        limit: int = 10,
        raise_errors: bool = False,
    ) -> SalesAgentResponse:
        """
        Procesa una pregunta comercial.

        Parameters
        ----------
        question:
            Pregunta escrita por el usuario.

        business_id:
            Empresa sobre la cual se realiza la consulta.

        year:
            Filtro anual explícito. Tiene prioridad sobre el
            año extraído desde la pregunta.

        month:
            Filtro mensual explícito. Tiene prioridad sobre el
            mes extraído desde la pregunta.

        limit:
            Cantidad máxima de documentos en consultas de detalle.

        raise_errors:
            Si es True, propaga excepciones. Es útil durante desarrollo.
            Si es False, retorna una respuesta estructurada de error.
        """

        started_at = time.perf_counter()

        request = SalesAgentRequest(
            question=question,
            business_id=business_id,
            year=year,
            month=month,
            limit=limit,
        )

        try:
            _validate_request(request)

            intent_result = route_sales_intent(
                request.question
            )

            elapsed_ms = (
                time.perf_counter() - started_at
            ) * 1000

            if intent_result.is_unknown:
                return _unknown_response(
                    intent_result=intent_result,
                    elapsed_ms=round(
                        elapsed_ms,
                        3,
                    ),
                )

            query_parameters = (
                _resolve_query_parameters(
                    request=request,
                    intent_result=intent_result,
                )
            )

            handler = QUERY_HANDLERS.get(
                intent_result.intent
            )

            if handler is None:
                return _not_implemented_response(
                    intent_result=intent_result,
                    query_parameters=query_parameters,
                    elapsed_ms=round(
                        elapsed_ms,
                        3,
                    ),
                )

            handler_kwargs = _build_handler_kwargs(
                intent=intent_result.intent,
                query_parameters=query_parameters,
                collection=self._collection,
            )

            query_result = handler(
                **handler_kwargs
            )

            response_build_result = (
                build_sales_response_result(
                    intent=intent_result.intent,
                    query_result=query_result,
                )
            )
            
            answer = response_build_result.answer

            elapsed_ms = (
                time.perf_counter() - started_at
            ) * 1000

            return SalesAgentResponse(
                status="answered",
                answer=answer,
                intent=intent_result.intent.value,
                confidence=intent_result.confidence,
                entities={
                    **intent_result.entities,
                    "year": query_parameters["year"],
                    "month": query_parameters["month"],
                },
                data=query_result.get("result"),
                trace={
                    "matchedRule": (
                        intent_result.matched_rule
                    ),
                    "queryType": query_result.get(
                        "queryType"
                    ),
                    "source": query_result.get(
                        "metadata",
                        {},
                    ).get(
                        "source"
                    ),
                    "generatedAt": query_result.get(
                        "metadata",
                        {},
                    ).get(
                        "generatedAt"
                    ),
                    "responseBuilder": (
                        response_build_result.builder
                    ),
                    "deterministic": True,
                    "elapsedMs": round(
                        elapsed_ms,
                        3,
                    ),
                },
            )

        except Exception as error:
            if raise_errors:
                raise

            elapsed_ms = (
                time.perf_counter() - started_at
            ) * 1000

            fallback_intent = IntentResult.unknown(
                original_question=question,
                normalized_question=None,
                matched_rule="agent_error",
            )

            return _error_response(
                intent_result=fallback_intent,
                error=error,
                elapsed_ms=round(
                    elapsed_ms,
                    3,
                ),
            )


# ==================================================
# FUNCIÓN PÚBLICA
# ==================================================


_default_agent = SalesAgent()


def ask_sales_agent(
    *,
    question: str,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    limit: int = 10,
    raise_errors: bool = False,
) -> dict[str, Any]:
    """
    Interfaz simplificada para FastAPI y otros servicios.
    """

    response = _default_agent.ask(
        question=question,
        business_id=business_id,
        year=year,
        month=month,
        limit=limit,
        raise_errors=raise_errors,
    )

    return response.to_dict()


# ==================================================
# TERMINAL
# ==================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Agente comercial determinista de Luca."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python3 -m luca.sales_agent \\
      --business-id 5 \\
      --question "¿Cuánto dinero tengo por cobrar?"

  python3 -m luca.sales_agent \\
      --business-id 5 \\
      --question "Dame un resumen general de las ventas"

  python3 -m luca.sales_agent \\
      --business-id 5 \\
      --question "Muéstrame las notas de crédito de enero de 2026"

  python3 -m luca.sales_agent \\
      --business-id 5 \\
      --question "¿Qué documentos fueron anulados?" \\
      --limit 20

  python3 -m luca.sales_agent \\
      --business-id 5 \\
      --question "¿Cuánto dinero tengo por cobrar?" \\
      --json
""",
    )

    parser.add_argument(
        "--business-id",
        type=int,
        required=True,
        help="Identificador de la empresa.",
    )

    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="Pregunta comercial del usuario.",
    )

    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Filtro anual explícito.",
    )

    parser.add_argument(
        "--month",
        type=int,
        default=None,
        help="Filtro mensual explícito.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=(
            "Máximo de documentos retornados. "
            "Por defecto: 10"
        ),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Muestra solamente el JSON final.",
    )

    parser.add_argument(
        "--raise-errors",
        action="store_true",
        help=(
            "Propaga errores en lugar de convertirlos "
            "en una respuesta estructurada."
        ),
    )

    return parser


def print_response(
    response: SalesAgentResponse,
) -> None:
    """
    Presenta la respuesta como la recibiría el usuario.
    """

    print()
    print("=" * 88)
    print("XAPITY — AGENTE COMERCIAL")
    print("=" * 88)
    print(f"Estado    : {response.status}")
    print(f"Intent    : {response.intent}")
    print(f"Confianza : {response.confidence}")
    print()
    print("Respuesta:")
    print(response.answer)
    print()
    print("Entidades:")
    print(
        json.dumps(
            response.entities,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print()
    print("Datos:")
    print(
        json.dumps(
            response.data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print()
    print("Trace:")
    print(
        json.dumps(
            response.trace,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    if response.error:
        print()
        print("Error:")
        print(
            json.dumps(
                response.error,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    agent = SalesAgent()

    response = agent.ask(
        question=args.question,
        business_id=args.business_id,
        year=args.year,
        month=args.month,
        limit=args.limit,
        raise_errors=args.raise_errors,
    )

    if args.json:
        print(
            json.dumps(
                response.to_dict(),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print_response(response)

    if response.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()