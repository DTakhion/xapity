# luca/conversation_intents.py
"""
Definiciones de intenciones conversacionales generales para Xapity.

Este módulo contiene únicamente estructuras de dominio conversacional:

- ConversationIntent:
    Catálogo de intenciones conversacionales que el agente puede reconocer.

- ConversationIntentResult:
    Resultado estructurado producido por el router conversacional.

Estas intenciones representan interacciones generales con Xapity y no
consultas específicas sobre un dominio de negocio.

No contiene reglas de clasificación, acceso a datos, lógica comercial
ni generación de respuestas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConversationIntent(str, Enum):
    """
    Intenciones conversacionales generales soportadas por Xapity.

    Estas intenciones permiten resolver interacciones introductorias,
    sociales y de descubrimiento de capacidades antes de delegar una
    solicitud a un dominio específico, como ventas.
    """

    # ------------------------------------------------------------------
    # Interacciones sociales
    # ------------------------------------------------------------------

    GREETING = "greeting"  # Hola, buenos días, buenas tardes
    THANKS = "thanks"  # Gracias, muchas gracias
    FAREWELL = "farewell"  # Adiós, hasta luego, nos vemos

    # ------------------------------------------------------------------
    # Identidad y capacidades del servicio
    # ------------------------------------------------------------------

    SERVICE_DESCRIPTION = "service_description"
    # ¿Qué eres?, ¿Qué haces como servicio?, ¿Para qué sirve Xapity?

    CAPABILITIES = "capabilities"
    # ¿Qué puedes hacer?, ¿Qué te puedo preguntar?, ¿En qué me puedes ayudar?

    # ------------------------------------------------------------------
    # Disponibilidad de dominios
    # ------------------------------------------------------------------

    DOMAIN_AVAILABILITY = "domain_availability"
    # ¿Puedo preguntarte sobre mis ventas?
    # ¿Puedes ayudarme con mis compras?
    # ¿Trabajas con remuneraciones?

    # ------------------------------------------------------------------
    # Intención no reconocida
    # ------------------------------------------------------------------

    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ConversationIntentResult:
    """
    Resultado de la clasificación realizada por el router conversacional.

    Attributes
    ----------
    intent:
        Intención conversacional detectada.

    confidence:
        Nivel de confianza entre 0.0 y 1.0.

    entities:
        Entidades extraídas desde el mensaje. Por ejemplo:

        {
            "domain": "sales"
        }

        o:

        {
            "domain": "purchases"
        }

    matched_rule:
        Nombre o identificador de la regla que produjo la clasificación.

    normalized_question:
        Mensaje normalizado utilizado durante el análisis.

    original_question:
        Mensaje original recibido desde el usuario.
    """

    intent: ConversationIntent
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    matched_rule: str | None = None
    normalized_question: str | None = None
    original_question: str | None = None

    def __post_init__(self) -> None:
        """
        Valida los datos básicos del resultado.

        ``frozen=True`` evita que el resultado sea modificado accidentalmente
        después de que el router lo haya construido.
        """

        if not isinstance(self.intent, ConversationIntent):
            raise TypeError(
                "intent debe ser una instancia de ConversationIntent."
            )

        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence,
            (int, float),
        ):
            raise TypeError(
                "confidence debe ser un número entre 0.0 y 1.0."
            )

        confidence = float(self.confidence)

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "confidence debe estar entre 0.0 y 1.0."
            )

        if not isinstance(self.entities, dict):
            raise TypeError(
                "entities debe ser un diccionario."
            )

        # Normaliza confidence a float incluso cuando se recibió un int.
        object.__setattr__(self, "confidence", confidence)

    @property
    def is_unknown(self) -> bool:
        """
        Indica si el router no logró reconocer la intención conversacional.
        """

        return self.intent is ConversationIntent.UNKNOWN

    @property
    def has_entities(self) -> bool:
        """
        Indica si el router extrajo alguna entidad.
        """

        return bool(self.entities)

    def get_entity(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """
        Obtiene una entidad extraída sin acceder directamente al diccionario.

        Parameters
        ----------
        name:
            Nombre de la entidad.

        default:
            Valor retornado cuando la entidad no existe.
        """

        return self.entities.get(name, default)

    def to_dict(self) -> dict[str, Any]:
        """
        Convierte el resultado a un diccionario serializable.
        """

        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "entities": dict(self.entities),
            "matchedRule": self.matched_rule,
            "normalizedQuestion": self.normalized_question,
            "originalQuestion": self.original_question,
            "isUnknown": self.is_unknown,
        }

    @classmethod
    def unknown(
        cls,
        *,
        original_question: str | None = None,
        normalized_question: str | None = None,
        matched_rule: str | None = None,
    ) -> "ConversationIntentResult":
        """
        Construye un resultado estándar para una intención conversacional
        desconocida.
        """

        return cls(
            intent=ConversationIntent.UNKNOWN,
            confidence=0.0,
            entities={},
            matched_rule=matched_rule,
            normalized_question=normalized_question,
            original_question=original_question,
        )