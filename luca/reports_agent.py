# luca/reports_agent.py

"""
Agente determinista de reportes de Luca.

Flujo principal:

    pregunta del usuario
        ↓
    reports_intent_router.py
        ↓
    reports_query_service.py
        ↓
    reports_response_builder.py
        ↓
    resultado estructurado

El agente consulta exclusivamente reportes previamente
sincronizados y persistidos en MongoDB.

No consulta Luca API durante una interacción normal.

Capacidades actualmente conectadas:

- GENERAL_BALANCE

Las demás intenciones reconocidas en el futuro por el router
retornarán un estado "not_implemented" hasta que su consulta
determinista sea incorporada en reports_query_service.py.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any, Callable


from luca.reports_intent_router import (
    route_reports_intent,
)

from luca.reports_intents import (
    ReportsIntent,
    ReportsIntentResult,
    ReportsOperation,
)

from luca.reports_query_service import (
    ReportsQueryResult,
    query_general_balance,
)

from luca.reports_response_builder import (
    build_reports_response_result,
)
from luca.reports_execute_service import (
    ReportsExecuteResult,
    prepare_general_balance_email,
)
from db.mongo_persistence_luca import (
    create_pending_action,
)


# ==================================================
# TIPOS
# ==================================================


ReportsQueryHandler = Callable[
    ...,
    ReportsQueryResult,
]

ReportsExecuteHandler = Callable[
    ...,
    ReportsExecuteResult,
]


@dataclass(
    frozen=True,
    slots=True,
)
class ReportsAgentRequest:
    """
    Solicitud recibida por el agente de reportes.
    """

    question: str
    business_id: int
    query_from: str | None = None
    query_to: str | None = None
    limit: int = 10


@dataclass(
    frozen=True,
    slots=True,
)
class ReportsAgentResponse:
    """
    Respuesta estructurada del agente de reportes.

    Este contrato puede utilizarse directamente
    desde FastAPI y desde XapityAgent.
    """

    status: str
    answer: str
    intent: str
    confidence: float
    entities: dict[str, Any]
    data: dict[str, Any] | None
    trace: dict[str, Any]
    error: dict[str, Any] | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convierte la respuesta a un diccionario serializable.
        """

        payload: dict[str, Any] = {
            "status": self.status,
            "answer": self.answer,
            "intent": self.intent,
            "confidence": self.confidence,
            "entities": dict(
                self.entities
            ),
            "data": self.data,
            "trace": dict(
                self.trace
            ),
        }

        if self.error is not None:
            payload["error"] = dict(
                self.error
            )

        return payload


# ==================================================
# REGISTRO DE CAPACIDADES
# ==================================================


QUERY_HANDLERS: dict[
    ReportsIntent,
    ReportsQueryHandler,
] = {
    ReportsIntent.GENERAL_BALANCE:
        query_general_balance,
}

EXECUTE_HANDLERS: dict[
    ReportsIntent,
    ReportsExecuteHandler,
] = {
    ReportsIntent.GENERAL_BALANCE:
        prepare_general_balance_email,
}


def _resolve_query_handler(
    *,
    intent: ReportsIntent,
) -> ReportsQueryHandler | None:
    """
    Resuelve el handler determinista
    de consulta asociado a una intención.
    """

    return QUERY_HANDLERS.get(
        intent
    )


def _resolve_execute_handler(
    *,
    intent: ReportsIntent,
) -> ReportsExecuteHandler | None:
    """
    Resuelve el handler determinista
    de ejecución asociado a una intención.
    """

    return EXECUTE_HANDLERS.get(
        intent
    )


# ==================================================
# VALIDACIONES
# ==================================================


def _validate_request(
    request: ReportsAgentRequest,
) -> None:
    if not isinstance(
        request.question,
        str,
    ):
        raise TypeError(
            "question debe ser un string."
        )

    if not request.question.strip():
        raise ValueError(
            "question no puede estar vacía."
        )

    if isinstance(
        request.business_id,
        bool,
    ) or not isinstance(
        request.business_id,
        int,
    ):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if request.business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    if (
        request.query_from
        is not None
        and not isinstance(
            request.query_from,
            str,
        )
    ):
        raise TypeError(
            "query_from debe ser string o None."
        )

    if (
        request.query_to
        is not None
        and not isinstance(
            request.query_to,
            str,
        )
    ):
        raise TypeError(
            "query_to debe ser string o None."
        )

    if (
        request.query_from is None
        and request.query_to is not None
    ):
        raise ValueError(
            "query_from y query_to deben "
            "informarse juntos."
        )

    if (
        request.query_from is not None
        and request.query_to is None
    ):
        raise ValueError(
            "query_from y query_to deben "
            "informarse juntos."
        )

    if isinstance(
        request.limit,
        bool,
    ) or not isinstance(
        request.limit,
        int,
    ):
        raise TypeError(
            "limit debe ser un entero."
        )

    if request.limit <= 0:
        raise ValueError(
            "limit debe ser mayor que cero."
        )


# ==================================================
# RESOLUCIÓN DE CONTEXTO
# ==================================================


def _resolve_query_parameters(
    *,
    request: ReportsAgentRequest,
    intent_result: ReportsIntentResult,
) -> dict[str, Any]:
    """
    Combina parámetros explícitos del request
    con las entidades detectadas por el router.

    En esta primera versión:

    - query_from/query_to explícitos tienen prioridad.
    - Si no existen fechas explícitas, se consulta
      el snapshot más reciente disponible en Mongo.
    - dateScope="today" NO genera artificialmente
      un período inexistente en Mongo.
    - limit controla la cantidad de cuentas destacadas
      en los rankings del análisis.

    El período real utilizado será informado por
    ReportsQueryResult.
    """

    return {
        "business_id": (
            request.business_id
        ),
        "query_from": (
            request.query_from
        ),
        "query_to": (
            request.query_to
        ),
        "top_limit": (
            request.limit
        ),
    }


def _build_handler_kwargs(
    *,
    intent: ReportsIntent,
    query_parameters: dict[str, Any],
) -> dict[str, Any]:
    """
    Construye únicamente los argumentos aceptados
    por cada handler de reportes.
    """

    kwargs: dict[str, Any] = {
        "business_id": (
            query_parameters[
                "business_id"
            ]
        ),
        "query_from": (
            query_parameters[
                "query_from"
            ]
        ),
        "query_to": (
            query_parameters[
                "query_to"
            ]
        ),
    }

    intents_with_limit = {
        ReportsIntent.GENERAL_BALANCE,
    }

    if intent in intents_with_limit:
        kwargs["top_limit"] = (
            query_parameters[
                "top_limit"
            ]
        )

    return kwargs

def _build_execute_handler_kwargs(
    *,
    request: ReportsAgentRequest,
    intent_result: ReportsIntentResult,
) -> dict[str, Any]:
    """
    Construye los argumentos aceptados
    por los handlers de ejecución.
    """

    return {
        "business_id": (
            request.business_id
        ),
        "query_from": (
            request.query_from
        ),
        "query_to": (
            request.query_to
        ),
        "report_format": (
            intent_result.get_entity(
                "format",
                "xlsx",
            )
        ),
    }


# ==================================================
# RESPUESTAS DE CONTROL
# ==================================================


def _not_handled_response(
    *,
    intent_result: ReportsIntentResult,
    elapsed_ms: float,
) -> ReportsAgentResponse:
    """
    La consulta no pertenece al dominio de reportes.

    No se considera un error.

    XapityAgent puede continuar intentando con
    otros agentes especializados.
    """

    return ReportsAgentResponse(
        status="not_handled",
        answer="",
        intent=ReportsIntent.UNKNOWN.value,
        confidence=(
            intent_result.confidence
        ),
        entities=dict(
            intent_result.entities
        ),
        data=None,
        trace={
            "matchedRule": (
                intent_result.matched_rule
            ),
            "source": (
                "reports_intent_router"
            ),
            "responseBuilder": None,
            "deterministic": True,
            "handled": False,
            "elapsedMs": elapsed_ms,
        },
    )


def _not_implemented_response(
    *,
    intent_result: ReportsIntentResult,
    elapsed_ms: float,
) -> ReportsAgentResponse:
    """
    La intención fue reconocida, pero aún no tiene
    un handler de consulta conectado.
    """

    return ReportsAgentResponse(
        status="not_implemented",
        answer=(
            "Entendí la acción solicitada sobre el reporte, "
            "pero esta capacidad todavía no está implementada."
        ),
        intent=(
            intent_result.intent.value
        ),
        confidence=(
            intent_result.confidence
        ),
        entities=dict(
            intent_result.entities
        ),
        data=None,
        trace={
            "matchedRule": (
                intent_result.matched_rule
            ),
            "operation": (
                intent_result.operation.value
            ),
            "source": (
                "reports_intent_router"
            ),
            "responseBuilder": None,
            "deterministic": True,
            "handled": True,
            "implemented": False,
            "elapsedMs": elapsed_ms,
        },
    )

def _pending_confirmation_response(
    *,
    intent_result: ReportsIntentResult,
    execute_result: ReportsExecuteResult,
    pending_action: dict[str, Any],
    elapsed_ms: float,
) -> ReportsAgentResponse:
    """
    Construye la respuesta cuando una ejecución
    fue preparada correctamente pero aún requiere
    confirmación explícita del usuario.
    """

    data = execute_result.data

    recipient_email = (
        data.get(
            "recipientEmail"
        )
    )

    report_format = (
        data.get(
            "format"
        )
    )

    snapshot = (
        data.get(
            "snapshot"
        )
        or {}
    )
    
    action_id = (
        pending_action.get(
            "actionId"
        )
    )

    expires_at = (
        pending_action.get(
            "expiresAt"
        )
    )

    query_from = (
        snapshot.get(
            "queryFrom"
        )
    )

    query_to = (
        snapshot.get(
            "queryTo"
        )
    )

    format_label = (
        "Excel"
        if report_format == "xlsx"
        else str(
            report_format
        ).upper()
    )

    answer = (
        "Enviaré el Balance General "
        f"correspondiente al período "
        f"{query_from} a {query_to} "
        f"a {recipient_email} "
        f"en formato {format_label}. "
        "¿Confirmas el envío?"
    )

    resolved_entities = {
        **intent_result.entities,
        "queryFrom": (
            query_from
        ),
        "queryTo": (
            query_to
        ),
        "recipientEmail": (
            recipient_email
        ),
    }

    return ReportsAgentResponse(
        status="pending_confirmation",
        answer=answer,
        intent=(
            intent_result.intent.value
        ),
        confidence=(
            intent_result.confidence
        ),
        entities=resolved_entities,
        data={
            **execute_result.data,
            "pendingAction": {
                "actionId": (
                    action_id
                ),
                "status": (
                    pending_action.get(
                        "status"
                    )
                ),
                "expiresAt": (
                    expires_at
                ),
            },
        },
        trace={
            "matchedRule": (
                intent_result.matched_rule
            ),
            "operation": (
                intent_result.operation.value
            ),
            "executionType": (
                execute_result.execution_type
            ),
            "source": (
                execute_result.source
            ),
            "queryFrom": (
                query_from
            ),
            "queryTo": (
                query_to
            ),
            "mongoId": (
                execute_result.trace.get(
                    "mongoId"
                )
            ),
            "version": (
                execute_result.trace.get(
                    "version"
                )
            ),
            "contentHash": (
                execute_result.trace.get(
                    "contentHash"
                )
            ),
            "loadedAt": (
                execute_result.trace.get(
                    "loadedAt"
                )
            ),
            "recipientUserId": (
                execute_result.trace.get(
                    "recipientUserId"
                )
            ),
            "deliveryChannel": (
                execute_result.trace.get(
                    "deliveryChannel"
                )
            ),
            "format": (
                execute_result.trace.get(
                    "format"
                )
            ),
            "requiresConfirmation": True,
            "executed": False,
            "pendingActionId": (
                action_id
            ),
            "pendingActionExpiresAt": (
                expires_at
            ),
            "responseBuilder": (
                "_pending_confirmation_response"
            ),
            "deterministic": True,
            "handled": True,
            "elapsedMs": elapsed_ms,
        },
    )


def _error_response(
    *,
    intent_result: ReportsIntentResult,
    error: Exception,
    elapsed_ms: float,
) -> ReportsAgentResponse:
    """
    Construye una respuesta de error controlada.
    """

    return ReportsAgentResponse(
        status="error",
        answer=(
            "No pude completar la consulta de reportes "
            "debido a un error al acceder o procesar "
            "los datos."
        ),
        intent=(
            intent_result.intent.value
        ),
        confidence=(
            intent_result.confidence
        ),
        entities=dict(
            intent_result.entities
        ),
        data=None,
        trace={
            "matchedRule": (
                intent_result.matched_rule
            ),
            "source": (
                "reports_agent"
            ),
            "responseBuilder": None,
            "deterministic": True,
            "handled": True,
            "elapsedMs": elapsed_ms,
        },
        error={
            "type": (
                type(error).__name__
            ),
            "message": str(
                error
            ),
        },
    )


# ==================================================
# AGENTE
# ==================================================


class ReportsAgent:
    """
    Orquestador del agente determinista de reportes.
    """

    def ask(
        self,
        *,
        question: str,
        business_id: int,
        query_from: str | None = None,
        query_to: str | None = None,
        limit: int = 10,
        raise_errors: bool = False,
    ) -> ReportsAgentResponse:
        """
        Procesa una pregunta relacionada con reportes.

        Parameters
        ----------
        question:
            Pregunta escrita por el usuario.

        business_id:
            Empresa sobre la cual se realiza
            la consulta.

        query_from:
            Fecha inicial explícita del reporte
            en formato YYYY-MM-DD.

            Si no se informa, se utilizará el
            snapshot más reciente disponible.

        query_to:
            Fecha final explícita del reporte
            en formato YYYY-MM-DD.

            Debe utilizarse junto con query_from.

        limit:
            Cantidad máxima de cuentas destacadas
            en rankings del análisis.

        raise_errors:
            Si es True, propaga excepciones.

            Es útil durante desarrollo.

            Si es False, retorna una respuesta
            estructurada de error.
        """

        started_at = (
            time.perf_counter()
        )

        request = ReportsAgentRequest(
            question=question,
            business_id=business_id,
            query_from=query_from,
            query_to=query_to,
            limit=limit,
        )

        try:
            _validate_request(
                request
            )

            intent_result = (
                route_reports_intent(
                    request.question
                )
            )

            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000

            if intent_result.is_unknown:
                return (
                    _not_handled_response(
                        intent_result=(
                            intent_result
                        ),
                        elapsed_ms=round(
                            elapsed_ms,
                            3,
                        ),
                    )
                )
            
            if (
                intent_result.operation
                == ReportsOperation.EXECUTE
            ):
                execute_handler = (
                    _resolve_execute_handler(
                        intent=(
                            intent_result.intent
                        ),
                    )
                )

                if execute_handler is None:
                    return (
                        _not_implemented_response(
                            intent_result=(
                                intent_result
                            ),
                            elapsed_ms=round(
                                elapsed_ms,
                                3,
                            ),
                        )
                    )

                execute_kwargs = (
                    _build_execute_handler_kwargs(
                        request=request,
                        intent_result=(
                            intent_result
                        ),
                    )
                )

                execute_result = (
                    execute_handler(
                        **execute_kwargs
                    )
                )

                recipient_user_id = (
                    execute_result.trace.get(
                        "recipientUserId"
                    )
                )

                if (
                    isinstance(
                        recipient_user_id,
                        bool,
                    )
                    or not isinstance(
                        recipient_user_id,
                        int,
                    )
                    or recipient_user_id <= 0
                ):
                    raise RuntimeError(
                        "No se pudo resolver el usuario autenticado "
                        "para persistir la acción pendiente."
                    )

                pending_action = (
                    create_pending_action(
                        business_id=(
                            request.business_id
                        ),
                        user_id=(
                            recipient_user_id
                        ),
                        action_type=(
                            execute_result.execution_type
                        ),
                        payload=dict(
                            execute_result.data
                        ),
                        original_question=(
                            request.question
                        ),
                    )
                )

                elapsed_ms = (
                    time.perf_counter()
                    - started_at
                ) * 1000

                return (
                    _pending_confirmation_response(
                        intent_result=(
                            intent_result
                        ),
                        execute_result=(
                            execute_result
                        ),
                        pending_action=(
                            pending_action
                        ),
                        elapsed_ms=round(
                            elapsed_ms,
                            3,
                        ),
                    )
                )

            query_parameters = (
                _resolve_query_parameters(
                    request=request,
                    intent_result=(
                        intent_result
                    ),
                )
            )

            handler = _resolve_query_handler(
                intent=(
                    intent_result.intent
                ),
            )

            if handler is None:
                return (
                    _not_implemented_response(
                        intent_result=(
                            intent_result
                        ),
                        elapsed_ms=round(
                            elapsed_ms,
                            3,
                        ),
                    )
                )

            handler_kwargs = (
                _build_handler_kwargs(
                    intent=(
                        intent_result.intent
                    ),
                    query_parameters=(
                        query_parameters
                    ),
                )
            )

            query_result = handler(
                **handler_kwargs
            )

            response_build_result = (
                build_reports_response_result(
                    intent=(
                        intent_result.intent
                    ),
                    query_result=(
                        query_result
                    ),
                )
            )

            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000

            resolved_entities = {
                **intent_result.entities,
                "queryFrom": (
                    query_result.query_from
                ),
                "queryTo": (
                    query_result.query_to
                ),
            }

            return ReportsAgentResponse(
                status="answered",
                answer=(
                    response_build_result.answer
                ),
                intent=(
                    intent_result.intent.value
                ),
                confidence=(
                    intent_result.confidence
                ),
                entities=resolved_entities,
                data=(
                    query_result.data
                ),
                trace={
                    "matchedRule": (
                        intent_result.matched_rule
                    ),
                    "operation": (
                        intent_result.operation.value
                    ),
                    "executionType": (
                        query_result.report_type
                    ),
                    "source": (
                        query_result.source
                    ),
                    "queryFrom": (
                        query_result.query_from
                    ),
                    "queryTo": (
                        query_result.query_to
                    ),
                    "mongoId": (
                        query_result.trace.get(
                            "mongoId"
                        )
                    ),
                    "version": (
                        query_result.trace.get(
                            "version"
                        )
                    ),
                    "contentHash": (
                        query_result.trace.get(
                            "contentHash"
                        )
                    ),
                    "loadedAt": (
                        query_result.trace.get(
                            "loadedAt"
                        )
                    ),
                    "responseBuilder": (
                        response_build_result.builder
                    ),
                    "deterministic": True,
                    "handled": True,
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
                time.perf_counter()
                - started_at
            ) * 1000

            fallback_intent = (
                ReportsIntentResult.unknown(
                    original_question=(
                        question
                    ),
                    normalized_question="",
                )
            )

            return _error_response(
                intent_result=(
                    fallback_intent
                ),
                error=error,
                elapsed_ms=round(
                    elapsed_ms,
                    3,
                ),
            )


# ==================================================
# FUNCIÓN PÚBLICA
# ==================================================


_default_agent = ReportsAgent()


def ask_reports_agent(
    *,
    question: str,
    business_id: int,
    query_from: str | None = None,
    query_to: str | None = None,
    limit: int = 10,
    raise_errors: bool = False,
) -> dict[str, Any]:
    """
    Interfaz simplificada para FastAPI,
    XapityAgent y otros servicios.
    """

    response = _default_agent.ask(
        question=question,
        business_id=business_id,
        query_from=query_from,
        query_to=query_to,
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
            "Agente determinista de reportes "
            "de Luca."
        ),
        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),
        epilog="""
Ejemplos:

  python3 -m luca.reports_agent \\
      --business-id 70 \\
      --question "Muéstrame el balance general"

  python3 -m luca.reports_agent \\
      --business-id 70 \\
      --question "Dame un resumen del balance general"

  python3 -m luca.reports_agent \\
      --business-id 70 \\
      --question "Entrégame el balance general de la empresa al día de hoy"

  python3 -m luca.reports_agent \\
      --business-id 70 \\
      --question "Muéstrame el balance general" \\
      --query-from 2026-01-01 \\
      --query-to 2026-09-04

  python3 -m luca.reports_agent \\
      --business-id 70 \\
      --question "Muéstrame el balance general" \\
      --json
""",
    )

    parser.add_argument(
        "--business-id",
        type=int,
        required=True,
        help=(
            "Identificador de la empresa."
        ),
    )

    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help=(
            "Pregunta de reportes del usuario."
        ),
    )

    parser.add_argument(
        "--query-from",
        type=str,
        default=None,
        help=(
            "Fecha inicial explícita "
            "en formato YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--query-to",
        type=str,
        default=None,
        help=(
            "Fecha final explícita "
            "en formato YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=(
            "Máximo de cuentas destacadas "
            "por ranking. Por defecto: 10"
        ),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Muestra solamente el JSON final."
        ),
    )

    parser.add_argument(
        "--raise-errors",
        action="store_true",
        help=(
            "Propaga errores en lugar de "
            "convertirlos en una respuesta "
            "estructurada."
        ),
    )

    return parser


def print_response(
    response: ReportsAgentResponse,
) -> None:
    """
    Presenta la respuesta como la recibiría
    el usuario.
    """

    print()
    print("=" * 88)
    print(
        "XAPITY — AGENTE DE REPORTES"
    )
    print("=" * 88)

    print(
        f"Estado    : {response.status}"
    )

    print(
        f"Intent    : {response.intent}"
    )

    print(
        f"Confianza : {response.confidence}"
    )

    print()
    print("Respuesta:")
    print(
        response.answer
    )

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

    agent = ReportsAgent()

    response = agent.ask(
        question=args.question,
        business_id=args.business_id,
        query_from=args.query_from,
        query_to=args.query_to,
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
        print_response(
            response
        )

    if response.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()