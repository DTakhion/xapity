# luca/conversation_response_builder.py
"""
Constructor determinista de respuestas conversacionales generales para Xapity.

Responsabilidades de este módulo:

- Recibir una ConversationIntent ya clasificada.
- Recibir las entidades extraídas por el router conversacional.
- Seleccionar un builder específico.
- Construir una respuesta natural y controlada.
- Retornar metadata sobre el builder utilizado.

Este módulo NO:

- clasifica intenciones;
- consulta bases de datos;
- ejecuta acciones comerciales;
- utiliza un LLM;
- modifica información de negocio.

Las capacidades declaradas aquí deben representar únicamente funciones
realmente disponibles en Xapity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from luca.conversation_intents import (
    ConversationIntent,
)


# ==================================================
# TIPOS
# ==================================================


ResponseBuilder = Callable[
    [dict[str, Any]],
    str,
]


@dataclass(frozen=True, slots=True)
class ConversationResponseBuildResult:
    """
    Resultado estructurado generado por el response builder.

    Attributes
    ----------
    answer:
        Respuesta final que puede mostrarse al usuario.

    intent:
        Intención conversacional utilizada para construir la respuesta.

    builder:
        Nombre del builder específico utilizado.

    deterministic:
        Indica que la respuesta fue construida mediante lógica
        determinista y no mediante un modelo generativo.
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
# CATÁLOGO DE DOMINIOS
# ==================================================


DOMAIN_CAPABILITIES: dict[str, dict[str, Any]] = {
    "sales": {
        "label": "ventas",
        "available": True,
    },
    "purchases": {
        "label": "compras",
        "available": False,
    },
    "payroll": {
        "label": "remuneraciones",
        "available": False,
    },
    "accounting": {
        "label": "contabilidad",
        "available": False,
    },
    "banking": {
        "label": "información bancaria",
        "available": False,
    },
}


# ==================================================
# BUILDERS SOCIALES
# ==================================================


def build_greeting_response(
    entities: dict[str, Any],
) -> str:
    """
    Construye una respuesta de saludo.
    """

    return (
        "¡Hola! Soy Xapity, tu agente comercial. "
        "¿En qué te puedo ayudar?"
    )


def build_thanks_response(
    entities: dict[str, Any],
) -> str:
    """
    Construye una respuesta a un agradecimiento.
    """

    return (
        "¡De nada! Estoy disponible para ayudarte "
        "con tus consultas comerciales."
    )


def build_farewell_response(
    entities: dict[str, Any],
) -> str:
    """
    Construye una respuesta de despedida.
    """

    return (
        "¡Hasta luego! Cuando necesites revisar "
        "información comercial, aquí estaré."
    )


# ==================================================
# BUILDERS DE IDENTIDAD Y CAPACIDADES
# ==================================================


def build_service_description_response(
    entities: dict[str, Any],
) -> str:
    """
    Explica qué es Xapity y cuál es su función general.
    """

    return (
        "Soy Xapity, un agente comercial conectado a la información "
        "de tu negocio. Puedo ayudarte a consultar, analizar y entender "
        "información relacionada con tus ventas y cuentas por cobrar, "
        "y también apoyar acciones comerciales cuando exista una "
        "capacidad habilitada para ello."
    )


def build_capabilities_response(
    entities: dict[str, Any],
) -> str:
    """
    Describe las capacidades actualmente disponibles.

    La respuesta debe reflejar únicamente capacidades realmente
    implementadas en Xapity.
    """

    return (
        "Actualmente puedo ayudarte con información de ventas y "
        "cuentas por cobrar. Por ejemplo, puedes preguntarme cuánto "
        "has vendido, revisar tus principales clientes, consultar "
        "facturas pendientes o vencidas, analizar tendencias y "
        "comparaciones de ventas, y revisar documentos comerciales. "
        "También puedo explicar algunos resultados, proponerte acciones "
        "comerciales y ejecutar acciones específicas cuando esa "
        "capacidad esté disponible."
    )


# ==================================================
# DISPONIBILIDAD DE DOMINIOS
# ==================================================


def build_domain_availability_response(
    entities: dict[str, Any],
) -> str:
    """
    Responde si Xapity puede trabajar actualmente con un dominio.

    La entidad esperada es:

        {
            "domain": "sales"
        }

    o equivalente.
    """

    domain = entities.get("domain")

    if not isinstance(domain, str):
        return (
            "Puedo indicarte si una determinada área está disponible, "
            "pero necesito que me indiques qué tipo de información "
            "quieres consultar."
        )

    capability = DOMAIN_CAPABILITIES.get(
        domain
    )

    if capability is None:
        return (
            "Ese tipo de información no forma parte de las capacidades "
            "que tengo disponibles actualmente."
        )

    label = capability["label"]
    available = capability["available"]

    if available:
        return (
            f"Sí. Actualmente puedo ayudarte con información de {label}. "
            "Puedes hacerme una consulta directamente y trataré de "
            "resolverla con la información disponible."
        )

    return (
        f"Por ahora no tengo integrada la información de {label}. "
        "Actualmente mi dominio comercial disponible es ventas y "
        "cuentas por cobrar."
    )


# ==================================================
# REGISTRO DE BUILDERS
# ==================================================


RESPONSE_BUILDERS: dict[
    ConversationIntent,
    ResponseBuilder,
] = {
    ConversationIntent.GREETING:
        build_greeting_response,

    ConversationIntent.THANKS:
        build_thanks_response,

    ConversationIntent.FAREWELL:
        build_farewell_response,

    ConversationIntent.SERVICE_DESCRIPTION:
        build_service_description_response,

    ConversationIntent.CAPABILITIES:
        build_capabilities_response,

    ConversationIntent.DOMAIN_AVAILABILITY:
        build_domain_availability_response,
}


# ==================================================
# RESOLUCIÓN
# ==================================================


def get_response_builder(
    intent: ConversationIntent,
) -> ResponseBuilder:
    """
    Obtiene el builder correspondiente a una intención.

    UNKNOWN no posee builder porque debe ser tratado por el agente
    como ``not_handled`` y continuar hacia otro dominio.
    """

    if not isinstance(
        intent,
        ConversationIntent,
    ):
        raise TypeError(
            "intent debe ser una instancia de ConversationIntent."
        )

    builder = RESPONSE_BUILDERS.get(
        intent
    )

    if builder is None:
        raise ValueError(
            "No existe un response builder registrado "
            f"para la intención '{intent.value}'."
        )

    return builder


# ==================================================
# FUNCIÓN PÚBLICA
# ==================================================


def build_conversation_response_result(
    *,
    intent: ConversationIntent,
    entities: dict[str, Any] | None = None,
) -> ConversationResponseBuildResult:
    """
    Construye la respuesta conversacional final.

    Parameters
    ----------
    intent:
        Intención conversacional ya clasificada.

    entities:
        Entidades extraídas por el router.

    Returns
    -------
    ConversationResponseBuildResult
        Respuesta final y metadata del builder utilizado.
    """

    if not isinstance(
        intent,
        ConversationIntent,
    ):
        raise TypeError(
            "intent debe ser una instancia de ConversationIntent."
        )

    if entities is None:
        entities = {}

    if not isinstance(
        entities,
        dict,
    ):
        raise TypeError(
            "entities debe ser un diccionario."
        )

    if intent is ConversationIntent.UNKNOWN:
        raise ValueError(
            "ConversationIntent.UNKNOWN no debe generar "
            "una respuesta conversacional. El agente debe "
            "retornar not_handled."
        )

    builder = get_response_builder(
        intent
    )

    answer = builder(
        dict(entities)
    )

    if not isinstance(
        answer,
        str,
    ):
        raise TypeError(
            "El response builder debe retornar un string."
        )

    answer = answer.strip()

    if not answer:
        raise ValueError(
            "El response builder generó una respuesta vacía."
        )

    return ConversationResponseBuildResult(
        answer=answer,
        intent=intent.value,
        builder=builder.__name__,
        deterministic=True,
    )


# ==================================================
# FUNCIÓN SIMPLIFICADA
# ==================================================


def build_conversation_response(
    *,
    intent: ConversationIntent,
    entities: dict[str, Any] | None = None,
) -> str:
    """
    Retorna únicamente el texto final de la respuesta.

    Útil cuando no se requiere metadata adicional.
    """

    result = build_conversation_response_result(
        intent=intent,
        entities=entities,
    )

    return result.answer


# ==================================================
# PRUEBAS MANUALES
# ==================================================


if __name__ == "__main__":
    examples: tuple[
        tuple[
            ConversationIntent,
            dict[str, Any],
        ],
        ...,
    ] = (
        (
            ConversationIntent.GREETING,
            {},
        ),
        (
            ConversationIntent.SERVICE_DESCRIPTION,
            {},
        ),
        (
            ConversationIntent.CAPABILITIES,
            {},
        ),
        (
            ConversationIntent.DOMAIN_AVAILABILITY,
            {
                "domain": "sales",
            },
        ),
        (
            ConversationIntent.DOMAIN_AVAILABILITY,
            {
                "domain": "purchases",
            },
        ),
        (
            ConversationIntent.DOMAIN_AVAILABILITY,
            {
                "domain": "payroll",
            },
        ),
        (
            ConversationIntent.THANKS,
            {},
        ),
        (
            ConversationIntent.FAREWELL,
            {},
        ),
    )

    for intent, entities in examples:
        result = (
            build_conversation_response_result(
                intent=intent,
                entities=entities,
            )
        )

        print("=" * 80)
        print(
            f"Intent  : {result.intent}"
        )
        print(
            f"Builder : {result.builder}"
        )
        print(
            f"Entities: {entities}"
        )
        print()
        print(result.answer)