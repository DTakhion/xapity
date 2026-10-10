
# luca/sales_hybrid_router.py

from __future__ import annotations

import logging

from luca.sales_intent_router import route_sales_intent
from luca.sales_intents import IntentResult
from luca.sales_ollama_router import (
    route_sales_intent_with_ollama,
)


logger = logging.getLogger(__name__)


def route_hybrid_sales_intent(
    question: str,
) -> IntentResult:
    """
    Determinista primero; Ollama como respaldo.

    Un fallo de Ollama no impide utilizar
    las capacidades deterministas.
    """

    try:
        deterministic_result = route_sales_intent(
            question
        )

        if not deterministic_result.is_unknown:
            return deterministic_result

    except Exception:
        logger.exception(
            "Error en el router determinista."
        )

    try:
        return route_sales_intent_with_ollama(
            question
        )

    except Exception:
        logger.exception(
            "Error en el intérprete Ollama."
        )

        return IntentResult.unknown(
            original_question=question,
            matched_rule="hybrid_fallback",
        )
