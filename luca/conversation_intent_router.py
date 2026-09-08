# luca/conversation_intent_router.py
"""
Router determinista de intenciones conversacionales generales para Xapity.

Responsabilidades de este módulo:

- Recibir un mensaje en lenguaje natural.
- Normalizar el texto.
- Detectar una intención conversacional conocida.
- Extraer entidades simples, como el dominio consultado.
- Retornar un ConversationIntentResult estructurado.

Este módulo NO:

- consulta bases de datos;
- ejecuta capacidades comerciales;
- genera respuestas finales;
- utiliza un LLM;
- reemplaza los routers específicos de dominio, como sales_intent_router.py.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Pattern

from luca.conversation_intents import (
    ConversationIntent,
    ConversationIntentResult,
)


# ---------------------------------------------------------------------------
# Tipos internos
# ---------------------------------------------------------------------------


EntityExtractor = Callable[[str, str], dict[str, object]]


@dataclass(frozen=True, slots=True)
class IntentRule:
    """
    Regla determinista para reconocer una intención conversacional.

    Attributes
    ----------
    name:
        Identificador único de la regla.

    intent:
        Intención conversacional retornada cuando la regla coincide.

    patterns:
        Expresiones regulares evaluadas sobre el mensaje normalizado.

    confidence:
        Confianza asignada a la coincidencia.

    require_all:
        Si es True, todos los patrones deben coincidir.
        Si es False, basta con que coincida uno.

    extractor:
        Función opcional para extraer entidades.
    """

    name: str
    intent: ConversationIntent
    patterns: tuple[Pattern[str], ...]
    confidence: float = 1.0
    require_all: bool = False
    extractor: EntityExtractor | None = None

    def matches(
        self,
        normalized_question: str,
    ) -> bool:
        """
        Indica si el mensaje coincide con la regla.
        """

        results = [
            bool(pattern.search(normalized_question))
            for pattern in self.patterns
        ]

        if self.require_all:
            return all(results)

        return any(results)


# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------


DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "sales": (
        "venta",
        "ventas",
        "factura",
        "facturas",
        "cliente",
        "clientes",
        "cuentas por cobrar",
        "cobranza",
    ),
    "purchases": (
        "compra",
        "compras",
        "proveedor",
        "proveedores",
        "cuentas por pagar",
    ),
    "payroll": (
        "remuneracion",
        "remuneraciones",
        "sueldo",
        "sueldos",
        "nomina",
        "nominas",
        "previred",
    ),
    "accounting": (
        "contabilidad",
        "contable",
        "asiento contable",
        "asientos contables",
    ),
    "banking": (
        "banco",
        "bancos",
        "movimiento bancario",
        "movimientos bancarios",
        "conciliacion bancaria",
    ),
}


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------


def normalize_question(
    question: str,
) -> str:
    """
    Normaliza un mensaje para facilitar las comparaciones.

    La normalización:

    - convierte a minúsculas;
    - elimina tildes;
    - reemplaza signos de puntuación por espacios;
    - reduce espacios consecutivos;
    - conserva números.
    """

    if not isinstance(question, str):
        raise TypeError("question debe ser un string.")

    normalized = unicodedata.normalize(
        "NFKD",
        question,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = normalized.lower().strip()

    normalized = re.sub(
        r"[^a-z0-9ñ\s]",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


# ---------------------------------------------------------------------------
# Extracción de entidades
# ---------------------------------------------------------------------------


def extract_domain(
    normalized_question: str,
) -> str | None:
    """
    Detecta un dominio mencionado explícitamente por el usuario.

    Ejemplos
    --------
    "¿Puedo preguntarte sobre mis ventas?"
        -> "sales"

    "¿Puedes ayudarme con mis compras?"
        -> "purchases"

    "¿Trabajas con remuneraciones?"
        -> "payroll"
    """

    for domain, aliases in DOMAIN_ALIASES.items():
        for alias in aliases:
            if re.search(
                rf"\b{re.escape(alias)}\b",
                normalized_question,
            ):
                return domain

    return None


def extract_domain_entities(
    original_question: str,
    normalized_question: str,
) -> dict[str, object]:
    """
    Extrae entidades relacionadas con disponibilidad de dominios.
    """

    entities: dict[str, object] = {}

    domain = extract_domain(
        normalized_question
    )

    if domain is not None:
        entities["domain"] = domain

    return entities


# ---------------------------------------------------------------------------
# Construcción de patrones
# ---------------------------------------------------------------------------


def compile_patterns(
    *patterns: str,
) -> tuple[Pattern[str], ...]:
    """
    Compila expresiones regulares ignorando mayúsculas y minúsculas.
    """

    return tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in patterns
    )


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------


RULES: tuple[IntentRule, ...] = (

    # ------------------------------------------------------------------
    # Disponibilidad de dominios
    #
    # Debe evaluarse antes de CAPABILITIES porque preguntas como:
    #
    # "¿Puedes ayudarme con mis compras?"
    #
    # preguntan por una capacidad específica, no por las capacidades
    # generales de Xapity.
    # ------------------------------------------------------------------

    IntentRule(
        name="domain_availability",
        intent=ConversationIntent.DOMAIN_AVAILABILITY,
        patterns=compile_patterns(
            r"\bpuedo\s+preguntarte\s+(?:algo\s+)?sobre\b",
            r"\bte\s+puedo\s+preguntar\s+(?:algo\s+)?sobre\b",
            r"\bpuedo\s+consultarte\s+(?:algo\s+)?sobre\b",
            r"\bpuedo\s+consultar(?:te)?\s+(?:algo\s+)?sobre\b",
            r"\bpuedes\s+ayudarme\s+con\b",
            r"\bme\s+puedes\s+ayudar\s+con\b",
            r"\bpuedes\s+ayudarme\s+sobre\b",
            r"\btrabajas\s+con\b",
            r"\bmanejas\b",
            r"\bpuedes\s+ver\b",
            r"\btienes\s+informacion\s+(?:de|sobre)\b",
            r"\btienes\s+acceso\s+(?:a|a\s+mis)\b",
            r"\bpuedes\s+responder\s+(?:preguntas\s+)?sobre\b",
            r"\bsabes\s+(?:algo\s+)?sobre\s+mis\b",
        ),
        confidence=1.0,
        extractor=extract_domain_entities,
    ),

    # ------------------------------------------------------------------
    # Descripción del servicio
    # ------------------------------------------------------------------

    IntentRule(
        name="service_description",
        intent=ConversationIntent.SERVICE_DESCRIPTION,
        patterns=compile_patterns(
            r"\bque\s+eres\b",
            r"\bquien\s+eres\b",
            r"\bque\s+es\s+xapity\b",
            r"\bpara\s+que\s+sirves\b",
            r"\bpara\s+que\s+sirve\s+xapity\b",
            r"\bque\s+haces\s+como\s+servicio\b",
            r"\bque\s+hace\s+xapity\b",
            r"\bcual\s+es\s+tu\s+funcion\b",
            r"\bcual\s+es\s+la\s+funcion\s+de\s+xapity\b",
            r"\bque\s+tipo\s+de\s+asistente\s+eres\b",
        ),
        confidence=1.0,
    ),

    # ------------------------------------------------------------------
    # Capacidades generales
    # ------------------------------------------------------------------

    IntentRule(
        name="capabilities",
        intent=ConversationIntent.CAPABILITIES,
        patterns=compile_patterns(
            r"\bque\s+puedes\s+hacer\b",
            r"\bque\s+sabes\s+hacer\b",
            r"\bque\s+te\s+puedo\s+preguntar\b",
            r"\bque\s+puedo\s+preguntarte\b",
            r"\ben\s+que\s+me\s+puedes\s+ayudar\b",
            r"\ben\s+que\s+puedes\s+ayudarme\b",
            r"\bcomo\s+me\s+puedes\s+ayudar\b",
            r"\bque\s+capacidades\s+tienes\b",
            r"\bcuales\s+son\s+tus\s+capacidades\b",
            r"\bque\s+cosas\s+puedes\s+hacer\b",
            r"\bque\s+informacion\s+puedo\s+consultar\b",
            r"\bque\s+informacion\s+puedes\s+consultar\b",
        ),
        confidence=1.0,
    ),

    # ------------------------------------------------------------------
    # Agradecimientos y despedidas combinadas
    #
    # Estas reglas van antes de THANKS y FAREWELL simples para mantener
    # una clasificación determinista cuando aparecen ambas ideas.
    #
    # Para esta primera versión priorizamos FAREWELL porque el objetivo
    # principal del turno es cerrar la conversación.
    # ------------------------------------------------------------------

    IntentRule(
        name="farewell_with_thanks",
        intent=ConversationIntent.FAREWELL,
        patterns=compile_patterns(
            r"\b(?:gracias|muchas\s+gracias)\b.*\b(?:adios|chao|chau|hasta\s+luego|nos\s+vemos|hasta\s+pronto)\b",
            r"\b(?:adios|chao|chau|hasta\s+luego|nos\s+vemos|hasta\s+pronto)\b.*\b(?:gracias|muchas\s+gracias)\b",
        ),
        confidence=1.0,
    ),

    # ------------------------------------------------------------------
    # Saludos
    # ------------------------------------------------------------------

    IntentRule(
        name="greeting",
        intent=ConversationIntent.GREETING,
        patterns=compile_patterns(
            r"^\s*hola\s*$",
            r"^\s*hol[aai]+\s*$",
            r"^\s*buenos\s+dias\s*$",
            r"^\s*buen\s+dia\s*$",
            r"^\s*buenas\s+tardes\s*$",
            r"^\s*buenas\s+noches\s*$",
            r"^\s*hey\s*$",
            r"^\s*hello\s*$",
            r"^\s*hola\s+(?:xapity|luca)\s*$",
            r"^\s*buenos\s+dias\s+(?:xapity|luca)\s*$",
            r"^\s*buenas\s+tardes\s+(?:xapity|luca)\s*$",
        ),
        confidence=1.0,
    ),

    # ------------------------------------------------------------------
    # Agradecimientos
    # ------------------------------------------------------------------

    IntentRule(
        name="thanks",
        intent=ConversationIntent.THANKS,
        patterns=compile_patterns(
            r"^\s*gracias\s*$",
            r"^\s*muchas\s+gracias\s*$",
            r"^\s*gracias\s+por\s+la\s+ayuda\s*$",
            r"^\s*gracias\s+por\s+tu\s+ayuda\s*$",
            r"^\s*te\s+lo\s+agradezco\s*$",
            r"^\s*perfecto\s+gracias\s*$",
            r"^\s*genial\s+gracias\s*$",
            r"^\s*excelente\s+gracias\s*$",
        ),
        confidence=1.0,
    ),

    # ------------------------------------------------------------------
    # Despedidas
    # ------------------------------------------------------------------

    IntentRule(
        name="farewell",
        intent=ConversationIntent.FAREWELL,
        patterns=compile_patterns(
            r"^\s*adios\s*$",
            r"^\s*chao\s*$",
            r"^\s*chau\s*$",
            r"^\s*hasta\s+luego\s*$",
            r"^\s*hasta\s+pronto\s*$",
            r"^\s*nos\s+vemos\s*$",
            r"^\s*hablamos\s+luego\s*$",
            r"^\s*eso\s+seria\s+todo\s*$",
            r"^\s*eso\s+es\s+todo\s*$",
        ),
        confidence=1.0,
    ),
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ConversationIntentRouter:
    """
    Router determinista para interacciones conversacionales generales.

    Las reglas se evalúan en orden. Por esta razón, las intenciones más
    específicas deben aparecer antes que las más generales.

    Si ninguna regla coincide, el resultado será UNKNOWN. Esto permite
    que una capa superior delegue posteriormente la pregunta a un router
    específico de dominio, como SalesIntentRouter.
    """

    def __init__(
        self,
        rules: tuple[IntentRule, ...] | None = None,
    ) -> None:
        self._rules = rules or RULES

    @property
    def rules(self) -> tuple[IntentRule, ...]:
        """
        Retorna las reglas configuradas.
        """

        return self._rules

    def route(
        self,
        question: str,
    ) -> ConversationIntentResult:
        """
        Clasifica un mensaje y retorna un resultado estructurado.
        """

        if not isinstance(question, str):
            raise TypeError("question debe ser un string.")

        original_question = question.strip()

        if not original_question:
            return ConversationIntentResult.unknown(
                original_question=question,
                normalized_question="",
                matched_rule="empty_question",
            )

        normalized_question = normalize_question(
            original_question
        )

        for rule in self._rules:
            if not rule.matches(normalized_question):
                continue

            entities: dict[str, object] = {}

            if rule.extractor is not None:
                entities = rule.extractor(
                    original_question,
                    normalized_question,
                )

            # Una consulta de disponibilidad de dominio solo es válida
            # cuando efectivamente se logró identificar el dominio.
            #
            # Esto evita clasificar frases genéricas como:
            #
            # "¿Puedes ayudarme con esto?"
            #
            # como DOMAIN_AVAILABILITY sin evidencia suficiente.
            if (
                rule.intent
                is ConversationIntent.DOMAIN_AVAILABILITY
                and "domain" not in entities
            ):
                continue

            return ConversationIntentResult(
                intent=rule.intent,
                confidence=rule.confidence,
                entities=entities,
                matched_rule=rule.name,
                normalized_question=normalized_question,
                original_question=original_question,
            )

        return ConversationIntentResult.unknown(
            original_question=original_question,
            normalized_question=normalized_question,
            matched_rule="no_matching_rule",
        )


# ---------------------------------------------------------------------------
# Instancia y función pública
# ---------------------------------------------------------------------------


_default_router = ConversationIntentRouter()


def route_conversation_intent(
    question: str,
) -> ConversationIntentResult:
    """
    Función pública simplificada para clasificar un mensaje.

    Ejemplo
    -------
    result = route_conversation_intent(
        "¿Puedo preguntarte sobre mis ventas?"
    )
    """

    return _default_router.route(question)


# ---------------------------------------------------------------------------
# Ejecución manual
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    example_questions = (
        "Hola",
        "Buenos días",
        "¿Qué eres?",
        "¿Qué haces como servicio?",
        "¿Qué puedes hacer?",
        "¿Qué te puedo preguntar?",
        "¿Puedo preguntarte sobre mis ventas?",
        "¿Puedo consultarte sobre mis compras?",
        "¿Trabajas con remuneraciones?",
        "Gracias",
        "Muchas gracias",
        "Adiós",
        "Adiós, muchas gracias",
        "¿Cuánto vendí este mes?",
    )

    for question in example_questions:
        result = route_conversation_intent(question)

        print("-" * 80)
        print(f"Pregunta   : {question}")
        print(f"Intent     : {result.intent.value}")
        print(f"Confianza  : {result.confidence}")
        print(f"Entidades  : {result.entities}")
        print(f"Regla      : {result.matched_rule}")