# luca/conversation_agent.py
"""
Agente conversacional determinista de Xapity.

Flujo principal:

    mensaje del usuario
        ↓
    conversation_intent_router.py
        ↓
    conversation_response_builder.py
        ↓
    resultado estructurado

Este agente resuelve interacciones conversacionales generales e
introductorias que no requieren consultar información de negocio.

Capacidades actualmente soportadas:

- GREETING
- THANKS
- FAREWELL
- SERVICE_DESCRIPTION
- CAPABILITIES
- DOMAIN_AVAILABILITY

Cuando el router conversacional no reconoce el mensaje, el agente retorna
el estado ``not_handled``. Esto NO representa un error: indica que una capa
superior puede delegar el mensaje a otro agente de dominio, por ejemplo
SalesAgent.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any

from luca.conversation_intent_router import (
    route_conversation_intent,
)
from luca.conversation_intents import (
    ConversationIntentResult,
)
from luca.conversation_response_builder import (
    build_conversation_response_result,
)


# ==================================================
# MODELOS
# ==================================================


@dataclass(frozen=True, slots=True)
class ConversationAgentRequest:
    """
    Solicitud recibida por el agente conversacional.

    En esta primera versión solo necesita el mensaje del usuario porque
    las capacidades conversacionales generales no dependen de una empresa,
    período ni fuente de datos.
    """

    question: str


@dataclass(frozen=True, slots=True)
class ConversationAgentResponse:
    """
    Respuesta estructurada del agente conversacional.

    El contrato conserva una forma similar a SalesAgentResponse para
    facilitar posteriormente su integración desde FastAPI o desde un
    orquestador superior.
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
# VALIDACIONES
# ==================================================


def _validate_request(
    request: ConversationAgentRequest,
) -> None:
    """
    Valida la solicitud recibida por el agente.
    """

    if not isinstance(
        request,
        ConversationAgentRequest,
    ):
        raise TypeError(
            "request debe ser una instancia de "
            "ConversationAgentRequest."
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


# ==================================================
# RESPUESTAS DE CONTROL
# ==================================================


def _not_handled_response(
    *,
    intent_result: ConversationIntentResult,
    elapsed_ms: float,
) -> ConversationAgentResponse:
    """
    Construye la respuesta cuando el mensaje no corresponde a una
    intención conversacional conocida.

    ``not_handled`` no representa un error.

    Su objetivo es permitir que una capa superior continúe evaluando
    otros agentes o dominios, por ejemplo SalesAgent.
    """

    return ConversationAgentResponse(
        status="not_handled",
        answer="",
        intent=intent_result.intent.value,
        confidence=intent_result.confidence,
        entities=dict(
            intent_result.entities
        ),
        data=None,
        trace={
            "matchedRule": (
                intent_result.matched_rule
            ),
            "responseBuilder": None,
            "deterministic": True,
            "handled": False,
            "elapsedMs": elapsed_ms,
        },
    )


def _error_response(
    *,
    intent_result: ConversationIntentResult,
    error: Exception,
    elapsed_ms: float,
) -> ConversationAgentResponse:
    """
    Construye una respuesta estructurada cuando ocurre un error interno.
    """

    return ConversationAgentResponse(
        status="error",
        answer=(
            "No pude procesar correctamente "
            "la interacción conversacional."
        ),
        intent=intent_result.intent.value,
        confidence=intent_result.confidence,
        entities=dict(
            intent_result.entities
        ),
        data=None,
        trace={
            "matchedRule": (
                intent_result.matched_rule
            ),
            "responseBuilder": None,
            "deterministic": True,
            "handled": False,
            "elapsedMs": elapsed_ms,
        },
        error={
            "type": error.__class__.__name__,
            "message": str(error),
        },
    )


# ==================================================
# AGENTE
# ==================================================


class ConversationAgent:
    """
    Orquestador del agente conversacional determinista.

    Este agente:

    1. valida el mensaje;
    2. clasifica la intención conversacional;
    3. deja pasar mensajes no conversacionales;
    4. construye una respuesta natural para intenciones reconocidas;
    5. retorna un contrato estructurado.

    No consulta bases de datos ni ejecuta capacidades comerciales.
    """

    def ask(
        self,
        *,
        question: str,
        raise_errors: bool = False,
    ) -> ConversationAgentResponse:
        """
        Procesa una interacción conversacional.

        Parameters
        ----------
        question:
            Mensaje escrito por el usuario.

        raise_errors:
            Si es True, propaga excepciones. Es útil durante desarrollo.

            Si es False, convierte errores internos en una respuesta
            estructurada.
        """

        started_at = time.perf_counter()

        request = ConversationAgentRequest(
            question=question,
        )

        try:
            _validate_request(
                request
            )

            intent_result = (
                route_conversation_intent(
                    request.question
                )
            )

            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000

            # ----------------------------------------------
            # UNKNOWN
            # ----------------------------------------------
            #
            # En este agente UNKNOWN significa:
            #
            # "No es una interacción conversacional general
            # reconocida por esta capa".
            #
            # No debemos generar aquí una respuesta genérica,
            # porque otra capa puede reconocer correctamente
            # el mensaje como una consulta comercial.
            #
            # Ejemplo:
            #
            # "¿Cuánto vendí este mes?"
            #
            # ConversationAgent -> not_handled
            # SalesAgent        -> MONTHLY_SALES
            # ----------------------------------------------

            if intent_result.is_unknown:
                return _not_handled_response(
                    intent_result=intent_result,
                    elapsed_ms=round(
                        elapsed_ms,
                        3,
                    ),
                )

            # ----------------------------------------------
            # CONSTRUCCIÓN DE RESPUESTA
            # ----------------------------------------------

            response_build_result = (
                build_conversation_response_result(
                    intent=intent_result.intent,
                    entities=intent_result.entities,
                )
            )

            answer = (
                response_build_result.answer
            )

            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000

            return ConversationAgentResponse(
                status="answered",
                answer=answer,
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
                    "responseBuilder": (
                        response_build_result.builder
                    ),
                    "deterministic": (
                        response_build_result.deterministic
                    ),
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
                ConversationIntentResult.unknown(
                    original_question=question,
                    normalized_question=None,
                    matched_rule="agent_error",
                )
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


_default_agent = ConversationAgent()


def ask_conversation_agent(
    *,
    question: str,
    raise_errors: bool = False,
) -> dict[str, Any]:
    """
    Interfaz simplificada para FastAPI, orquestadores y otros servicios.
    """

    response = _default_agent.ask(
        question=question,
        raise_errors=raise_errors,
    )

    return response.to_dict()


# ==================================================
# TERMINAL
# ==================================================


def build_parser() -> argparse.ArgumentParser:
    """
    Construye el parser para pruebas manuales desde terminal.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Agente conversacional determinista de Xapity."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python3 -m luca.conversation_agent \\
      --question "Hola"

  python3 -m luca.conversation_agent \\
      --question "¿Qué puedes hacer?"

  python3 -m luca.conversation_agent \\
      --question "¿Puedo preguntarte sobre mis ventas?"

  python3 -m luca.conversation_agent \\
      --question "¿Puedo preguntarte sobre mis compras?"

  python3 -m luca.conversation_agent \\
      --question "Muchas gracias"

  python3 -m luca.conversation_agent \\
      --question "Adiós, muchas gracias"

  python3 -m luca.conversation_agent \\
      --question "¿Cuánto vendí este mes?"

  python3 -m luca.conversation_agent \\
      --question "Hola" \\
      --json
""",
    )

    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help=(
            "Mensaje conversacional del usuario."
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
            "Propaga errores en lugar de convertirlos "
            "en una respuesta estructurada."
        ),
    )

    return parser


def print_response(
    response: ConversationAgentResponse,
) -> None:
    """
    Presenta la respuesta como la recibiría el usuario.
    """

    print()
    print("=" * 88)
    print(
        "XAPITY — AGENTE CONVERSACIONAL"
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
            "(sin respuesta — continuar routing)"
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

    agent = ConversationAgent()

    response = agent.ask(
        question=args.question,
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