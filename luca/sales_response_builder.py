# luca/sales_response_builder.py
"""
Construcción determinista de respuestas comerciales para Luca.

Este módulo recibe:

- la intención comercial detectada;
- el resultado estructurado de sales_query_service.py;

y devuelve una respuesta natural para el usuario.

No realiza:

- consultas a Mongo;
- detección de intenciones;
- cálculos comerciales adicionales;
- llamadas a modelos de lenguaje.

La información numérica siempre proviene del servicio determinista
de consultas comerciales.

Capacidades actualmente implementadas:

- SALES_OVERVIEW
- TOTAL_RECEIVABLE
- CREDIT_NOTES
- CANCELLED_DOCUMENTS
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from luca.sales_intents import (
    SalesIntent,
    SalesOperation,
)


# ==================================================
# TIPOS
# ==================================================


ResponseBuilderHandler = Callable[
    [Mapping[str, Any]],
    str,
]


@dataclass(frozen=True, slots=True)
class SalesResponseBuildResult:
    """
    Resultado estructurado del constructor de respuestas.

    Attributes
    ----------
    answer:
        Texto natural que será mostrado al usuario.

    intent:
        Intención utilizada para construir la respuesta.

    builder:
        Nombre del constructor ejecutado.

    deterministic:
        Indica que el texto fue generado mediante reglas
        deterministas, sin participación de un LLM.
    """

    answer: str
    intent: str
    operation: str
    builder: str
    deterministic: bool = True

    def to_dict(self) -> dict[str, Any]:
        """
        Convierte el resultado a un diccionario serializable.
        """

        return {
            "answer": self.answer,
            "intent": self.intent,
            "operation": self.operation,
            "builder": self.builder,
            "deterministic": self.deterministic,
        }


# ==================================================
# VALIDACIONES
# ==================================================


def _validate_execution_result(
    execution_result: Mapping[str, Any],
    operation: SalesOperation,
) -> None:
    """
    Valida la estructura mínima según la operación ejecutada.
    """

    if not isinstance(execution_result, Mapping):
        raise TypeError(
            "execution_result debe ser un mapping."
        )

    if operation is SalesOperation.QUERY:
        result = execution_result.get("result")

        if result is None:
            raise ValueError(
                "execution_result no contiene la clave 'result'."
            )

        if not isinstance(result, Mapping):
            raise TypeError(
                "execution_result['result'] debe ser un mapping."
            )

        filters = execution_result.get("filters")

        if (
            filters is not None
            and not isinstance(filters, Mapping)
        ):
            raise TypeError(
                "execution_result['filters'] debe ser un mapping "
                "o None."
            )

        return

    if operation is SalesOperation.EXPLAIN:
        analysis = execution_result.get("analysis")

        if analysis is None:
            raise ValueError(
                "execution_result no contiene la clave 'analysis'."
            )

        if not isinstance(analysis, Mapping):
            raise TypeError(
                "execution_result['analysis'] debe ser un mapping."
            )

        return
    
    if operation is SalesOperation.PROPOSE:
        proposal = execution_result.get("proposal")

        if proposal is None:
            raise ValueError(
                "execution_result no contiene la clave 'proposal'."
            )

        if not isinstance(proposal, Mapping):
            raise TypeError(
                "execution_result['proposal'] debe ser un mapping."
            )

        return
    
    if operation is SalesOperation.EXECUTE:
        status = execution_result.get("status")

        if not isinstance(status, str):
            raise ValueError(
                "execution_result no contiene un 'status' válido."
            )

        execution = execution_result.get("execution")

        if (
            execution is not None
            and not isinstance(execution, Mapping)
        ):
            raise TypeError(
                "execution_result['execution'] debe ser "
                "un mapping o None."
            )

        return

    raise ValueError(
        f"Operación no soportada: {operation.value}"
    )

def _validate_operation(
    operation: SalesOperation,
) -> None:
    if not isinstance(operation, SalesOperation):
        raise TypeError(
            "operation debe ser una instancia de SalesOperation."
        )


def _validate_intent(
    intent: SalesIntent,
) -> None:
    if not isinstance(intent, SalesIntent):
        raise TypeError(
            "intent debe ser una instancia de SalesIntent."
        )


# ==================================================
# ACCESO SEGURO
# ==================================================


def _get_result(
    query_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    result = query_result.get(
        "result",
        {},
    )

    return (
        result
        if isinstance(result, Mapping)
        else {}
    )

def _get_analysis(
    execution_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    analysis = execution_result.get(
        "analysis",
        {},
    )

    return (
        analysis
        if isinstance(analysis, Mapping)
        else {}
    )

def _get_proposal(
    execution_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    proposal = execution_result.get(
        "proposal",
        {},
    )

    return (
        proposal
        if isinstance(proposal, Mapping)
        else {}
    )

def _get_execution(
    execution_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    execution = execution_result.get(
        "execution",
        {},
    )

    return (
        execution
        if isinstance(execution, Mapping)
        else {}
    )


def _get_filters(
    query_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    filters = query_result.get(
        "filters",
        {},
    )

    return (
        filters
        if isinstance(filters, Mapping)
        else {}
    )


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    if value is None:
        return default

    if isinstance(value, bool):
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None:
        return default

    if isinstance(value, str):
        normalized = (
            value.strip()
            .replace("$", "")
            .replace(" ", "")
        )

        if (
            "." in normalized
            and "," in normalized
        ):
            normalized = (
                normalized
                .replace(".", "")
                .replace(",", ".")
            )

        elif "," in normalized:
            normalized = normalized.replace(
                ",",
                ".",
            )

        value = normalized

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ==================================================
# FORMATO DE VALORES
# ==================================================


def format_clp(
    value: Any,
) -> str:
    """
    Formatea un monto como peso chileno.

    Ejemplos
    --------
    1250000
        -> $1.250.000

    -45000
        -> -$45.000
    """

    amount = round(
        _safe_float(value)
    )

    absolute_amount = abs(amount)

    formatted = (
        f"{absolute_amount:,}"
        .replace(",", ".")
    )

    sign = "-" if amount < 0 else ""

    return f"{sign}${formatted}"


def format_number(
    value: Any,
) -> str:
    """
    Formatea un entero usando separador de miles chileno.
    """

    number = _safe_int(value)

    return f"{number:,}".replace(
        ",",
        ".",
    )


def format_period(
    *,
    year: Any = None,
    month: Any = None,
) -> str:
    """
    Construye una frase temporal breve.

    Ejemplos
    --------
    year=2026, month=1
        -> " durante enero de 2026"

    year=2026
        -> " durante 2026"

    year=None, month=None
        -> ""
    """

    resolved_year = (
        _safe_int(year)
        if year is not None
        else None
    )

    resolved_month = (
        _safe_int(month)
        if month is not None
        else None
    )

    month_names = {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "septiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre",
    }

    month_name = month_names.get(
        resolved_month
    )

    if (
        resolved_year is not None
        and month_name is not None
    ):
        return (
            f" durante {month_name} "
            f"de {resolved_year}"
        )

    if resolved_year is not None:
        return f" durante {resolved_year}"

    if month_name is not None:
        return f" durante {month_name}"

    return ""


def _singular_or_plural(
    amount: int,
    *,
    singular: str,
    plural: str,
) -> str:
    return (
        singular
        if amount == 1
        else plural
    )


# ==================================================
# OVERVIEW
# ==================================================


def build_sales_overview_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para SALES_OVERVIEW.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    total_documents = _safe_int(
        result.get("totalDocuments")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    receivable_documents = _safe_int(
        result.get("receivableDocuments")
    )

    receivable_amount = _safe_float(
        result.get("receivableAmount")
    )

    unique_customers = _safe_int(
        result.get("uniqueCustomers")
    )

    credit_notes = _safe_int(
        result.get("creditNotes")
    )

    cancelled_documents = _safe_int(
        result.get("cancelledDocuments")
    )

    linked_documents = _safe_int(
        result.get("linkedDocuments")
    )

    if total_documents == 0:
        return (
            f"No encontré documentos de venta"
            f"{period}."
        )

    document_word = _singular_or_plural(
        total_documents,
        singular="documento",
        plural="documentos",
    )

    customer_word = _singular_or_plural(
        unique_customers,
        singular="cliente único",
        plural="clientes únicos",
    )

    parts = [
        (
            f"El resumen comercial{period} registra "
            f"{format_number(total_documents)} "
            f"{document_word} por un total de "
            f"{format_clp(total_amount)}."
        ),
        (
            f"Actualmente hay "
            f"{format_number(receivable_documents)} "
            f"documentos por cobrar, equivalentes a "
            f"{format_clp(receivable_amount)}."
        ),
        (
            f"Los documentos corresponden a "
            f"{format_number(unique_customers)} "
            f"{customer_word}."
        ),
    ]

    additional_details: list[str] = []

    if credit_notes > 0:
        credit_note_word = _singular_or_plural(
            credit_notes,
            singular="nota de crédito",
            plural="notas de crédito",
        )

        additional_details.append(
            f"{format_number(credit_notes)} "
            f"{credit_note_word}"
        )

    if cancelled_documents > 0:
        cancelled_word = _singular_or_plural(
            cancelled_documents,
            singular="documento anulado",
            plural="documentos anulados",
        )

        additional_details.append(
            f"{format_number(cancelled_documents)} "
            f"{cancelled_word}"
        )

    if linked_documents > 0:
        linked_word = _singular_or_plural(
            linked_documents,
            singular="documento vinculado",
            plural="documentos vinculados",
        )

        additional_details.append(
            f"{format_number(linked_documents)} "
            f"{linked_word}"
        )

    if additional_details:
        parts.append(
            "Además, se identificaron "
            + ", ".join(additional_details)
            + "."
        )

    return " ".join(parts)

# ==================================================
# TOTAL DOCUMENTOS
# ==================================================


def build_total_documents_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para TOTAL_DOCUMENTS.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré documentos de venta"
            f"{period}."
        )

    document_word = _singular_or_plural(
        documents_count,
        singular="documento de venta",
        plural="documentos de venta",
    )

    return (
        f"Tienes "
        f"{format_number(documents_count)} "
        f"{document_word}{period}, "
        f"por un monto total de "
        f"{format_clp(total_amount)}."
    )

# ==================================================
# TOTAL POR COBRAR
# ==================================================


def build_total_receivable_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para TOTAL_RECEIVABLE.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré documentos por cobrar"
            f"{period}."
        )

    document_word = _singular_or_plural(
        documents_count,
        singular="documento",
        plural="documentos",
    )

    return (
        f"Tienes {format_clp(total_amount)} "
        f"por cobrar{period}, distribuidos en "
        f"{format_number(documents_count)} "
        f"{document_word}."
    )

# ==================================================
# DOCUMENTOS POR COBRAR — CONSULTA
# ==================================================


def build_receivable_documents_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta QUERY para RECEIVABLE_DOCUMENTS.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    returned_documents_count = _safe_int(
        result.get("returnedDocumentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    documents = result.get(
        "documents",
        [],
    )

    if documents_count == 0:
        return (
            f"No encontré facturas pendientes"
            f"{period}."
        )

    parts = [
        (
            f"Tienes {format_number(documents_count)} "
            f"facturas pendientes{period}, "
            f"por un total de "
            f"{format_clp(total_amount)}."
        )
    ]

    if isinstance(documents, list) and documents:
        details: list[str] = []

        for document in documents[:5]:
            customer_name = (
                document.get("customerName")
                or document.get("customerRut")
                or "cliente sin identificar"
            )

            amount = _safe_float(
                document.get("amount")
            )

            due_date = document.get(
                "dueDate"
            )

            due_date_text = ""

            if due_date:
                due_date_text = (
                    f", vencimiento {str(due_date)[:10]}"
                )

            details.append(
                f"{customer_name}: "
                f"{format_clp(amount)}"
                f"{due_date_text}"
            )

        parts.append(
            "Entre las principales están: "
            + "; ".join(details)
            + "."
        )

    if (
        returned_documents_count > 0
        and returned_documents_count < documents_count
    ):
        parts.append(
            f"Estoy mostrando "
            f"{format_number(returned_documents_count)} "
            f"de los "
            f"{format_number(documents_count)} "
            f"documentos pendientes."
        )

    return " ".join(parts)

# ==================================================
# DOCUMENTOS POR COBRAR — EXPLICACIÓN
# ==================================================


def build_receivable_documents_explanation_response(
    execution_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta EXPLAIN para RECEIVABLE_DOCUMENTS.
    """

    analysis = _get_analysis(
        execution_result
    )

    documents_count = _safe_int(
        analysis.get("documentsCount")
    )

    total_amount = _safe_float(
        analysis.get("totalAmount")
    )

    overdue_documents_count = _safe_int(
        analysis.get("overdueDocumentsCount")
    )

    overdue_amount = _safe_float(
        analysis.get("overdueAmount")
    )

    overdue_pct = analysis.get(
        "overduePct"
    )

    primary_customer = analysis.get(
        "primaryCustomer"
    )

    if documents_count == 0:
        return (
            "No encontré documentos pendientes "
            "para analizar."
        )

    parts = [
        (
            f"Tienes {format_clp(total_amount)} "
            f"pendientes por cobrar, distribuidos en "
            f"{format_number(documents_count)} documentos."
        )
    ]

    if isinstance(primary_customer, Mapping):
        customer_name = (
            primary_customer.get("customerName")
            or primary_customer.get("customerRut")
            or "El principal cliente"
        )

        customer_amount = _safe_float(
            primary_customer.get(
                "totalAmount"
            )
        )

        concentration_pct = primary_customer.get(
            "concentrationPct"
        )

        if concentration_pct is not None:
            parts.append(
                f"{customer_name} concentra aproximadamente "
                f"el {_safe_float(concentration_pct):.1f}% "
                f"del saldo pendiente, equivalente a "
                f"{format_clp(customer_amount)}."
            )
        else:
            parts.append(
                f"{customer_name} es el principal cliente "
                f"pendiente, con "
                f"{format_clp(customer_amount)}."
            )

    if overdue_documents_count > 0:
        overdue_pct_text = ""

        if overdue_pct is not None:
            overdue_pct_text = (
                f", equivalente al "
                f"{_safe_float(overdue_pct):.1f}% "
                f"del saldo"
            )

        parts.append(
            f"Además, "
            f"{format_number(overdue_documents_count)} "
            f"documentos ya están vencidos por "
            f"{format_clp(overdue_amount)}"
            f"{overdue_pct_text}."
        )

    return " ".join(parts)

# ==================================================
# DOCUMENTOS POR COBRAR — PROPUESTA
# ==================================================


def build_receivable_documents_proposal_response(
    execution_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta PROPOSE para RECEIVABLE_DOCUMENTS.
    """

    proposal = _get_proposal(
        execution_result
    )

    proposals_count = _safe_int(
        proposal.get("proposalsCount")
    )

    primary_proposal = proposal.get(
        "primaryProposal"
    )

    proposals = proposal.get(
        "proposals",
        [],
    )

    if (
        proposals_count == 0
        or not isinstance(
            primary_proposal,
            Mapping,
        )
    ):
        return (
            "No encontré evidencia suficiente para "
            "proponer una prioridad de cobranza concreta."
        )

    proposal_type = primary_proposal.get(
        "proposalType"
    )

    parts: list[str] = []

    # --------------------------------------------------
    # Cliente con alta concentración
    # --------------------------------------------------

    if (
        proposal_type
        == "prioritize_key_receivable_customer"
    ):
        target = primary_proposal.get(
            "target",
            {},
        )

        evidence = primary_proposal.get(
            "evidence",
            {},
        )

        customer_name = (
            target.get("customerName")
            or target.get("customerRut")
            or "este cliente"
        )

        customer_amount = _safe_float(
            evidence.get(
                "customerAmount"
            )
        )

        concentration_pct = _safe_float(
            evidence.get(
                "concentrationPct"
            )
        )

        parts.append(
            f"Te sugiero priorizar la cobranza de "
            f"{customer_name}, porque concentra "
            f"aproximadamente el "
            f"{concentration_pct:.1f}% "
            f"del saldo pendiente, equivalente a "
            f"{format_clp(customer_amount)}."
        )

    # --------------------------------------------------
    # Alta proporción vencida
    # --------------------------------------------------

    elif (
        proposal_type
        == "prioritize_overdue_receivables"
    ):
        evidence = primary_proposal.get(
            "evidence",
            {},
        )

        overdue_amount = _safe_float(
            evidence.get(
                "overdueAmount"
            )
        )

        overdue_pct = _safe_float(
            evidence.get(
                "overduePct"
            )
        )

        parts.append(
            f"Te sugiero priorizar los documentos vencidos, "
            f"porque representan aproximadamente el "
            f"{overdue_pct:.1f}% del saldo pendiente, "
            f"equivalente a "
            f"{format_clp(overdue_amount)}."
        )

    # --------------------------------------------------
    # Documento individual relevante
    # --------------------------------------------------

    elif (
        proposal_type
        == "prioritize_largest_receivable"
    ):
        target = primary_proposal.get(
            "target",
            {},
        )

        evidence = primary_proposal.get(
            "evidence",
            {},
        )

        customer_name = (
            target.get("customerName")
            or target.get("customerRut")
            or "el cliente asociado"
        )

        document_amount = _safe_float(
            evidence.get(
                "documentAmount"
            )
        )

        share_pct = _safe_float(
            evidence.get(
                "shareOfReceivablePct"
            )
        )

        parts.append(
            f"Te sugiero priorizar el documento de "
            f"{customer_name} por "
            f"{format_clp(document_amount)}, "
            f"ya que representa aproximadamente "
            f"el {share_pct:.1f}% "
            f"del saldo pendiente."
        )

    # --------------------------------------------------
    # Fallback
    # --------------------------------------------------

    elif (
        proposal_type
        == "review_receivable_portfolio"
    ):
        parts.append(
            "Te sugiero revisar la cartera pendiente "
            "por monto y antigüedad, porque no existe "
            "un único cliente o documento que concentre "
            "suficiente saldo como para priorizarlo por sí solo."
        )

    else:
        parts.append(
            "Identifiqué una prioridad de cobranza, "
            "pero todavía no tengo una forma específica "
            "de presentarla."
        )

    # --------------------------------------------------
    # Propuestas complementarias
    # --------------------------------------------------

    if isinstance(proposals, list):
        overdue_proposal = next(
            (
                item
                for item in proposals
                if isinstance(item, Mapping)
                and item.get("proposalType")
                == "prioritize_overdue_receivables"
                and item is not primary_proposal
            ),
            None,
        )

        if isinstance(
            overdue_proposal,
            Mapping,
        ):
            evidence = overdue_proposal.get(
                "evidence",
                {},
            )

            overdue_amount = _safe_float(
                evidence.get(
                    "overdueAmount"
                )
            )

            overdue_pct = _safe_float(
                evidence.get(
                    "overduePct"
                )
            )

            parts.append(
                f"Además, conviene abordar primero "
                f"los documentos vencidos: representan "
                f"el {overdue_pct:.1f}% del saldo, "
                f"por {format_clp(overdue_amount)}."
            )

    return " ".join(parts)

# ==================================================
# DOCUMENTOS POR COBRAR — EJECUCIÓN
# ==================================================


def build_receivable_documents_execute_response(
    execution_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta EXECUTE para RECEIVABLE_DOCUMENTS.

    En esta primera versión la ejecución puede quedar:

    - blocked:
        falta alguna precondición;

    - prepared:
        el correo está preparado y requiere aprobación;

    - executed:
        reservado para la futura ejecución real.
    """

    status = execution_result.get(
        "status"
    )

    block_reason = execution_result.get(
        "blockReason"
    )

    facts = execution_result.get(
        "facts",
        {},
    )

    if not isinstance(facts, Mapping):
        facts = {}

    # --------------------------------------------------
    # BLOCKED
    # --------------------------------------------------

    if status == "blocked":
        recipient = facts.get(
            "recipient",
            {},
        )

        if not isinstance(
            recipient,
            Mapping,
        ):
            recipient = {}

        priority_customer = facts.get(
            "priorityCustomer",
            {},
        )

        if not isinstance(
            priority_customer,
            Mapping,
        ):
            priority_customer = {}

        customer_name = (
            recipient.get("companyName")
            or priority_customer.get(
                "customerName"
            )
            or priority_customer.get(
                "customerRut"
            )
            or "el cliente priorizado"
        )

        if (
            block_reason
            == "missing_recipient_email"
        ):
            return (
                f"No puedo preparar el envío porque "
                f"{customer_name} no tiene un correo "
                f"de contacto registrado en Luca. "
                f"Te sugiero completar el contacto "
                f"comercial o financiero de esta empresa "
                f"antes de continuar."
            )

        if (
            block_reason
            == "missing_company_id"
        ):
            return (
                f"Identifiqué a {customer_name} como "
                f"cliente prioritario, pero no pude resolver "
                f"su registro de empresa en Luca. "
                f"Es necesario revisar los datos del cliente "
                f"antes de continuar."
            )

        if (
            block_reason
            == "missing_priority_customer"
        ):
            return (
                "No pude identificar un cliente prioritario "
                "con evidencia suficiente para preparar "
                "una acción de cobranza."
            )

        if (
            block_reason
            == "missing_receivable_documents"
        ):
            return (
                f"Identifiqué a {customer_name}, pero no "
                f"encontré documentos pendientes asociados "
                f"que permitan preparar el correo de cobranza."
            )

        if (
            block_reason
            == "missing_sender_email"
        ):
            return (
                "No puedo preparar el correo porque el "
                "usuario autenticado no tiene una dirección "
                "de correo válida registrada en Luca."
            )

        if block_reason == "inactive_sender":
            return (
                "No puedo preparar el envío porque el "
                "usuario autenticado de Luca no está activo."
            )

        if (
            block_reason
            == "subscription_expired"
        ):
            return (
                "No puedo preparar el envío porque la "
                "suscripción asociada al usuario de Luca "
                "se encuentra vencida."
            )

        if (
            block_reason
            == "missing_access_token"
        ):
            return (
                "No pude validar la sesión de Luca necesaria "
                "para preparar la acción de cobranza."
            )

        return (
            "No pude preparar el correo de cobranza "
            "porque falta una condición necesaria "
            "para ejecutar la acción."
        )

    # --------------------------------------------------
    # PREPARED
    # --------------------------------------------------

    if status == "prepared":
        execution = _get_execution(
            execution_result
        )

        draft = execution.get(
            "draft",
            {},
        )

        if not isinstance(
            draft,
            Mapping,
        ):
            draft = {}

        sender = draft.get(
            "from",
            {},
        )

        recipient = draft.get(
            "to",
            {},
        )

        if not isinstance(
            sender,
            Mapping,
        ):
            sender = {}

        if not isinstance(
            recipient,
            Mapping,
        ):
            recipient = {}

        sender_name = (
            sender.get("name")
            or sender.get("email")
            or "usuario autenticado"
        )

        sender_email = sender.get(
            "email"
        )

        recipient_name = (
            recipient.get("name")
            or recipient.get("email")
            or "cliente"
        )

        recipient_email = recipient.get(
            "email"
        )

        subject = (
            draft.get("subject")
            or "Documentos pendientes de pago"
        )

        body = (
            draft.get("body")
            or ""
        )

        documents_count = _safe_int(
            draft.get(
                "documentsCount"
            )
        )

        total_amount = _safe_float(
            draft.get(
                "totalAmount"
            )
        )

        sender_text = sender_name

        if sender_email:
            sender_text = (
                f"{sender_name} <{sender_email}>"
            )

        recipient_text = recipient_name

        if recipient_email:
            recipient_text = (
                f"{recipient_name} "
                f"<{recipient_email}>"
            )

        return (
            f"Preparé un correo de cobranza para "
            f"{recipient_text}, desde {sender_text}, "
            f"por {format_clp(total_amount)} "
            f"correspondientes a "
            f"{format_number(documents_count)} "
            f"documentos pendientes. "
            f"Asunto: “{subject}”. "
            f"El mensaje quedó preparado para tu revisión "
            f"y todavía no ha sido enviado.\n\n"
            f"{body}"
        )

    # --------------------------------------------------
    # EXECUTED — FUTURO
    # --------------------------------------------------

    if status == "executed":
        return (
            "El correo de cobranza fue enviado "
            "correctamente."
        )

    return (
        "La acción de cobranza fue procesada, "
        "pero no pude determinar su estado final."
    )

# ==================================================
# NOTAS DE CRÉDITO
# ==================================================


def build_credit_notes_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para CREDIT_NOTES.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré notas de crédito"
            f"{period}."
        )

    note_word = _singular_or_plural(
        documents_count,
        singular="nota de crédito",
        plural="notas de crédito",
    )

    return (
        f"Encontré "
        f"{format_number(documents_count)} "
        f"{note_word}{period}, por un monto total de "
        f"{format_clp(total_amount)}."
    )


# ==================================================
# DOCUMENTOS ANULADOS
# ==================================================


def build_cancelled_documents_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta para CANCELLED_DOCUMENTS.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré documentos anulados"
            f"{period}."
        )

    document_word = _singular_or_plural(
        documents_count,
        singular="documento anulado",
        plural="documentos anulados",
    )

    return (
        f"Encontré "
        f"{format_number(documents_count)} "
        f"{document_word}{period}, por un monto total de "
        f"{format_clp(total_amount)}."
    )

# ==================================================
# VENTAS MENSUALES — CONSULTA
# ==================================================


def build_monthly_sales_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta QUERY para MONTHLY_SALES.
    """

    result = _get_result(
        query_result
    )

    filters = _get_filters(
        query_result
    )

    period = format_period(
        year=filters.get("year"),
        month=filters.get("month"),
    )

    documents_count = _safe_int(
        result.get("documentsCount")
    )

    total_amount = _safe_float(
        result.get("totalAmount")
    )

    if documents_count == 0:
        return (
            f"No encontré ventas"
            f"{period}."
        )

    document_word = _singular_or_plural(
        documents_count,
        singular="documento",
        plural="documentos",
    )

    return (
        f"Vendiste {format_clp(total_amount)}"
        f"{period}, distribuidos en "
        f"{format_number(documents_count)} "
        f"{document_word}."
    )

# ==================================================
# VENTAS MENSUALES — EXPLICACIÓN
# ==================================================


def build_monthly_sales_explanation_response(
    execution_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta EXPLAIN para MONTHLY_SALES.
    """

    analysis = _get_analysis(
        execution_result
    )

    period_data = execution_result.get(
        "period",
        {},
    )

    comparison_period_data = execution_result.get(
        "comparisonPeriod",
        {},
    )

    current_amount = _safe_float(
        analysis.get("currentAmount")
    )

    previous_amount = _safe_float(
        analysis.get("previousAmount")
    )

    variation_amount = _safe_float(
        analysis.get("variationAmount")
    )

    variation_pct = analysis.get(
        "variationPct"
    )

    current_period = format_period(
        year=period_data.get("year"),
        month=period_data.get("month"),
    ).replace(" durante ", "")

    previous_period = format_period(
        year=comparison_period_data.get("year"),
        month=comparison_period_data.get("month"),
    ).replace(" durante ", "")

    if variation_amount > 0:
        direction = "aumentaron"
    elif variation_amount < 0:
        direction = "disminuyeron"
    else:
        direction = "se mantuvieron sin variación"

    if variation_amount == 0:
        return (
            f"Las ventas de {current_period} "
            f"se mantuvieron en {format_clp(current_amount)}, "
            f"sin variación respecto de {previous_period}."
        )

    percentage_text = ""

    if variation_pct is not None:
        percentage_text = (
            f", equivalente a "
            f"{abs(_safe_float(variation_pct)):.1f}%"
        )

    return (
        f"Las ventas de {current_period} {direction} "
        f"{format_clp(abs(variation_amount))}"
        f"{percentage_text} respecto de {previous_period}. "
        f"Pasaron de {format_clp(previous_amount)} "
        f"a {format_clp(current_amount)}."
    )

# ==================================================
# TENDENCIA DE VENTAS — CONSULTA
# ==================================================


def build_sales_trend_response(
    query_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta QUERY para SALES_TREND.
    """

    result = _get_result(
        query_result
    )

    periods = result.get(
        "periods",
        [],
    )

    if not isinstance(periods, list) or not periods:
        return (
            "No encontré información suficiente "
            "para construir la tendencia de ventas."
        )

    if len(periods) == 1:
        period = periods[0]

        period_text = format_period(
            year=period.get("year"),
            month=period.get("month"),
        ).replace(" durante ", "")

        return (
            f"Solo encontré información para {period_text}, "
            f"con ventas por "
            f"{format_clp(period.get('totalAmount'))}."
        )

    parts: list[str] = []

    for period in periods:
        period_text = format_period(
            year=period.get("year"),
            month=period.get("month"),
        ).replace(" durante ", "")

        parts.append(
            f"{period_text}: "
            f"{format_clp(period.get('totalAmount'))}"
        )

    return (
        "La evolución mensual de tus ventas es: "
        + "; ".join(parts)
        + "."
    )

# ==================================================
# TENDENCIA DE VENTAS — EXPLICACIÓN
# ==================================================


def build_sales_trend_explanation_response(
    execution_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta EXPLAIN para SALES_TREND.
    """

    analysis = _get_analysis(
        execution_result
    )

    periods_count = _safe_int(
        analysis.get("periodsCount")
    )

    if periods_count == 0:
        return (
            "No encontré información suficiente "
            "para explicar la tendencia de ventas."
        )

    if periods_count == 1:
        return (
            "Solo existe un período disponible, "
            "por lo que todavía no es posible "
            "analizar una tendencia."
        )

    direction = analysis.get(
        "direction"
    )

    first_amount = _safe_float(
        analysis.get("firstAmount")
    )

    last_amount = _safe_float(
        analysis.get("lastAmount")
    )

    total_variation_amount = _safe_float(
        analysis.get("totalVariationAmount")
    )

    total_variation_pct = analysis.get(
        "totalVariationPct"
    )

    largest_increase = analysis.get(
        "largestIncrease"
    )

    largest_drop = analysis.get(
        "largestDrop"
    )

    if direction == "up":
        direction_text = "muestra una tendencia general al alza"
    elif direction == "down":
        direction_text = "muestra una tendencia general a la baja"
    else:
        direction_text = "se mantiene prácticamente estable"

    percentage_text = ""

    if total_variation_pct is not None:
        percentage_text = (
            f", equivalente a "
            f"{abs(_safe_float(total_variation_pct)):.1f}%"
        )

    parts = [
        (
            f"La serie {direction_text}. "
            f"Las ventas pasaron de "
            f"{format_clp(first_amount)} "
            f"a {format_clp(last_amount)}, "
            f"con una variación total de "
            f"{format_clp(abs(total_variation_amount))}"
            f"{percentage_text}."
        )
    ]

    if isinstance(largest_increase, Mapping):
        from_period = largest_increase.get(
            "from",
            {},
        )

        to_period = largest_increase.get(
            "to",
            {},
        )

        increase_from = format_period(
            year=from_period.get("year"),
            month=from_period.get("month"),
        ).replace(" durante ", "")

        increase_to = format_period(
            year=to_period.get("year"),
            month=to_period.get("month"),
        ).replace(" durante ", "")

        parts.append(
            f"El mayor aumento ocurrió entre "
            f"{increase_from} y {increase_to}, "
            f"con un incremento de "
            f"{format_clp(largest_increase.get('variationAmount'))}."
        )

    if isinstance(largest_drop, Mapping):
        from_period = largest_drop.get(
            "from",
            {},
        )

        to_period = largest_drop.get(
            "to",
            {},
        )

        drop_from = format_period(
            year=from_period.get("year"),
            month=from_period.get("month"),
        ).replace(" durante ", "")

        drop_to = format_period(
            year=to_period.get("year"),
            month=to_period.get("month"),
        ).replace(" durante ", "")

        parts.append(
            f"La mayor caída ocurrió entre "
            f"{drop_from} y {drop_to}, "
            f"con una disminución de "
            f"{format_clp(abs(_safe_float(largest_drop.get('variationAmount'))))}."
        )

    return " ".join(parts)

# ==================================================
# TENDENCIA DE VENTAS — PROPUESTA
# ==================================================


def build_sales_trend_proposal_response(
    execution_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta PROPOSE para SALES_TREND.
    """

    proposal = _get_proposal(
        execution_result
    )

    proposals_count = _safe_int(
        proposal.get("proposalsCount")
    )

    primary_proposal = proposal.get(
        "primaryProposal"
    )

    if (
        proposals_count == 0
        or not isinstance(
            primary_proposal,
            Mapping,
        )
    ):
        return (
            "No encontré evidencia suficiente para "
            "proponer una acción comercial concreta."
        )

    proposal_type = primary_proposal.get(
        "proposalType"
    )

    # --------------------------------------------------
    # Recuperación de cliente clave
    # --------------------------------------------------

    if proposal_type == "recover_key_customer":
        target = primary_proposal.get(
            "target",
            {},
        )

        evidence = primary_proposal.get(
            "evidence",
            {},
        )

        customer_name = (
            target.get("customerName")
            or target.get("customerRut")
            or "este cliente"
        )

        contribution_pct = _safe_float(
            evidence.get(
                "contributionToDropPct"
            )
        )

        sales_drop = _safe_float(
            evidence.get(
                "salesDrop"
            )
        )

        return (
            f"{customer_name} explica aproximadamente "
            f"el {contribution_pct:.1f}% de la caída, "
            f"con una disminución de "
            f"{format_clp(sales_drop)} en ventas. "
            f"Te sugiero priorizar el contacto con este cliente "
            f"para entender la reducción y evaluar una "
            f"oportunidad de recuperación."
        )

    # --------------------------------------------------
    # Caída sin cliente dominante
    # --------------------------------------------------

    if proposal_type == "review_sales_drop":
        evidence = primary_proposal.get(
            "evidence",
            {},
        )

        sales_drop = _safe_float(
            evidence.get(
                "salesDrop"
            )
        )

        return (
            f"Se identificó una caída de "
            f"{format_clp(sales_drop)} en ventas, "
            f"pero no existe un cliente dominante que la explique. "
            f"Te sugiero revisar los principales cambios por cliente "
            f"para identificar oportunidades de recuperación."
        )

    # --------------------------------------------------
    # Tendencia positiva
    # --------------------------------------------------

    if proposal_type == "reinforce_growth":
        evidence = primary_proposal.get(
            "evidence",
            {},
        )

        variation_pct = evidence.get(
            "totalVariationPct"
        )

        percentage_text = ""

        if variation_pct is not None:
            percentage_text = (
                f" ({_safe_float(variation_pct):.1f}%)"
            )

        return (
            f"La tendencia general es positiva"
            f"{percentage_text}. "
            f"Te sugiero identificar qué clientes o períodos "
            f"están impulsando el crecimiento para reforzar "
            f"esas oportunidades."
        )

    # --------------------------------------------------
    # Tendencia estable
    # --------------------------------------------------

    if proposal_type == "review_growth_opportunities":
        return (
            "Las ventas se mantienen relativamente estables. "
            "Te sugiero revisar oportunidades de crecimiento, "
            "especialmente entre clientes con menor actividad "
            "o menor recurrencia de compra."
        )

    return (
        "Identifiqué una posible acción comercial, "
        "pero todavía no tengo una forma específica "
        "de presentarla."
    )

# ==================================================
# REGISTRO DE CONSTRUCTORES
# ==================================================


RESPONSE_BUILDERS: dict[
    tuple[SalesOperation, SalesIntent],
    ResponseBuilderHandler,
] = {
    (
        SalesOperation.QUERY,
        SalesIntent.SALES_OVERVIEW,
    ): build_sales_overview_response,

    (
        SalesOperation.QUERY,
        SalesIntent.TOTAL_DOCUMENTS,
    ): build_total_documents_response,

    (
        SalesOperation.QUERY,
        SalesIntent.TOTAL_RECEIVABLE,
    ): build_total_receivable_response,
    
        (
        SalesOperation.QUERY,
        SalesIntent.RECEIVABLE_DOCUMENTS,
    ): build_receivable_documents_response,

    (
        SalesOperation.EXPLAIN,
        SalesIntent.RECEIVABLE_DOCUMENTS,
    ): build_receivable_documents_explanation_response,

    (
        SalesOperation.PROPOSE,
        SalesIntent.RECEIVABLE_DOCUMENTS,
    ): build_receivable_documents_proposal_response,
    
    (
        SalesOperation.EXECUTE,
        SalesIntent.RECEIVABLE_DOCUMENTS,
    ): build_receivable_documents_execute_response,

    (
        SalesOperation.QUERY,
        SalesIntent.CREDIT_NOTES,
    ): build_credit_notes_response,

    (
        SalesOperation.QUERY,
        SalesIntent.CANCELLED_DOCUMENTS,
    ): build_cancelled_documents_response,

    (
        SalesOperation.QUERY,
        SalesIntent.MONTHLY_SALES,
    ): build_monthly_sales_response,

    (
        SalesOperation.EXPLAIN,
        SalesIntent.MONTHLY_SALES,
    ): build_monthly_sales_explanation_response,
    
    (
    SalesOperation.QUERY,
        SalesIntent.SALES_TREND,
    ): build_sales_trend_response,

    (
        SalesOperation.EXPLAIN,
        SalesIntent.SALES_TREND,
    ): build_sales_trend_explanation_response,
    
    (
        SalesOperation.PROPOSE,
        SalesIntent.SALES_TREND,
    ): build_sales_trend_proposal_response,
}


# ==================================================
# CONSTRUCTOR PRINCIPAL
# ==================================================


class SalesResponseBuilder:
    """
    Constructor determinista de respuestas comerciales.
    """

    def __init__(
        self,
        *,
        builders: Mapping[
            tuple[SalesOperation, SalesIntent],
            ResponseBuilderHandler,
        ] | None = None,
    ) -> None:
        """
        Permite inyectar constructores durante pruebas.
        """

        self._builders = dict(
            builders or RESPONSE_BUILDERS
        )

    def supports(
        self,
        intent: SalesIntent,
        operation: SalesOperation = SalesOperation.QUERY,
    ) -> bool:
        """
        Indica si existe un constructor para intención y operación.
        """

        _validate_intent(intent)
        _validate_operation(operation)

        return (
            operation,
            intent,
        ) in self._builders

    def build(
        self,
        *,
        intent: SalesIntent,
        operation: SalesOperation,
        execution_result: Mapping[str, Any],
    ) -> SalesResponseBuildResult:
        """
        Construye una respuesta natural para una intención y operación.
        """

        _validate_intent(intent)
        _validate_operation(operation)

        _validate_execution_result(
            execution_result,
            operation,
        )

        builder = self._builders.get(
            (
                operation,
                intent,
            )
        )

        if builder is None:
            raise NotImplementedError(
                "No existe un constructor de respuesta "
                f"para {operation.value}:{intent.value}"
            )

        answer = builder(
            execution_result
        )

        if not isinstance(answer, str):
            raise TypeError(
                "El constructor debe retornar un string."
            )

        normalized_answer = answer.strip()

        if not normalized_answer:
            raise ValueError(
                "El constructor generó una respuesta vacía."
            )

        return SalesResponseBuildResult(
            answer=normalized_answer,
            intent=intent.value,
            operation=operation.value,
            builder=builder.__name__,
            deterministic=True,
        )


# ==================================================
# INTERFAZ PÚBLICA
# ==================================================


_default_builder = SalesResponseBuilder()

def build_sales_response(
    *,
    intent: SalesIntent,
    operation: SalesOperation,
    execution_result: Mapping[str, Any],
) -> str:

    result = _default_builder.build(
        intent=intent,
        operation=operation,
        execution_result=execution_result,
    )

    return result.answer

def build_sales_response_result(
    *,
    intent: SalesIntent,
    operation: SalesOperation,
    execution_result: Mapping[str, Any],
) -> SalesResponseBuildResult:
    return _default_builder.build(
        intent=intent,
        operation=operation,
        execution_result=execution_result,
    )

# ==================================================
# PRUEBA MANUAL
# ==================================================


def main() -> None:
    """
    Prueba manual sin Mongo ni FastAPI.
    """

    examples: tuple[
        tuple[
            SalesIntent,
            dict[str, Any],
        ],
        ...,
    ] = (
        (
            SalesIntent.TOTAL_RECEIVABLE,
            {
                "queryType": "total_receivable",
                "businessId": 5,
                "filters": {
                    "year": 2026,
                    "month": 1,
                    "status": "POR COBRAR",
                },
                "result": {
                    "documentsCount": 18,
                    "totalAmount": 12_450_000,
                },
            },
        ),
        (
            SalesIntent.CREDIT_NOTES,
            {
                "queryType": "credit_notes",
                "businessId": 5,
                "filters": {
                    "year": None,
                    "month": None,
                    "documentCode": 61,
                    "limit": 10,
                },
                "result": {
                    "documentsCount": 3,
                    "totalAmount": 825_500,
                    "documents": [],
                },
            },
        ),
        (
            SalesIntent.CANCELLED_DOCUMENTS,
            {
                "queryType": "cancelled_documents",
                "businessId": 5,
                "filters": {
                    "year": None,
                    "month": None,
                    "limit": 10,
                },
                "result": {
                    "documentsCount": 0,
                    "totalAmount": 0,
                    "documents": [],
                },
            },
        ),
        (
            SalesIntent.SALES_OVERVIEW,
            {
                "queryType": "sales_overview",
                "businessId": 5,
                "filters": {
                    "year": 2026,
                    "month": None,
                },
                "result": {
                    "totalDocuments": 120,
                    "totalAmount": 98_700_000,
                    "receivableDocuments": 18,
                    "receivableAmount": 12_450_000,
                    "uniqueCustomers": 34,
                    "creditNotes": 3,
                    "cancelledDocuments": 2,
                    "linkedDocuments": 15,
                },
            },
        ),
    )

    print()
    print("=" * 88)
    print("PRUEBA SALES RESPONSE BUILDER")
    print("=" * 88)

    for intent, query_result in examples:
        result = build_sales_response_result(
            intent=intent,
            operation=SalesOperation.QUERY,
            execution_result=query_result,
        )

        print()
        print(f"Intent  : {result.intent}")
        print(f"Builder : {result.builder}")
        print(f"Answer  : {result.answer}")


if __name__ == "__main__":
    main()