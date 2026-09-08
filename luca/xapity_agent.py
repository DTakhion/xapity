# luca/xapity_agent.py

"""
Orquestador global de agentes para Xapity.

Responsabilidades:

- Recibir una consulta general del usuario.
- Delegarla al agente conversacional.
- Si no es resuelta, delegarla al agente comercial.
- Si no es resuelta, delegarla al agente de reportes.
- Unificar la respuesta final.
- Registrar en trace qué agente resolvió la interacción.
- Proveer un fallback global cuando ningún agente reconoce la consulta.

Este módulo NO:

- clasifica intenciones específicas;
- consulta bases de datos directamente;
- ejecuta reglas comerciales o contables;
- construye respuestas específicas de dominio;
- reemplaza a los agentes especializados.

Los agentes especializados mantienen sus propias responsabilidades.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

from luca.conversation_agent import (
    ask_conversation_agent,
)

from luca.sales_agent import (
    ask_sales_agent,
)

from luca.reports_agent import (
    ask_reports_agent,
)
from luca.luca_user_service import (
    get_luca_current_user,
)

from db.mongo_persistence_luca import (
    cancel_pending_action,
    confirm_pending_action,
    find_pending_action,
)


# ==================================================
# MODELOS
# ==================================================


@dataclass(
    frozen=True,
    slots=True,
)
class XapityAgentRequest:
    """
    Solicitud recibida por el orquestador global.

    Los parámetros específicos de dominio se mantienen
    en este contrato porque XapityAgent debe ser capaz
    de delegarlos al agente correspondiente.
    """

    question: str
    business_id: int

    year: int | None = None
    month: int | None = None

    query_from: str | None = None
    query_to: str | None = None

    limit: int = 10


@dataclass(
    frozen=True,
    slots=True,
)
class XapityAgentResponse:
    """
    Respuesta estructurada del orquestador global.
    """

    status: str
    answer: str
    intent: str
    confidence: float
    entities: dict[str, Any]
    data: Any
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
# VALIDACIONES
# ==================================================


def _validate_request(
    request: XapityAgentRequest,
) -> None:
    """
    Valida la solicitud recibida por XapityAgent.
    """

    if not isinstance(
        request,
        XapityAgentRequest,
    ):
        raise TypeError(
            "request debe ser una instancia de "
            "XapityAgentRequest."
        )

    if not isinstance(
        request.question,
        str,
    ):
        raise TypeError(
            "question debe ser un string."
        )

    if not request.question.strip():
        raise ValueError(
            "question no puede estar vacío."
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
        request.year is not None
        and (
            isinstance(
                request.year,
                bool,
            )
            or not isinstance(
                request.year,
                int,
            )
        )
    ):
        raise TypeError(
            "year debe ser un entero o None."
        )

    if (
        request.year is not None
        and not 2000 <= request.year <= 2100
    ):
        raise ValueError(
            "year debe estar entre 2000 y 2100."
        )

    if (
        request.month is not None
        and (
            isinstance(
                request.month,
                bool,
            )
            or not isinstance(
                request.month,
                int,
            )
        )
    ):
        raise TypeError(
            "month debe ser un entero o None."
        )

    if (
        request.month is not None
        and not 1 <= request.month <= 12
    ):
        raise ValueError(
            "month debe estar entre 1 y 12."
        )

    if (
        request.query_from is not None
        and not isinstance(
            request.query_from,
            str,
        )
    ):
        raise TypeError(
            "query_from debe ser string o None."
        )

    if (
        request.query_to is not None
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
# HELPERS
# ==================================================

def _normalize_confirmation_text(
    value: str,
) -> str:
    """
    Normaliza respuestas breves de confirmación
    sin realizar interpretación semántica amplia.
    """

    normalized = unicodedata.normalize(
        "NFD",
        value.strip().lower(),
    )

    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(
            character
        ) != "Mn"
    )

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return normalized


def _resolve_confirmation_decision(
    question: str,
) -> str | None:
    """
    Reconoce solamente confirmaciones o cancelaciones
    explícitas y breves.

    Retorna:
        "confirm"
        "cancel"
        None
    """

    normalized = (
        _normalize_confirmation_text(
            question
        )
    )

    affirmative_phrases = {
        "si",
        "confirmo",
        "si confirmo",
        "confirmar",
        "confirmado",
        "dale",
        "ok",
        "okay",
    }

    negative_phrases = {
        "no",
        "cancela",
        "cancelar",
        "no confirmo",
        "no cancela",
        "no gracias",
    }

    if normalized in affirmative_phrases:
        return "confirm"

    if normalized in negative_phrases:
        return "cancel"

    return None

def _build_trace(
    *,
    agent: str,
    child_trace: dict[str, Any] | None,
    elapsed_ms: float,
    attempted_agents: list[str],
) -> dict[str, Any]:
    """
    Construye el trace global del orquestador.
    """

    trace: dict[str, Any] = {
        "agent": agent,
        "attemptedAgents": list(
            attempted_agents
        ),
        "elapsedMs": elapsed_ms,
    }

    if child_trace:
        trace.update(
            child_trace
        )

        trace["agent"] = agent

        trace["attemptedAgents"] = list(
            attempted_agents
        )

        trace["elapsedMs"] = (
            elapsed_ms
        )

    return trace


def _from_agent_result(
    *,
    result: dict[str, Any],
    agent: str,
    elapsed_ms: float,
    attempted_agents: list[str],
) -> XapityAgentResponse:
    """
    Adapta la respuesta de un agente especializado
    al contrato global de XapityAgent.
    """

    child_trace = result.get(
        "trace"
    )

    if not isinstance(
        child_trace,
        dict,
    ):
        child_trace = {}

    entities = result.get(
        "entities"
    )

    if not isinstance(
        entities,
        dict,
    ):
        entities = {}

    error = result.get(
        "error"
    )

    if (
        error is not None
        and not isinstance(
            error,
            dict,
        )
    ):
        error = {
            "message": str(
                error
            ),
        }

    return XapityAgentResponse(
        status=str(
            result.get(
                "status",
                "answered",
            )
        ),
        answer=str(
            result.get(
                "answer",
                "",
            )
        ),
        intent=str(
            result.get(
                "intent",
                "unknown",
            )
        ),
        confidence=float(
            result.get(
                "confidence",
                0.0,
            )
        ),
        entities=dict(
            entities
        ),
        data=result.get(
            "data"
        ),
        trace=_build_trace(
            agent=agent,
            child_trace=child_trace,
            elapsed_ms=elapsed_ms,
            attempted_agents=(
                attempted_agents
            ),
        ),
        error=error,
    )


def _agent_has_handled_result(
    result: dict[str, Any],
) -> bool:
    """
    Determina si un agente especializado reconoció
    y procesó la consulta, aunque su status no sea
    necesariamente "answered".

    UNKNOWN / not_handled permiten continuar
    con el siguiente agente.
    """

    status = result.get(
        "status"
    )

    intent = str(
        result.get(
            "intent",
            "unknown",
        )
    )

    if status == "answered":
        return True

    if status in {
        None,
        "not_handled",
        "unknown_intent",
    }:
        return False

    return intent != "unknown"

def _pending_action_confirmation_response(
    *,
    pending_action: dict[str, Any],
    elapsed_ms: float,
) -> XapityAgentResponse:
    """
    Respuesta global para una acción que fue
    confirmada explícitamente por el usuario.

    En esta etapa la acción queda confirmada,
    pero todavía no se ejecuta.
    """

    action_id = (
        pending_action.get(
            "actionId"
        )
    )

    action_type = (
        pending_action.get(
            "actionType"
        )
    )

    confirmed_at = (
        pending_action.get(
            "confirmedAt"
        )
    )

    payload = (
        pending_action.get(
            "payload"
        )
        or {}
    )

    snapshot = (
        payload.get(
            "snapshot"
        )
        or {}
    )

    return XapityAgentResponse(
        status="confirmed",
        answer=(
            "Perfecto. El envío del Balance General "
            "quedó confirmado."
        ),
        intent="pending_action_confirmation",
        confidence=1.0,
        entities={
            "actionType": (
                action_type
            ),
        },
        data={
            "pendingAction": {
                "actionId": (
                    action_id
                ),
                "actionType": (
                    action_type
                ),
                "status": (
                    pending_action.get(
                        "status"
                    )
                ),
                "confirmedAt": (
                    confirmed_at
                ),
            },
            "deliveryChannel": (
                payload.get(
                    "deliveryChannel"
                )
            ),
            "format": (
                payload.get(
                    "format"
                )
            ),
            "recipientEmail": (
                payload.get(
                    "recipientEmail"
                )
            ),
            "snapshot": (
                snapshot
            ),
        },
        trace={
            "agent": "xapity",
            "attemptedAgents": [
                "pending_action",
            ],
            "matchedRule": (
                "pending_action_confirm"
            ),
            "operation": "confirm",
            "executionType": (
                action_type
            ),
            "pendingActionId": (
                action_id
            ),
            "requiresConfirmation": False,
            "executed": False,
            "responseBuilder": (
                "_pending_action_confirmation_response"
            ),
            "deterministic": True,
            "handled": True,
            "elapsedMs": (
                elapsed_ms
            ),
        },
    )

def _pending_action_cancellation_response(
    *,
    pending_action: dict[str, Any],
    elapsed_ms: float,
) -> XapityAgentResponse:
    """
    Respuesta global para una acción cancelada
    explícitamente por el usuario.
    """

    action_id = (
        pending_action.get(
            "actionId"
        )
    )

    action_type = (
        pending_action.get(
            "actionType"
        )
    )

    return XapityAgentResponse(
        status="cancelled",
        answer=(
            "Entendido. El envío pendiente fue cancelado."
        ),
        intent="pending_action_cancellation",
        confidence=1.0,
        entities={
            "actionType": (
                action_type
            ),
        },
        data={
            "pendingAction": {
                "actionId": (
                    action_id
                ),
                "actionType": (
                    action_type
                ),
                "status": (
                    pending_action.get(
                        "status"
                    )
                ),
                "cancelledAt": (
                    pending_action.get(
                        "cancelledAt"
                    )
                ),
            },
        },
        trace={
            "agent": "xapity",
            "attemptedAgents": [
                "pending_action",
            ],
            "matchedRule": (
                "pending_action_cancel"
            ),
            "operation": "cancel",
            "executionType": (
                action_type
            ),
            "pendingActionId": (
                action_id
            ),
            "requiresConfirmation": False,
            "executed": False,
            "responseBuilder": (
                "_pending_action_cancellation_response"
            ),
            "deterministic": True,
            "handled": True,
            "elapsedMs": (
                elapsed_ms
            ),
        },
    )


# ==================================================
# FALLBACK GLOBAL
# ==================================================


def _global_fallback_response(
    *,
    elapsed_ms: float,
    attempted_agents: list[str],
) -> XapityAgentResponse:
    """
    Respuesta utilizada cuando ningún agente
    especializado reconoce la consulta.
    """

    return XapityAgentResponse(
        status="not_handled",
        answer=(
            "No pude relacionar tu consulta con una capacidad "
            "disponible actualmente. Por ahora puedo ayudarte "
            "con información comercial, ventas, cuentas por cobrar "
            "y reportes contables disponibles en Xapity."
        ),
        intent="unknown",
        confidence=0.0,
        entities={},
        data=None,
        trace={
            "agent": "xapity",
            "attemptedAgents": list(
                attempted_agents
            ),
            "matchedRule": None,
            "responseBuilder": (
                "_global_fallback_response"
            ),
            "deterministic": True,
            "handled": False,
            "elapsedMs": elapsed_ms,
        },
    )


def _error_response(
    *,
    error: Exception,
    elapsed_ms: float,
    attempted_agents: list[str],
) -> XapityAgentResponse:
    """
    Convierte un error interno del orquestador
    en una respuesta estructurada.
    """

    return XapityAgentResponse(
        status="error",
        answer=(
            "No fue posible procesar correctamente "
            "la consulta en Xapity."
        ),
        intent="unknown",
        confidence=0.0,
        entities={},
        data=None,
        trace={
            "agent": "xapity",
            "attemptedAgents": list(
                attempted_agents
            ),
            "matchedRule": None,
            "responseBuilder": None,
            "deterministic": True,
            "handled": False,
            "elapsedMs": elapsed_ms,
        },
        error={
            "type": (
                error.__class__.__name__
            ),
            "message": str(
                error
            ),
        },
    )


# ==================================================
# AGENTE GLOBAL
# ==================================================


class XapityAgent:
    """
    Orquestador global de Xapity.

    Orden actual de resolución:

    1. ConversationAgent
    2. SalesAgent
    3. ReportsAgent
    4. Fallback global

    Mientras el número de agentes sea pequeño,
    el enrutamiento secuencial mantiene la
    arquitectura simple, explícita y trazable.

    Si en el futuro crece significativamente el
    número de dominios, podrá incorporarse un
    router global sin modificar la lógica interna
    de los agentes especializados.
    """

    def ask(
        self,
        *,
        question: str,
        business_id: int,
        year: int | None = None,
        month: int | None = None,
        query_from: str | None = None,
        query_to: str | None = None,
        limit: int = 10,
        raise_errors: bool = False,
    ) -> XapityAgentResponse:
        """
        Procesa una consulta general y la delega
        al agente adecuado.
        """

        started_at = (
            time.perf_counter()
        )

        attempted_agents: list[
            str
        ] = []

        request = XapityAgentRequest(
            question=question,
            business_id=business_id,
            year=year,
            month=month,
            query_from=query_from,
            query_to=query_to,
            limit=limit,
        )

        try:
            _validate_request(
                request
            )
            
            # ==============================================
            # 0. PENDING ACTION CONFIRMATION
            # ==============================================

            confirmation_decision = (
                _resolve_confirmation_decision(
                    request.question
                )
            )

            if confirmation_decision is not None:
                current_user = (
                    get_luca_current_user()
                )

                pending_action = (
                    find_pending_action(
                        business_id=(
                            request.business_id
                        ),
                        user_id=(
                            current_user.user_id
                        ),
                    )
                )

                if pending_action is not None:
                    attempted_agents.append(
                        "pending_action"
                    )

                    action_id = (
                        pending_action.get(
                            "actionId"
                        )
                    )

                    if (
                        confirmation_decision
                        == "confirm"
                    ):
                        resolved_action = (
                            confirm_pending_action(
                                business_id=(
                                    request.business_id
                                ),
                                user_id=(
                                    current_user.user_id
                                ),
                                action_id=(
                                    action_id
                                ),
                            )
                        )

                        if resolved_action is None:
                            raise RuntimeError(
                                "La acción pendiente ya no está "
                                "disponible para confirmación."
                            )

                        elapsed_ms = (
                            time.perf_counter()
                            - started_at
                        ) * 1000

                        return (
                            _pending_action_confirmation_response(
                                pending_action=(
                                    resolved_action
                                ),
                                elapsed_ms=round(
                                    elapsed_ms,
                                    3,
                                ),
                            )
                        )

                    resolved_action = (
                        cancel_pending_action(
                            business_id=(
                                request.business_id
                            ),
                            user_id=(
                                current_user.user_id
                            ),
                            action_id=(
                                action_id
                            ),
                        )
                    )

                    if resolved_action is None:
                        raise RuntimeError(
                            "La acción pendiente ya no está "
                            "disponible para cancelación."
                        )

                    elapsed_ms = (
                        time.perf_counter()
                        - started_at
                    ) * 1000

                    return (
                        _pending_action_cancellation_response(
                            pending_action=(
                                resolved_action
                            ),
                            elapsed_ms=round(
                                elapsed_ms,
                                3,
                            ),
                        )
                    )

            # ==============================================
            # 1. CONVERSATION AGENT
            # ==============================================

            attempted_agents.append(
                "conversation"
            )

            conversation_result = (
                ask_conversation_agent(
                    question=request.question,
                    raise_errors=True,
                )
            )

            if _agent_has_handled_result(
                conversation_result
            ):
                elapsed_ms = (
                    time.perf_counter()
                    - started_at
                ) * 1000

                return _from_agent_result(
                    result=conversation_result,
                    agent="conversation",
                    elapsed_ms=round(
                        elapsed_ms,
                        3,
                    ),
                    attempted_agents=(
                        attempted_agents
                    ),
                )

            # ==============================================
            # 2. SALES AGENT
            # ==============================================

            attempted_agents.append(
                "sales"
            )

            sales_result = (
                ask_sales_agent(
                    question=(
                        request.question
                    ),
                    business_id=(
                        request.business_id
                    ),
                    year=request.year,
                    month=request.month,
                    limit=request.limit,
                    raise_errors=True,
                )
            )

            if _agent_has_handled_result(
                sales_result
            ):
                elapsed_ms = (
                    time.perf_counter()
                    - started_at
                ) * 1000

                return _from_agent_result(
                    result=sales_result,
                    agent="sales",
                    elapsed_ms=round(
                        elapsed_ms,
                        3,
                    ),
                    attempted_agents=(
                        attempted_agents
                    ),
                )

            # ==============================================
            # 3. REPORTS AGENT
            # ==============================================

            attempted_agents.append(
                "reports"
            )

            reports_result = (
                ask_reports_agent(
                    question=(
                        request.question
                    ),
                    business_id=(
                        request.business_id
                    ),
                    query_from=(
                        request.query_from
                    ),
                    query_to=(
                        request.query_to
                    ),
                    limit=request.limit,
                    raise_errors=True,
                )
            )

            if _agent_has_handled_result(
                reports_result
            ):
                elapsed_ms = (
                    time.perf_counter()
                    - started_at
                ) * 1000

                return _from_agent_result(
                    result=reports_result,
                    agent="reports",
                    elapsed_ms=round(
                        elapsed_ms,
                        3,
                    ),
                    attempted_agents=(
                        attempted_agents
                    ),
                )

            # ==============================================
            # 4. FALLBACK GLOBAL
            # ==============================================

            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000

            return (
                _global_fallback_response(
                    elapsed_ms=round(
                        elapsed_ms,
                        3,
                    ),
                    attempted_agents=(
                        attempted_agents
                    ),
                )
            )

        except Exception as error:
            if raise_errors:
                raise

            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000

            return _error_response(
                error=error,
                elapsed_ms=round(
                    elapsed_ms,
                    3,
                ),
                attempted_agents=(
                    attempted_agents
                ),
            )


# ==================================================
# FUNCIÓN PÚBLICA
# ==================================================


_default_agent = XapityAgent()


def ask_xapity(
    *,
    question: str,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    query_from: str | None = None,
    query_to: str | None = None,
    limit: int = 10,
    raise_errors: bool = False,
) -> dict[str, Any]:
    """
    Interfaz pública simplificada
    del orquestador Xapity.
    """

    response = _default_agent.ask(
        question=question,
        business_id=business_id,
        year=year,
        month=month,
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
    """
    Construye el parser para pruebas manuales.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Orquestador global de agentes de Xapity."
        ),
        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),
        epilog="""
Ejemplos:

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "Hola"

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "¿Qué puedes hacer?"

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "¿Cuánto tengo por cobrar?"

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "Muéstrame el balance general"

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "Entrégame el balance general al día de hoy"

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "Muéstrame el balance general" \\
      --query-from 2026-01-01 \\
      --query-to 2026-09-04

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "Cuéntame un chiste"

  python3 -m luca.xapity_agent \\
      --business-id 70 \\
      --question "Hola" \\
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
            "Consulta del usuario."
        ),
    )

    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help=(
            "Año opcional para consultas comerciales."
        ),
    )

    parser.add_argument(
        "--month",
        type=int,
        default=None,
        help=(
            "Mes opcional para consultas comerciales."
        ),
    )

    parser.add_argument(
        "--query-from",
        type=str,
        default=None,
        help=(
            "Fecha inicial opcional para reportes "
            "en formato YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--query-to",
        type=str,
        default=None,
        help=(
            "Fecha final opcional para reportes "
            "en formato YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=(
            "Límite utilizado por agentes "
            "especializados. Por defecto: 10"
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
    response: XapityAgentResponse,
) -> None:
    """
    Presenta la respuesta global de Xapity.
    """

    print()
    print("=" * 88)
    print(
        "XAPITY — ORQUESTADOR GLOBAL"
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

    if response.answer:
        print(
            response.answer
        )
    else:
        print(
            "(sin respuesta)"
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
    """
    Punto de entrada para pruebas manuales.
    """

    parser = build_parser()

    args = parser.parse_args()

    agent = XapityAgent()

    response = agent.ask(
        question=args.question,
        business_id=args.business_id,
        year=args.year,
        month=args.month,
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