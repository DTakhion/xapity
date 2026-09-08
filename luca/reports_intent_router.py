# luca/reports_intent_router.py

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from luca.reports_intents import (
    ReportsIntent,
    ReportsIntentResult,
    ReportsOperation,
)


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def normalize_question(question: str) -> str:
    """
    Normaliza una consulta para clasificación determinista.

    - elimina espacios sobrantes
    - convierte a minúsculas
    - elimina tildes
    - normaliza signos de puntuación
    """
    if not isinstance(question, str):
        raise TypeError(
            "question debe ser str."
        )

    normalized = question.strip().lower()

    normalized = unicodedata.normalize(
        "NFD",
        normalized,
    )

    normalized = "".join(
        char
        for char in normalized
        if unicodedata.category(char)
        != "Mn"
    )

    normalized = re.sub(
        r"[¿?¡!.,;:()\[\]{}\"']+",
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
# Reglas
# ---------------------------------------------------------------------------

@dataclass(
    frozen=True,
    slots=True,
)
class IntentRule:
    """
    Regla determinista para clasificación de reportes.
    """

    name: str
    intent: ReportsIntent
    patterns: tuple[str, ...]

    operation: ReportsOperation = (
        ReportsOperation.QUERY
    )

    confidence: float = 1.0

    entity_builder: (
        Callable[[str], dict[str, object]]
        | None
    ) = None
    entity_builder: (
        Callable[[str], dict[str, object]]
        | None
    ) = None

    def matches(
        self,
        normalized_question: str,
    ) -> bool:
        """
        Retorna True si alguno de los patrones
        coincide con la consulta normalizada.
        """
        return any(
            re.search(
                pattern,
                normalized_question,
            )
            is not None
            for pattern in self.patterns
        )

    def build_entities(
        self,
        normalized_question: str,
    ) -> dict[str, object]:
        """
        Construye entidades asociadas a la regla.
        """
        if self.entity_builder is None:
            return {}

        return self.entity_builder(
            normalized_question
        )


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------

def _build_general_balance_entities(
    normalized_question: str,
) -> dict[str, object]:
    """
    Extrae modificadores simples asociados al Balance General.

    Por ahora no intenta resolver fechas concretas.
    Esa responsabilidad quedará en la capa de servicio.

    Ejemplo:
        "balance general al dia de hoy"

    produce:
        {
            "dateScope": "today"
        }
    """
    entities: dict[str, object] = {}

    today_patterns = (
        r"\bal dia de hoy\b",
        r"\ba la fecha\b",
        r"\bhasta hoy\b",
        r"\bhoy\b",
        r"\bactual\b",
        r"\bactualizado\b",
    )

    if any(
        re.search(
            pattern,
            normalized_question,
        )
        is not None
        for pattern in today_patterns
    ):
        entities["dateScope"] = "today"

    if re.search(
        r"\bresumen\b",
        normalized_question,
    ):
        entities["view"] = "summary"

    return entities

def _build_general_balance_email_entities(
    normalized_question: str,
) -> dict[str, object]:
    """
    Extrae entidades asociadas al envío del
    Balance General por correo.
    """
    entities = (
        _build_general_balance_entities(
            normalized_question
        )
    )

    entities["deliveryChannel"] = "email"

    if re.search(
        r"\bpdf\b",
        normalized_question,
    ):
        entities["format"] = "pdf"

    elif re.search(
        r"\bcsv\b",
        normalized_question,
    ):
        entities["format"] = "csv"

    elif re.search(
        r"\bexcel\b|\bxlsx\b",
        normalized_question,
    ):
        entities["format"] = "xlsx"

    else:
        entities["format"] = "xlsx"

    return entities


# ---------------------------------------------------------------------------
# Reglas disponibles
# ---------------------------------------------------------------------------

INTENT_RULES: tuple[IntentRule, ...] = (
    IntentRule(
        name="general_balance_email_execute",
        intent=ReportsIntent.GENERAL_BALANCE,
        operation=ReportsOperation.EXECUTE,
        confidence=1.0,
        patterns=(
            (
                r"\b(?:envia|enviame|mandame|manda|"
                r"enviar|mandar)\b.*"
                r"\bbalance general\b.*"
                r"\b(?:correo|email|mail)\b"
            ),
            (
                r"\bbalance general\b.*"
                r"\b(?:por correo|por email|por mail)\b"
            ),
        ),
        entity_builder=(
            _build_general_balance_email_entities
        ),
    ),

    IntentRule(
        name="general_balance",
        intent=ReportsIntent.GENERAL_BALANCE,
        operation=ReportsOperation.QUERY,
        confidence=1.0,
        patterns=(
            r"\bbalance general\b",
            r"\bbalance de la empresa\b",
            r"\bbalance contable\b",
        ),
        entity_builder=(
            _build_general_balance_entities
        ),
    ),
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def route_reports_intent(
    question: str,
) -> ReportsIntentResult:
    """
    Clasifica determinísticamente una consulta
    dentro del dominio de reportes.

    Si ninguna regla coincide, retorna UNKNOWN.
    """
    if not isinstance(question, str):
        raise TypeError(
            "question debe ser str."
        )

    original_question = question
    normalized_question = (
        normalize_question(question)
    )

    if not normalized_question:
        return ReportsIntentResult.unknown(
            original_question=(
                original_question
            ),
            normalized_question=(
                normalized_question
            ),
        )

    for rule in INTENT_RULES:
        if not rule.matches(
            normalized_question
        ):
            continue

        entities = rule.build_entities(
            normalized_question
        )

        return ReportsIntentResult(
            intent=rule.intent,
            operation=rule.operation,
            confidence=rule.confidence,
            entities=entities,
            matched_rule=rule.name,
            normalized_question=(
                normalized_question
            ),
            original_question=(
                original_question
            ),
        )

    return ReportsIntentResult.unknown(
        original_question=(
            original_question
        ),
        normalized_question=(
            normalized_question
        ),
    )