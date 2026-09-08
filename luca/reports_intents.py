# # luca/reports_intents.py

# from __future__ import annotations

# from dataclasses import dataclass, field
# from enum import Enum
# from typing import Any


# class ReportsIntent(str, Enum):
#     """
#     Intenciones disponibles para el dominio de reportes.
#     """

#     GENERAL_BALANCE = "general_balance"

#     UNKNOWN = "unknown"


# @dataclass(
#     frozen=True,
#     slots=True,
# )
# class ReportsIntentResult:
#     """
#     Resultado del proceso de clasificación de una consulta
#     perteneciente al dominio de reportes.
#     """

#     intent: ReportsIntent
#     confidence: float

#     entities: dict[str, Any] = field(
#         default_factory=dict
#     )

#     matched_rule: str | None = None
#     normalized_question: str = ""
#     original_question: str = ""

#     def __post_init__(self) -> None:
#         if not isinstance(
#             self.intent,
#             ReportsIntent,
#         ):
#             raise TypeError(
#                 "intent debe ser una instancia de ReportsIntent."
#             )

#         if isinstance(
#             self.confidence,
#             bool,
#         ) or not isinstance(
#             self.confidence,
#             (int, float),
#         ):
#             raise TypeError(
#                 "confidence debe ser numérico."
#             )

#         if not (
#             0.0
#             <= float(self.confidence)
#             <= 1.0
#         ):
#             raise ValueError(
#                 "confidence debe estar entre 0.0 y 1.0."
#             )

#         if not isinstance(
#             self.entities,
#             dict,
#         ):
#             raise TypeError(
#                 "entities debe ser un diccionario."
#             )

#         if (
#             self.matched_rule
#             is not None
#             and not isinstance(
#                 self.matched_rule,
#                 str,
#             )
#         ):
#             raise TypeError(
#                 "matched_rule debe ser str o None."
#             )

#         if not isinstance(
#             self.normalized_question,
#             str,
#         ):
#             raise TypeError(
#                 "normalized_question debe ser str."
#             )

#         if not isinstance(
#             self.original_question,
#             str,
#         ):
#             raise TypeError(
#                 "original_question debe ser str."
#             )

#     @property
#     def is_unknown(self) -> bool:
#         """
#         Indica si no fue posible clasificar la consulta.
#         """
#         return (
#             self.intent
#             == ReportsIntent.UNKNOWN
#         )

#     @property
#     def has_entities(self) -> bool:
#         """
#         Indica si existen entidades extraídas.
#         """
#         return bool(
#             self.entities
#         )

#     def get_entity(
#         self,
#         key: str,
#         default: Any = None,
#     ) -> Any:
#         """
#         Obtiene una entidad específica.
#         """
#         return self.entities.get(
#             key,
#             default,
#         )

#     def to_dict(self) -> dict[str, Any]:
#         """
#         Serializa el resultado a diccionario.
#         """
#         return {
#             "intent": self.intent.value,
#             "confidence": float(
#                 self.confidence
#             ),
#             "entities": dict(
#                 self.entities
#             ),
#             "matchedRule": (
#                 self.matched_rule
#             ),
#             "normalizedQuestion": (
#                 self.normalized_question
#             ),
#             "originalQuestion": (
#                 self.original_question
#             ),
#         }

#     @classmethod
#     def unknown(
#         cls,
#         *,
#         original_question: str,
#         normalized_question: str = "",
#     ) -> "ReportsIntentResult":
#         """
#         Construye un resultado UNKNOWN estándar.
#         """
#         return cls(
#             intent=ReportsIntent.UNKNOWN,
#             confidence=0.0,
#             entities={},
#             matched_rule=None,
#             normalized_question=(
#                 normalized_question
#             ),
#             original_question=(
#                 original_question
#             ),
#         )

# luca/reports_intents.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReportsOperation(str, Enum):
    """
    Operaciones disponibles para el dominio de reportes.
    """

    QUERY = "query"
    EXECUTE = "execute"


class ReportsIntent(str, Enum):
    """
    Intenciones disponibles para el dominio de reportes.
    """

    GENERAL_BALANCE = "general_balance"

    UNKNOWN = "unknown"


@dataclass(
    frozen=True,
    slots=True,
)
class ReportsIntentResult:
    """
    Resultado del proceso de clasificación de una consulta
    perteneciente al dominio de reportes.
    """

    intent: ReportsIntent
    confidence: float

    operation: ReportsOperation = (
        ReportsOperation.QUERY
    )

    entities: dict[str, Any] = field(
        default_factory=dict
    )

    matched_rule: str | None = None
    normalized_question: str = ""
    original_question: str = ""

    def __post_init__(self) -> None:
        if not isinstance(
            self.intent,
            ReportsIntent,
        ):
            raise TypeError(
                "intent debe ser una instancia de ReportsIntent."
            )

        if not isinstance(
            self.operation,
            ReportsOperation,
        ):
            raise TypeError(
                "operation debe ser una instancia "
                "de ReportsOperation."
            )

        if isinstance(
            self.confidence,
            bool,
        ) or not isinstance(
            self.confidence,
            (int, float),
        ):
            raise TypeError(
                "confidence debe ser numérico."
            )

        if not (
            0.0
            <= float(self.confidence)
            <= 1.0
        ):
            raise ValueError(
                "confidence debe estar entre 0.0 y 1.0."
            )

        if not isinstance(
            self.entities,
            dict,
        ):
            raise TypeError(
                "entities debe ser un diccionario."
            )

        if (
            self.matched_rule
            is not None
            and not isinstance(
                self.matched_rule,
                str,
            )
        ):
            raise TypeError(
                "matched_rule debe ser str o None."
            )

        if not isinstance(
            self.normalized_question,
            str,
        ):
            raise TypeError(
                "normalized_question debe ser str."
            )

        if not isinstance(
            self.original_question,
            str,
        ):
            raise TypeError(
                "original_question debe ser str."
            )

    @property
    def is_unknown(self) -> bool:
        """
        Indica si no fue posible clasificar la consulta.
        """
        return (
            self.intent
            == ReportsIntent.UNKNOWN
        )

    @property
    def has_entities(self) -> bool:
        """
        Indica si existen entidades extraídas.
        """
        return bool(
            self.entities
        )

    def get_entity(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Obtiene una entidad específica.
        """
        return self.entities.get(
            key,
            default,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa el resultado a diccionario.
        """
        return {
            "intent": self.intent.value,
            "operation": (
                self.operation.value
            ),
            "confidence": float(
                self.confidence
            ),
            "entities": dict(
                self.entities
            ),
            "matchedRule": (
                self.matched_rule
            ),
            "normalizedQuestion": (
                self.normalized_question
            ),
            "originalQuestion": (
                self.original_question
            ),
        }

    @classmethod
    def unknown(
        cls,
        *,
        original_question: str,
        normalized_question: str = "",
    ) -> "ReportsIntentResult":
        """
        Construye un resultado UNKNOWN estándar.
        """
        return cls(
            intent=ReportsIntent.UNKNOWN,
            operation=ReportsOperation.QUERY,
            confidence=0.0,
            entities={},
            matched_rule=None,
            normalized_question=(
                normalized_question
            ),
            original_question=(
                original_question
            ),
        )