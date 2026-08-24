# luca/sales_intent_router.py
"""
Router determinista de intenciones para el agente comercial de Luca.

Responsabilidades de este módulo:

- Recibir una pregunta en lenguaje natural.
- Normalizar el texto.
- Detectar una intención comercial conocida.
- Extraer entidades simples:
    - cliente
    - límite
    - año
    - mes
- Retornar un IntentResult estructurado.

Este módulo NO:

- consulta MongoDB;
- ejecuta funciones de sales_query_service.py;
- genera respuestas finales;
- utiliza un LLM.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Callable, Pattern

from luca.sales_intents import IntentResult, SalesIntent, SalesOperation


# ---------------------------------------------------------------------------
# Tipos internos
# ---------------------------------------------------------------------------


EntityExtractor = Callable[[str, str], dict[str, object]]


@dataclass(frozen=True, slots=True)
class IntentRule:
    """
    Regla determinista para reconocer una intención.

    Attributes
    ----------
    name:
        Identificador único de la regla.

    intent:
        Intención que retorna cuando la regla coincide.

    patterns:
        Expresiones regulares evaluadas sobre la pregunta normalizada.

    confidence:
        Confianza asignada a la coincidencia.

    require_all:
        Si es True, todos los patrones deben coincidir.
        Si es False, basta con que coincida uno.

    extractor:
        Función opcional para extraer entidades.
    """

    name: str
    intent: SalesIntent
    patterns: tuple[Pattern[str], ...]
    confidence: float = 1.0
    operation: SalesOperation = SalesOperation.QUERY
    require_all: bool = False
    extractor: EntityExtractor | None = None

    def matches(self, normalized_question: str) -> bool:
        """
        Indica si la pregunta coincide con la regla.
        """

        results = [
            bool(pattern.search(normalized_question))
            for pattern in self.patterns
        ]

        if self.require_all:
            return all(results)

        return any(results)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------


MONTHS: dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


CUSTOMER_PREFIXES: tuple[str, ...] = (
    "de ",
    "del cliente ",
    "para el cliente ",
    "para ",
    "cliente ",
    "ventas de ",
    "facturas de ",
    "documentos de ",
    "movimientos de ",
    "cuanto le he vendido a ",
    "cuanto vendi a ",
    "cuanto me debe ",
    "cuanto debe ",
    "deuda de ",
)


CUSTOMER_STOP_WORDS: tuple[str, ...] = (
    " en enero",
    " en febrero",
    " en marzo",
    " en abril",
    " en mayo",
    " en junio",
    " en julio",
    " en agosto",
    " en septiembre",
    " en setiembre",
    " en octubre",
    " en noviembre",
    " en diciembre",
    " este mes",
    " este ano",
    " durante ",
    " del ano ",
    " de 20",
    " por cobrar",
    " pendientes",
    " pagadas",
    " anuladas",
    " vencidas",
    " el mes pasado",
    " el mes anterior",
    " mes pasado",
    " mes anterior",
    " el ano pasado",
    " ano pasado",
    " ano anterior",
)


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------


def normalize_question(question: str) -> str:
    """
    Normaliza una pregunta para facilitar las comparaciones.

    La normalización:

    - convierte a minúsculas;
    - elimina tildes;
    - reemplaza signos de puntuación por espacios;
    - reduce espacios consecutivos;
    - conserva números.
    """

    if not isinstance(question, str):
        raise TypeError("question debe ser un string.")

    normalized = unicodedata.normalize("NFKD", question)

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


def extract_limit(
    normalized_question: str,
    *,
    default: int | None = None,
    maximum: int = 100,
) -> int | None:
    """
    Extrae un límite numérico desde expresiones como:

    - top 10
    - principales 5 clientes
    - primeros 20 documentos
    - dame 3 facturas
    """

    patterns = (
        r"\btop\s+(\d{1,3})\b",
        r"\bprincipales\s+(\d{1,3})\b",
        r"\bprimeros?\s+(\d{1,3})\b",
        r"\bultimos?\s+(\d{1,3})\b",
        r"\bmuéstrame\s+(\d{1,3})\b",
        r"\bmuestrame\s+(\d{1,3})\b",
        r"\bdame\s+(\d{1,3})\b",
        r"\blos\s+(\d{1,3})\s+(?:clientes|documentos|facturas)\b",
    )

    for pattern in patterns:
        match = re.search(pattern, normalized_question)

        if not match:
            continue

        value = int(match.group(1))

        if value <= 0:
            return default

        return min(value, maximum)

    return default


def extract_year(normalized_question: str) -> int | None:
    """
    Extrae un año entre 2000 y 2099.
    """

    match = re.search(
        r"\b(20\d{2})\b",
        normalized_question,
    )

    if not match:
        return None

    return int(match.group(1))


def extract_month(normalized_question: str) -> int | None:
    """
    Extrae un mes expresado por nombre o número.
    """

    for month_name, month_number in MONTHS.items():
        if re.search(
            rf"\b{re.escape(month_name)}\b",
            normalized_question,
        ):
            return month_number

    numeric_patterns = (
        r"\bmes\s+(\d{1,2})\b",
        r"\bmonth\s+(\d{1,2})\b",
    )

    for pattern in numeric_patterns:
        match = re.search(pattern, normalized_question)

        if not match:
            continue

        month_number = int(match.group(1))

        if 1 <= month_number <= 12:
            return month_number

    return None


def extract_relative_period(
    normalized_question: str,
) -> dict[str, int]:
    """
    Extrae períodos relativos simples.

    Soporta:

    - este mes
    - mes actual
    - este año
    - año actual
    - mes pasado
    - mes anterior
    - último mes
    - año pasado
    - año anterior
    """

    now = datetime.now()

    entities: dict[str, int] = {}

    # --------------------------------------------------------
    # Mes actual
    # --------------------------------------------------------

    if any(
        expression in normalized_question
        for expression in (
            "este mes",
            "mes actual",
            "durante este mes",
        )
    ):
        entities["year"] = now.year
        entities["month"] = now.month

        return entities

    # --------------------------------------------------------
    # Mes anterior
    # --------------------------------------------------------

    if any(
        expression in normalized_question
        for expression in (
            "mes pasado",
            "mes anterior",
            "ultimo mes",
            "mes previo",
        )
    ):
        previous_month = (
            now
            - relativedelta(
                months=1
            )
        )

        entities["year"] = (
            previous_month.year
        )

        entities["month"] = (
            previous_month.month
        )

        return entities

    # --------------------------------------------------------
    # Año actual
    # --------------------------------------------------------

    if any(
        expression in normalized_question
        for expression in (
            "este ano",
            "ano actual",
            "durante este ano",
        )
    ):
        entities["year"] = now.year

        return entities

    # --------------------------------------------------------
    # Año anterior
    # --------------------------------------------------------

    if any(
        expression in normalized_question
        for expression in (
            "ano pasado",
            "ano anterior",
            "ultimo ano",
        )
    ):
        entities["year"] = (
            now.year - 1
        )

        return entities

    return entities


def extract_period_entities(
    normalized_question: str,
) -> dict[str, int]:
    """
    Extrae año y mes desde una pregunta.
    """

    entities = extract_relative_period(normalized_question)

    year = extract_year(normalized_question)
    month = extract_month(normalized_question)

    if year is not None:
        entities["year"] = year

    if month is not None:
        entities["month"] = month

    return entities


def clean_customer_candidate(candidate: str) -> str | None:
    """
    Limpia un posible nombre de cliente.
    """

    customer = candidate.strip()

    for stop_word in CUSTOMER_STOP_WORDS:
        stop_position = customer.find(stop_word)

        if stop_position >= 0:
            customer = customer[:stop_position].strip()

    customer = re.sub(
        r"\b(?:por favor|gracias|please)\b.*$",
        "",
        customer,
    ).strip()

    customer = re.sub(
        r"\s+",
        " ",
        customer,
    ).strip()

    invalid_values = {
        "",
        "mis clientes",
        "clientes",
        "cliente",
        "todos",
        "todas",
        "cada cliente",
        "los clientes",
        "un cliente",
        "una empresa",
    }

    if customer in invalid_values:
        return None

    if len(customer) < 2:
        return None

    return customer


def extract_customer(
    original_question: str,
    normalized_question: str,
) -> str | None:
    """
    Extrae el nombre de un cliente desde expresiones habituales.

    Ejemplos:

    - Muéstrame las facturas de Frogmi.
    - ¿Cuánto le he vendido a Osher?
    - ¿Cuánto me debe Empresa ABC?
    - Ventas del cliente Acme.
    """

    patterns = (
        r"\bfacturas?\s+(?:del cliente\s+|de\s+)(.+)$",
        r"\bdocumentos?\s+(?:del cliente\s+|de\s+)(.+)$",
        r"\bventas?\s+(?:del cliente\s+|de\s+|a\s+)(.+)$",
        r"\bcuanto\s+le\s+he\s+vendido\s+a\s+(.+)$",
        r"\bcuanto\s+vendi\s+a\s+(.+)$",
        r"\bcuanto\s+me\s+debe\s+(.+)$",
        r"\bcuanto\s+debe\s+(.+)$",
        r"\bdeuda\s+(?:del cliente\s+|de\s+)(.+)$",
        r"\bcliente\s+(.+)$",
    )

    for pattern in patterns:
        match = re.search(pattern, normalized_question)

        if not match:
            continue

        customer = clean_customer_candidate(match.group(1))

        if customer:
            return customer

    return None


def extract_common_entities(
    original_question: str,
    normalized_question: str,
) -> dict[str, object]:
    """
    Extrae entidades generales disponibles para cualquier intención.
    """

    entities: dict[str, object] = {}

    entities.update(
        extract_period_entities(normalized_question)
    )

    limit = extract_limit(normalized_question)

    if limit is not None:
        entities["limit"] = limit

    return entities


def extract_top_customers_entities(
    original_question: str,
    normalized_question: str,
) -> dict[str, object]:
    """
    Entidades para consultas de principales clientes.
    """

    entities = extract_common_entities(
        original_question,
        normalized_question,
    )

    entities.setdefault(
        "limit",
        10,
    )

    return entities


def extract_customer_detail_entities(
    original_question: str,
    normalized_question: str,
) -> dict[str, object]:
    """
    Entidades para consultas relacionadas con un cliente específico.
    """

    entities = extract_common_entities(
        original_question,
        normalized_question,
    )

    customer = extract_customer(
        original_question,
        normalized_question,
    )

    if customer:
        entities["customer"] = customer

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
    # Cliente específico
    # Deben evaluarse antes de reglas generales de clientes o ventas.
    # ------------------------------------------------------------------

    IntentRule(
        name="customer_receivable_detail",
        intent=SalesIntent.CUSTOMER_DETAIL,
        patterns=compile_patterns(
            r"\bcuanto\s+me\s+debe\b",
            r"\bcuanto\s+debe\s+\w+",
            r"\bdeuda\s+de\b",
            r"\bsaldo\s+pendiente\s+de\b",
        ),
        confidence=1.0,
        extractor=extract_customer_detail_entities,
    ),

    IntentRule(
        name="customer_sales_detail",
        intent=SalesIntent.CUSTOMER_DETAIL,
        patterns=compile_patterns(
            r"\bcuanto\s+le\s+he\s+vendido\s+a\b",
            r"\bcuanto\s+vendi\s+a\b",
            r"\bventas?\s+(?:del cliente\s+|de\s+|a\s+)\w+",
            r"\bfacturas?\s+del\s+cliente\s+\w+",
            r"\bdocumentos?\s+del\s+cliente\s+\w+",
        ),
        confidence=1.0,
        extractor=extract_customer_detail_entities,
    ),

    # ------------------------------------------------------------------
    # Documentos específicos
    # ------------------------------------------------------------------

    IntentRule(
        name="credit_notes",
        intent=SalesIntent.CREDIT_NOTES,
        patterns=compile_patterns(
            r"\bnotas?\s+de\s+credito\b",
            r"\bnota\s+credito\b",
            r"\bdocumentos?\s+de\s+credito\b",
            r"\bque\s+notas?\s+de\s+credito\s+tengo\b",
            r"\bcuantas?\s+notas?\s+de\s+credito\s+tengo\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="cancelled_documents",
        intent=SalesIntent.CANCELLED_DOCUMENTS,
        patterns=compile_patterns(
            r"\bdocumentos?\s+anulados?\b",
            r"\bfacturas?\s+anuladas?\b",
            r"\bventas?\s+anuladas?\b",
            r"\bcuantos?\s+documentos?\s+estan\s+anulados?\b",
            r"\bque\s+documentos?\s+fueron\s+anulados?\b",
            r"\bque\s+documentos?\s+tengo\s+anulados?\b",
            r"\bque\s+facturas?\s+tengo\s+anuladas?\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="linked_documents",
        intent=SalesIntent.LINKED_DOCUMENTS,
        patterns=compile_patterns(
            r"\bdocumentos?\s+vinculados?\b",
            r"\bfacturas?\s+vinculadas?\b",
            r"\bdocumentos?\s+con\s+linkage\b",
            r"\bcuantos?\s+documentos?\s+tienen\s+linkage\b",
            r"\bhay\s+documentos?\s+vinculados?\b",
            r"\bque\s+documentos?\s+estan\s+vinculados?\b",
            r"\bque\s+facturas?\s+estan\s+vinculadas?\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="largest_document",
        intent=SalesIntent.LARGEST_DOCUMENT,
        patterns=compile_patterns(
            r"\bfactura\s+(?:de\s+)?mayor\s+monto\b",
            r"\bdocumento\s+(?:de\s+)?mayor\s+monto\b",
            r"\bfactura\s+mas\s+grande\b",
            r"\bdocumento\s+mas\s+grande\b",
            r"\bmayor\s+factura\b",
            r"\bventa\s+mas\s+alta\b",
            r"\bcual\s+es\s+mi\s+venta\s+de\s+mayor\s+monto\b",
            r"\bcual\s+fue\s+mi\s+venta\s+de\s+mayor\s+monto\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="smallest_document",
        intent=SalesIntent.SMALLEST_DOCUMENT,
        patterns=compile_patterns(
            r"\bfactura\s+(?:de\s+)?menor\s+monto\b",
            r"\bdocumento\s+(?:de\s+)?menor\s+monto\b",
            r"\bfactura\s+mas\s+pequena\b",
            r"\bdocumento\s+mas\s+pequeno\b",
            r"\bmenor\s+factura\b",
            r"\bventa\s+mas\s+baja\b",
            r"\bcual\s+es\s+mi\s+venta\s+de\s+menor\s+monto\b",
            r"\bcual\s+fue\s+mi\s+venta\s+de\s+menor\s+monto\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    # ------------------------------------------------------------------
    # Vencimientos
    # ------------------------------------------------------------------

    IntentRule(
        name="documents_due_today",
        intent=SalesIntent.DOCUMENTS_DUE_TODAY,
        patterns=compile_patterns(
            r"\bvencen?\s+hoy\b",
            r"\bvencimiento\s+de\s+hoy\b",
            r"\bdocumentos?\s+por\s+vencer\s+hoy\b",
            r"\bfacturas?\s+que\s+vencen\s+hoy\b",
            r"\bque\s+documentos?\s+vencen\s+hoy\b",
            r"\bque\s+facturas?\s+vencen\s+hoy\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="documents_due_this_week",
        intent=SalesIntent.DOCUMENTS_DUE_THIS_WEEK,
        patterns=compile_patterns(
            r"\bvencen?\s+esta\s+semana\b",
            r"\bvencimiento\s+esta\s+semana\b",
            r"\bdocumentos?\s+por\s+vencer\s+esta\s+semana\b",
            r"\bfacturas?\s+que\s+vencen\s+esta\s+semana\b",
            r"\bque\s+documentos?\s+vencen\s+esta\s+semana\b",
            r"\bque\s+facturas?\s+vencen\s+esta\s+semana\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="documents_due_this_month",
        intent=SalesIntent.DOCUMENTS_DUE_THIS_MONTH,
        patterns=compile_patterns(
            r"\bvencen?\s+este\s+mes\b",
            r"\bvencimiento\s+este\s+mes\b",
            r"\bdocumentos?\s+por\s+vencer\s+este\s+mes\b",
            r"\bfacturas?\s+que\s+vencen\s+este\s+mes\b",
            r"\bque\s+documentos?\s+vencen\s+este\s+mes\b",
            r"\bque\s+facturas?\s+vencen\s+este\s+mes\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="documents_without_due_date",
        intent=SalesIntent.DOCUMENTS_WITHOUT_DUE_DATE,
        patterns=compile_patterns(
            r"\bsin\s+fecha\s+de\s+vencimiento\b",
            r"\bno\s+tienen\s+fecha\s+de\s+vencimiento\b",
            r"\bdocumentos?\s+sin\s+vencimiento\b",
            r"\bfacturas?\s+sin\s+vencimiento\b",
            r"\bque\s+documentos?\s+no\s+tienen\s+fecha\s+de\s+vencimiento\b",
            r"\bque\s+facturas?\s+no\s+tienen\s+fecha\s+de\s+vencimiento\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="overdue_documents",
        intent=SalesIntent.OVERDUE_DOCUMENTS,
        patterns=compile_patterns(
            r"\bdocumentos?\s+vencidos?\b",
            r"\bfacturas?\s+vencidas?\b",
            r"\bcuentas?\s+vencidas?\b",
            r"\bmorosidad\b",
            r"\bclientes?\s+morosos?\b",
            r"\bpendientes?\s+vencidos?\b",
            r"\bque\s+documentos?\s+tengo\s+vencidos?\b",
            r"\bque\s+facturas?\s+tengo\s+vencidas?\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    # ------------------------------------------------------------------
    # Cuentas por cobrar
    # ------------------------------------------------------------------
    
    IntentRule(
        name="receivable_documents_execute",
        intent=SalesIntent.RECEIVABLE_DOCUMENTS,
        operation=SalesOperation.EXECUTE,
        patterns=compile_patterns(
            r"\benvia\s+(?:un\s+)?correo\b.*\b(?:cobranza|facturas?|documentos?)\b",
            r"\benviar\s+(?:un\s+)?correo\b.*\b(?:cobranza|facturas?|documentos?)\b",
            r"\bmanda\s+(?:un\s+)?correo\b.*\b(?:cobranza|facturas?|documentos?)\b",
            r"\bmandar\s+(?:un\s+)?correo\b.*\b(?:cobranza|facturas?|documentos?)\b",
            r"\bcontacta\s+(?:por\s+correo\s+)?al\s+cliente\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bcontactar\s+(?:por\s+correo\s+)?al\s+cliente\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\benvia\s+(?:un\s+)?correo\s+de\s+cobranza\b",
            r"\bprepara\s+y\s+envia\s+(?:un\s+)?correo\s+de\s+cobranza\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="receivable_documents_propose",
        intent=SalesIntent.RECEIVABLE_DOCUMENTS,
        operation=SalesOperation.PROPOSE,
        patterns=compile_patterns(
            r"\bque\s+me\s+propones\s+hacer\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bque\s+podria\s+hacer\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bque\s+podemos\s+hacer\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bcomo\s+deberia\s+priorizar\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bque\s+acciones?\s+recomiendas?\b.*\b(?:cobro|cobranza|facturas?\s+pendientes)\b",
            r"\bque\s+acciones?\s+propones?\b.*\b(?:cobro|cobranza|facturas?\s+pendientes)\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="receivable_documents_explain",
        intent=SalesIntent.RECEIVABLE_DOCUMENTS,
        operation=SalesOperation.EXPLAIN,
        patterns=compile_patterns(
            r"\bdonde\s+se\s+concentra\b.*\bpendiente\s+por\s+cobrar\b",
            r"\bdonde\s+se\s+concentran\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bque\s+explica\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bcomo\s+se\s+distribuye\b.*\bpendiente\s+por\s+cobrar\b",
            r"\bcomo\s+se\s+distribuyen\b.*\b(?:facturas?|documentos?)\s+pendientes\b",
            r"\bque\s+clientes?\s+concentran\b.*\b(?:saldo|monto|pendiente)\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="receivable_documents",
        intent=SalesIntent.RECEIVABLE_DOCUMENTS,
        patterns=compile_patterns(
            r"\bque\s+facturas?\s+tengo\s+pendientes\b",
            r"\bque\s+documentos?\s+tengo\s+pendientes\b",
            r"\bmu[eé]strame\s+(?:los\s+)?documentos?\s+por\s+cobrar\b",
            r"\blista\s+(?:de\s+)?documentos?\s+por\s+cobrar\b",
            r"\bcuales\s+son\s+(?:las\s+)?facturas?\s+pendientes\b",
            r"\bmu[eé]strame\s+(?:las\s+)?facturas?\s+pendientes\b",
            r"\bdocumentos?\s+pendientes\s+de\s+cobro\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="total_receivable",
        intent=SalesIntent.TOTAL_RECEIVABLE,
        patterns=compile_patterns(
            r"\bcuanto\s+(?:dinero\s+)?tengo\s+por\s+cobrar\b",
            r"\bcuanto\s+me\s+deben\b",
            r"\bmonto\s+(?:total\s+)?por\s+cobrar\b",
            r"\btotal\s+por\s+cobrar\b",
            r"\bsaldo\s+pendiente\b",
            r"\bdinero\s+pendiente\s+de\s+cobro\b",
            r"\bcuanto\s+esta\s+pendiente\s+de\s+cobro\b",
            r"\bcuanto\s+falta\s+por\s+cobrar\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------

    IntentRule(
        name="customers_with_multiple_documents",
        intent=SalesIntent.CUSTOMERS_WITH_MULTIPLE_DOCUMENTS,
        patterns=compile_patterns(
            r"\bclientes?\s+con\s+mas\s+de\s+una\s+factura\b",
            r"\bclientes?\s+con\s+varias\s+facturas\b",
            r"\bclientes?\s+con\s+multiples\s+documentos\b",
            r"\bclientes?\s+que\s+repiten\b",
            r"\bclientes?\s+con\s+mas\s+documentos\b",
            r"\bque\s+clientes?\s+tienen\s+mas\s+de\s+un\s+documento\b",
            r"\bque\s+clientes?\s+tienen\s+varias\s+facturas\b",
            r"\bque\s+clientes?\s+tienen\s+multiples\s+documentos\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="top_customers",
        intent=SalesIntent.TOP_CUSTOMERS,
        patterns=compile_patterns(
            r"\btop\s+\d+\s+clientes\b",
            r"\bprincipales\s+\d*\s*clientes\b",
            r"\bmejores?\s+clientes?\b",
            r"\bclientes?\s+con\s+mayor\s+facturacion\b",
            r"\bclientes?\s+que\s+mas\s+compran\b",
            r"\bclientes?\s+con\s+mayores\s+ventas\b",
            r"\bcliente\s+que\s+mas\s+compra\b",
            r"\bquien\s+es\s+mi\s+mejor\s+cliente\b",
        ),
        confidence=1.0,
        extractor=extract_top_customers_entities,
    ),

    IntentRule(
        name="total_customers",
        intent=SalesIntent.TOTAL_CUSTOMERS,
        patterns=compile_patterns(
            r"\bcuantos?\s+clientes?\s+(?:distintos\s+)?(?:tengo|existen|hay)\b",
            r"\btotal\s+de\s+clientes\b",
            r"\bnumero\s+de\s+clientes\b",
            r"\bclientes?\s+unicos?\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    # ------------------------------------------------------------------
    # Tipos y estados
    # ------------------------------------------------------------------

    IntentRule(
        name="document_types",
        intent=SalesIntent.DOCUMENT_TYPES,
        patterns=compile_patterns(
            r"\btipos?\s+de\s+documentos?\b",
            r"\bpor\s+tipo\s+de\s+documento\b",
            r"\bcuantas?\s+facturas?\s+exentas?\b",
            r"\bque\s+tipo\s+de\s+documento\s+predomina\b",
            r"\bmonto\s+por\s+tipo\s+de\s+documento\b",
            r"\bcuanto\s+representa\s+cada\s+tipo\b",
            r"\bque\s+tipos?\s+de\s+documentos?\s+tengo\b",
            r"\bcuales\s+son\s+los\s+tipos?\s+de\s+documentos?\b",
            r"\bque\s+clases?\s+de\s+documentos?\s+tengo\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="document_status",
        intent=SalesIntent.DOCUMENT_STATUS,
        patterns=compile_patterns(
            r"\bestados?\s+de\s+(?:los\s+)?documentos?\b",
            r"\bdocumentos?\s+por\s+estado\b",
            r"\bmonto\s+por\s+estado\b",
            r"\bque\s+estados?\s+existen\b",
            r"\bdistribucion\s+por\s+estado\b",
            r"\bcual\s+es\s+el\s+estado\s+de\s+(?:mis\s+)?facturas?\b",
            r"\bcual\s+es\s+el\s+estado\s+de\s+(?:mis\s+)?documentos?\b",
            r"\bcomo\s+estan\s+(?:mis\s+)?facturas?\b",
            r"\bcomo\s+estan\s+(?:mis\s+)?documentos?\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    # ------------------------------------------------------------------
    # Tendencias y comparaciones
    # ------------------------------------------------------------------

    IntentRule(
        name="sales_comparison",
        intent=SalesIntent.SALES_COMPARISON,
        patterns=compile_patterns(
            r"\bvendimos?\s+mas\s+que\s+el\s+mes\s+pasado\b",
            r"\bcomparar\s+ventas\b",
            r"\bcomparacion\s+de\s+ventas\b",
            r"\bventas?\s+versus\b",
            r"\bventas?\s+vs\b",
            r"\bmes\s+actual\s+contra\s+mes\s+anterior\b",
        ),
        confidence=0.95,
        extractor=extract_common_entities,
    ),
    
    IntentRule(
        name="sales_trend_propose",
        intent=SalesIntent.SALES_TREND,
        operation=SalesOperation.PROPOSE,
        patterns=compile_patterns(
            r"\bque\s+me\s+propones\s+hacer\b.*\b(?:tendencia|ventas)\b",
            r"\bque\s+podria\s+hacer\b.*\b(?:mejorar|revertir|cambiar)\b.*\b(?:tendencia|ventas)\b",
            r"\bque\s+podemos\s+hacer\b.*\b(?:mejorar|revertir|cambiar)\b.*\b(?:tendencia|ventas)\b",
            r"\bcomo\s+podria\s+mejorar\b.*\b(?:tendencia|ventas)\b",
            r"\bcomo\s+podemos\s+mejorar\b.*\b(?:tendencia|ventas)\b",
            r"\bque\s+acciones?\s+recomiendas?\b.*\b(?:tendencia|ventas)\b",
            r"\bque\s+acciones?\s+propones?\b.*\b(?:tendencia|ventas)\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),
    
    IntentRule(
        name="sales_trend_explain",
        intent=SalesIntent.SALES_TREND,
        operation=SalesOperation.EXPLAIN,
        patterns=compile_patterns(
            r"\bque\s+explica\s+(?:la\s+)?tendencia\s+de\s+(?:mis\s+|las\s+)?ventas\b",
            r"\bque\s+explica\s+(?:la\s+)?evolucion\s+de\s+(?:mis\s+|las\s+)?ventas\b",
            r"\b(?:por\s+que|porque)\b.*\b(?:tendencia|evolucion)\b.*\bventas\b",
            r"\bque\s+factores?\s+explican\b.*\b(?:tendencia|evolucion)\b.*\bventas\b",
            r"\bque\s+esta\s+explicando\b.*\b(?:tendencia|evolucion)\b.*\bventas\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="sales_trend",
        intent=SalesIntent.SALES_TREND,
        patterns=compile_patterns(
            r"\bevolucion\s+de\s+(?:las\s+)?ventas\b",
            r"\btendencia\s+de\s+(?:las\s+)?ventas\b",
            r"\bcomo\s+han\s+cambiado\s+(?:las\s+)?ventas\b",
            r"\bcrecimiento\s+de\s+(?:las\s+)?ventas\b",
            r"\bventas?\s+en\s+el\s+tiempo\b",
            r"\bcomo\s+vienen\s+evolucionando\s+(?:mis\s+|las\s+)?ventas\b",
            r"\bcomo\s+vienen\s+(?:mis\s+|las\s+)?ventas\b",
        ),
        confidence=0.95,
        extractor=extract_common_entities,
    ),
    
    IntentRule(
        name="monthly_sales_explain",
        intent=SalesIntent.MONTHLY_SALES,
        operation=SalesOperation.EXPLAIN,
        patterns=compile_patterns(
            r"\b(?:por\s+que|porque)\b.*\b(?:vendi|vendimos|ventas?)\b.*\b(?:mes\s+pasado|mes\s+anterior)\b",
            r"\b(?:por\s+que|porque)\b.*\b(?:vendi|vendimos|ventas?)\b.*\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
            r"\bque\s+explica\b.*\b(?:ventas?|caida|aumento)\b.*\b(?:mes\s+pasado|mes\s+anterior)\b",
            r"\bque\s+paso\s+con\b.*\b(?:las\s+)?ventas\b.*\b(?:mes\s+pasado|mes\s+anterior)\b",
            r"\b(?:por\s+que|porque)\b.*\b(?:bajaron|subieron|cayeron|aumentaron)\b.*\bventas\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="monthly_sales",
        intent=SalesIntent.MONTHLY_SALES,
        patterns=compile_patterns(
            r"\bcuanto\s+vendi\s+en\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
            r"\bventas?\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b",
            r"\bventas?\s+del\s+mes\b",
            r"\bventas?\s+mensuales?\b",
            r"\bmonto\s+vendido\s+en\s+el\s+mes\b",
            r"\bcuanto\s+vendi\s+(?:el\s+)?mes\s+pasado\b",
            r"\bcuanto\s+vendi\s+(?:el\s+)?mes\s+anterior\b",
            r"\bventas?\s+del\s+mes\s+pasado\b",
            r"\bventas?\s+del\s+mes\s+anterior\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    # ------------------------------------------------------------------
    # Totales y overview
    # ------------------------------------------------------------------

    IntentRule(
        name="total_sales_amount",
        intent=SalesIntent.TOTAL_SALES_AMOUNT,
        patterns=compile_patterns(
            r"\bcuanto\s+he\s+vendido\b",
            r"\bcuanto\s+vendi\b",
            r"\bcuanto\s+vendimos\b",
            r"\bcuanto\s+hemos\s+vendido\b",
            r"\bmonto\s+total\s+de\s+ventas\b",
            r"\btotal\s+vendido\b",
            r"\btotal\s+de\s+ventas\b",
            r"\bventa\s+total\b",
            r"\bventas?\s+totales?\b",
            r"\bmonto\s+vendido\b",
            r"\bcuanto\s+dinero\s+representan\s+(?:las\s+)?ventas\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="total_documents",
        intent=SalesIntent.TOTAL_DOCUMENTS,
        patterns=compile_patterns(
            r"\bcuantos?\s+documentos?\s+(?:tengo|existen|hay)\b",
            r"\btotal\s+de\s+documentos\b",
            r"\bnumero\s+de\s+documentos\b",
            r"\bcuantas?\s+facturas?\s+(?:tengo|existen|hay)\b",
            r"\btotal\s+de\s+facturas\b",
            r"\bcuantos?\s+documentos?\s+de\s+venta\b",
            r"\bcuantos?\s+documentos?\s+comerciales\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),

    IntentRule(
        name="sales_overview",
        intent=SalesIntent.SALES_OVERVIEW,
        patterns=compile_patterns(
            r"\bresumen\s+(?:general\s+)?de\s+(?:(?:mis|las)\s+)?ventas\b",
            r"\bdame\s+(?:un\s+)?resumen\s+(?:general\s+)?de\s+(?:(?:mis|las)\s+)?ventas\b",
            r"\bpanorama\s+(?:general\s+)?de\s+(?:(?:mis|las)\s+)?ventas\b",
            r"\bvision\s+general\s+de\s+(?:(?:mis|las)\s+)?ventas\b",
            r"\bestado\s+general\s+de\s+(?:(?:mis|las)\s+)?ventas\b",
            r"\bcomo\s+estan\s+(?:(?:mis|las)\s+)?ventas\b",
            r"\bdame\s+un\s+resumen\s+comercial\b",
            r"\bresumen\s+comercial\b",
        ),
        confidence=1.0,
        extractor=extract_common_entities,
    ),
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class SalesIntentRouter:
    """
    Router determinista para preguntas comerciales.

    Las reglas se evalúan en orden. Por esta razón, las intenciones más
    específicas deben aparecer antes que las más generales.
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
    ) -> IntentResult:
        """
        Clasifica una pregunta y retorna un resultado estructurado.
        """

        if not isinstance(question, str):
            raise TypeError("question debe ser un string.")

        original_question = question.strip()

        if not original_question:
            return IntentResult.unknown(
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

            return IntentResult(
                intent=rule.intent,
                operation=rule.operation,
                confidence=rule.confidence,
                entities=entities,
                matched_rule=rule.name,
                normalized_question=normalized_question,
                original_question=original_question,
            )

        return IntentResult.unknown(
            original_question=original_question,
            normalized_question=normalized_question,
            matched_rule="no_matching_rule",
        )


# ---------------------------------------------------------------------------
# Instancia y función pública
# ---------------------------------------------------------------------------


_default_router = SalesIntentRouter()


def route_sales_intent(
    question: str,
) -> IntentResult:
    """
    Función pública simplificada para clasificar una pregunta.

    Ejemplo
    -------
    result = route_sales_intent(
        "¿Cuánto dinero tengo por cobrar?"
    )
    """

    return _default_router.route(question)


# ---------------------------------------------------------------------------
# Ejecución manual
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    example_questions = (
        "¿Cuánto dinero tengo por cobrar?",
        "Muéstrame las notas de crédito.",
        "¿Cuáles son mis 10 principales clientes?",
        "Muéstrame las facturas de Frogmi.",
        "¿Cuánto le he vendido a OSHER en enero de 2026?",
        "¿Cuál fue la factura de mayor monto?",
        "¿Qué documentos vencen esta semana?",
        "¿Cuántos clientes distintos existen?",
        "Dame un resumen general de las ventas.",
        "Cuéntame una historia sobre contabilidad.",
        "¿Cuánto vendí el mes pasado?",
        "¿Por qué vendí menos el mes pasado?", 
        "¿Por qué vendí menos en julio?", 
        "¿Qué pasó con las ventas del mes pasado?", 
        "¿Cómo vienen evolucionando mis ventas?",
        "¿Qué explica la tendencia de mis ventas?",
        "¿Qué me propones hacer para mejorar la tendencia de mis ventas?",
        "¿Qué facturas tengo pendientes?",
        "¿Dónde se concentra lo que tengo pendiente por cobrar?",
        "¿Qué me propones hacer con las facturas pendientes?",
    )

    for example_question in example_questions:
        result = route_sales_intent(example_question)

        print("=" * 80)
        print(f"Pregunta   : {example_question}")
        print(f"Intent     : {result.intent.value}")
        print(f"Operación  : {result.operation.value}")
        print(f"Confianza  : {result.confidence}")
        print(f"Regla      : {result.matched_rule}")
        print(f"Entidades  : {result.entities}")