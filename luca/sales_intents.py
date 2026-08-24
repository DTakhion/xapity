# luca/sales_intents.py
"""
Definiciones de intenciones comerciales para el agente de ventas de Luca.

Este módulo contiene únicamente estructuras de dominio:

- SalesIntent:
    Catálogo de intenciones que el agente puede reconocer.

- IntentResult:
    Resultado estructurado producido por el router de intenciones.

No contiene reglas de clasificación, consultas a MongoDB ni generación
de respuestas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class SalesOperation(str, Enum):
    """
    Tipo de operación solicitada por el usuario sobre una capacidad comercial.

    La intención define sobre qué información se trabaja.
    La operación define qué desea hacer el usuario con esa información.
    """

    QUERY = "query"
    EXPLAIN = "explain"
    PROPOSE = "propose"
    EXECUTE = "execute"

class SalesIntent(str, Enum):
    """
    Intenciones comerciales soportadas por el agente de ventas.

    Cada valor representa una capacidad determinista que posteriormente
    será enlazada con una función de ``sales_query_service.py``.
    """

    # ------------------------------------------------------------------
    # Resumen general
    # ------------------------------------------------------------------

    SALES_OVERVIEW = "sales_overview" # “Dame un resumen de mis ventas”
    TOTAL_DOCUMENTS = "total_documents" # ¿Cuántos documentos de venta tengo?
    TOTAL_SALES_AMOUNT = "total_sales_amount" # ¿Cuánto he vendido?
    TOTAL_CUSTOMERS = "total_customers" # ¿Cuántos clientes tengo?

    # ------------------------------------------------------------------
    # Cuentas por cobrar
    # ------------------------------------------------------------------

    TOTAL_RECEIVABLE = "total_receivable" # ¿Cuánto tengo por cobrar?
    RECEIVABLE_DOCUMENTS = "receivable_documents" # ¿Qué facturas tengo pendientes?

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------

    TOP_CUSTOMERS = "top_customers" # ¿Quiénes son mis mejores clientes?
    CUSTOMER_DETAIL = "customer_detail" # ¿Cuánto le he vendido a Frogmi?
    CUSTOMERS_WITH_MULTIPLE_DOCUMENTS = "customers_with_multiple_documents" # ¿Qué clientes tienen más de un documento?

    # ------------------------------------------------------------------
    # Documentos comerciales
    # ------------------------------------------------------------------

    CREDIT_NOTES = "credit_notes" # ¿Qué notas de crédito tengo?
    CANCELLED_DOCUMENTS = "cancelled_documents" # ¿Qué documentos tengo anulados?
    LINKED_DOCUMENTS = "linked_documents" # ¿Qué documentos están vinculados?

    LARGEST_DOCUMENT = "largest_document" # ¿Cuál es mi venta de mayor monto?
    SMALLEST_DOCUMENT = "smallest_document" # ¿Cuál es mi venta de menor monto?

    # ------------------------------------------------------------------
    # Clasificaciones y agrupaciones
    # ------------------------------------------------------------------

    DOCUMENT_TYPES = "document_types" # ¿Qué tipos de documentos tengo?, ¿Cuántas facturas y notas de crédito tengo?, Muéstrame la distribución por tipo de documento.
    DOCUMENT_STATUS = "document_status" # ¿Cuál es el estado de mis facturas?, ¿Cuántas facturas están por cobrar?, Dame la distribución de documentos por estado.

    # ------------------------------------------------------------------
    # Fechas y vencimientos
    # ------------------------------------------------------------------

    DOCUMENTS_DUE_TODAY = "documents_due_today" # ¿Qué documentos vencen hoy?
    DOCUMENTS_DUE_THIS_WEEK = "documents_due_this_week" # ¿Qué documentos vencen esta semana?
    DOCUMENTS_DUE_THIS_MONTH = "documents_due_this_month" # ¿Qué documentos vencen este mes?
    OVERDUE_DOCUMENTS = "overdue_documents" # ¿Qué documentos tengo vencidos?
    DOCUMENTS_WITHOUT_DUE_DATE = "documents_without_due_date" # ¿Qué documentos no tienen fecha de vencimiento?

    # ------------------------------------------------------------------
    # Comparaciones y tendencias
    # ------------------------------------------------------------------

    MONTHLY_SALES = "monthly_sales" # ¿Cuánto vendí el mes pasado?
    SALES_COMPARISON = "sales_comparison" # ¿Vendí más este mes que el anterior?
    SALES_TREND = "sales_trend"  # QUERY: evolución | EXPLAIN: qué la explica | PROPOSE: qué hacer al respecto

    # ------------------------------------------------------------------
    # Intención no reconocida
    # ------------------------------------------------------------------

    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class IntentResult:
    """
    Resultado de la clasificación realizada por el router.

    Attributes
    ----------
    intent:
        Intención comercial detectada.

    confidence:
        Nivel de confianza entre 0.0 y 1.0.

    entities:
        Entidades extraídas desde la pregunta. Por ejemplo:

        {
            "customer": "Frogmi",
            "limit": 10,
            "year": 2026,
            "month": 1
        }

    matched_rule:
        Nombre o identificador de la regla que produjo la clasificación.

    normalized_question:
        Pregunta normalizada utilizada durante el análisis.

    original_question:
        Pregunta original recibida desde el usuario.
    """

    intent: SalesIntent
    confidence: float
    operation: SalesOperation = SalesOperation.QUERY
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

        if not isinstance(self.intent, SalesIntent):
            raise TypeError(
                "intent debe ser una instancia de SalesIntent."
            )
        
        if not isinstance(self.operation, SalesOperation):
            raise TypeError(
                "operation debe ser una instancia de SalesOperation."
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
        Indica si el router no logró reconocer la intención.
        """

        return self.intent is SalesIntent.UNKNOWN

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
            "operation": self.operation.value,
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
    ) -> "IntentResult":
        """
        Construye un resultado estándar para una intención desconocida.
        """

        return cls(
            intent=SalesIntent.UNKNOWN,
            confidence=0.0,
            entities={},
            matched_rule=matched_rule,
            normalized_question=normalized_question,
            original_question=original_question,
        )