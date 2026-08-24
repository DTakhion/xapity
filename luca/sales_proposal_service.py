# luca/sales_proposal_service.py

from __future__ import annotations

from typing import Any

from pymongo.collection import Collection

from luca.sales_analysis_service import (
    explain_receivable_documents,
    explain_sales_trend,
)


# ==================================================
# CONSTANTES
# ==================================================


PRIMARY_DRIVER_HIGH_THRESHOLD_PCT = 40.0
PRIMARY_DRIVER_MEDIUM_THRESHOLD_PCT = 20.0
RECEIVABLE_HIGH_CONCENTRATION_PCT = 30.0
RECEIVABLE_HIGH_OVERDUE_PCT = 50.0


# ==================================================
# HELPERS
# ==================================================


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_customer_recovery_proposal(
    *,
    primary_driver: dict[str, Any],
) -> dict[str, Any]:
    """
    Construye una propuesta comercial para recuperar
    un cliente que explica una parte relevante de la caída.
    """

    contribution_pct = _safe_float(
        primary_driver.get("contributionPct")
    )

    variation_amount = _safe_float(
        primary_driver.get("variationAmount")
    )

    customer_name = (
        primary_driver.get("customerName")
        or primary_driver.get("customerRut")
        or "cliente identificado"
    )

    if (
        contribution_pct
        >= PRIMARY_DRIVER_HIGH_THRESHOLD_PCT
    ):
        priority = "high"

    elif (
        contribution_pct
        >= PRIMARY_DRIVER_MEDIUM_THRESHOLD_PCT
    ):
        priority = "medium"

    else:
        priority = "low"

    return {
        "proposalType": "recover_key_customer",
        "priority": priority,
        "target": {
            "customerRut": primary_driver.get(
                "customerRut"
            ),
            "customerName": primary_driver.get(
                "customerName"
            ),
        },
        "evidence": {
            "previousAmount": _safe_float(
                primary_driver.get(
                    "previousAmount"
                )
            ),
            "currentAmount": _safe_float(
                primary_driver.get(
                    "currentAmount"
                )
            ),
            "salesDrop": abs(
                variation_amount
            ),
            "contributionToDropPct": (
                contribution_pct
            ),
        },
        "suggestedAction": (
            "prioritize_customer_contact"
        ),
        "reason": (
            f"{customer_name} explica una parte "
            "relevante de la caída de ventas."
        ),
    }


# ==================================================
# PROPUESTA: TENDENCIA DE VENTAS
# ==================================================


def propose_sales_trend(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Genera propuestas comerciales deterministas a partir
    del análisis de la tendencia de ventas.

    Flujo:

        get_sales_trend()
            ↓
        explain_sales_trend()
            ↓
        drivers comerciales
            ↓
        propuesta estructurada

    Esta función no ejecuta ninguna acción comercial.
    Solo propone acciones justificadas por evidencia.
    """

    explanation = explain_sales_trend(
        business_id=business_id,
        year=year,
        month=month,
        collection=collection,
    )

    analysis = explanation.get(
        "analysis",
        {},
    )

    if not isinstance(analysis, dict):
        analysis = {}

    direction = analysis.get(
        "direction"
    )

    primary_driver = analysis.get(
        "primaryCustomerDriver"
    )

    largest_drop = analysis.get(
        "largestDrop"
    )

    proposals: list[dict[str, Any]] = []

    # --------------------------------------------------
    # Regla 1:
    # Existe una caída y un cliente relevante que la explica.
    # --------------------------------------------------

    if (
        direction == "down"
        and isinstance(
            primary_driver,
            dict,
        )
    ):
        proposals.append(
            _build_customer_recovery_proposal(
                primary_driver=primary_driver,
            )
        )

    # --------------------------------------------------
    # Regla 2:
    # Existe caída, pero no identificamos un driver principal.
    # --------------------------------------------------

    elif (
        direction == "down"
        and isinstance(
            largest_drop,
            dict,
        )
    ):
        proposals.append(
            {
                "proposalType": (
                    "review_sales_drop"
                ),
                "priority": "medium",
                "target": None,
                "evidence": {
                    "salesDrop": abs(
                        _safe_float(
                            largest_drop.get(
                                "variationAmount"
                            )
                        )
                    ),
                    "periodFrom": (
                        largest_drop.get(
                            "from"
                        )
                    ),
                    "periodTo": (
                        largest_drop.get(
                            "to"
                        )
                    ),
                },
                "suggestedAction": (
                    "review_customer_changes"
                ),
                "reason": (
                    "Se identificó una caída relevante "
                    "en las ventas, pero no existe un "
                    "cliente dominante que la explique."
                ),
            }
        )

    # --------------------------------------------------
    # Regla 3:
    # Tendencia positiva.
    # --------------------------------------------------

    elif direction == "up":
        proposals.append(
            {
                "proposalType": (
                    "reinforce_growth"
                ),
                "priority": "medium",
                "target": None,
                "evidence": {
                    "totalVariationAmount": (
                        _safe_float(
                            analysis.get(
                                "totalVariationAmount"
                            )
                        )
                    ),
                    "totalVariationPct": (
                        analysis.get(
                            "totalVariationPct"
                        )
                    ),
                },
                "suggestedAction": (
                    "identify_growth_drivers"
                ),
                "reason": (
                    "La tendencia general de ventas "
                    "es positiva. Conviene identificar "
                    "los factores que están impulsando "
                    "el crecimiento para reforzarlos."
                ),
            }
        )

    # --------------------------------------------------
    # Regla 4:
    # Tendencia estable.
    # --------------------------------------------------

    elif direction == "flat":
        proposals.append(
            {
                "proposalType": (
                    "review_growth_opportunities"
                ),
                "priority": "low",
                "target": None,
                "evidence": {
                    "totalVariationAmount": (
                        _safe_float(
                            analysis.get(
                                "totalVariationAmount"
                            )
                        )
                    ),
                    "totalVariationPct": (
                        analysis.get(
                            "totalVariationPct"
                        )
                    ),
                },
                "suggestedAction": (
                    "review_growth_opportunities"
                ),
                "reason": (
                    "Las ventas se mantienen estables. "
                    "Puede ser útil revisar oportunidades "
                    "para generar crecimiento."
                ),
            }
        )

    # --------------------------------------------------
    # Propuesta principal
    # --------------------------------------------------

    primary_proposal = (
        proposals[0]
        if proposals
        else None
    )

    return {
        "proposalType": (
            "sales_trend_proposal"
        ),
        "businessId": business_id,
        "filters": {
            "year": year,
            "month": month,
        },
        "facts": {
            "explanation": explanation,
        },
        "proposal": {
            "proposalsCount": len(
                proposals
            ),
            "primaryProposal": (
                primary_proposal
            ),
            "proposals": proposals,
        },
        "metadata": {
            "deterministic": True,
            "executed": False,
        },
    }

# ==================================================
# PROPUESTA: DOCUMENTOS POR COBRAR
# ==================================================


def propose_receivable_documents(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Genera propuestas deterministas para priorizar
    la cobranza de documentos pendientes.

    Consume la evidencia producida por
    ``explain_receivable_documents()``.

    Esta función no ejecuta acciones.
    Solo propone prioridades de cobranza.
    """

    explanation = explain_receivable_documents(
        business_id=business_id,
        year=year,
        month=month,
        collection=collection,
    )

    analysis = explanation.get(
        "analysis",
        {},
    )

    if not isinstance(analysis, dict):
        analysis = {}

    total_amount = _safe_float(
        analysis.get("totalAmount")
    )

    documents_count = int(
        analysis.get(
            "documentsCount",
            0,
        )
        or 0
    )

    overdue_amount = _safe_float(
        analysis.get("overdueAmount")
    )

    overdue_pct = _safe_float(
        analysis.get("overduePct")
    )

    primary_customer = analysis.get(
        "primaryCustomer"
    )

    largest_document = analysis.get(
        "largestDocument"
    )

    proposals: list[
        dict[str, Any]
    ] = []

    # --------------------------------------------------
    # Sin documentos pendientes
    # --------------------------------------------------

    if (
        documents_count == 0
        or total_amount <= 0
    ):
        return {
            "proposalType": (
                "receivable_documents_proposal"
            ),
            "businessId": business_id,
            "filters": {
                "year": year,
                "month": month,
            },
            "facts": {
                "explanation": explanation,
            },
            "proposal": {
                "proposalsCount": 0,
                "primaryProposal": None,
                "proposals": [],
            },
            "metadata": {
                "deterministic": True,
                "executed": False,
            },
        }

    # --------------------------------------------------
    # Regla 1:
    # Cliente con alta concentración del saldo.
    # --------------------------------------------------

    if isinstance(
        primary_customer,
        dict,
    ):
        concentration_pct = _safe_float(
            primary_customer.get(
                "concentrationPct"
            )
        )

        if (
            concentration_pct
            >= RECEIVABLE_HIGH_CONCENTRATION_PCT
        ):
            customer_name = (
                primary_customer.get(
                    "customerName"
                )
                or primary_customer.get(
                    "customerRut"
                )
                or "cliente identificado"
            )

            proposals.append(
                {
                    "proposalType": (
                        "prioritize_key_receivable_customer"
                    ),
                    "priority": "high",
                    "target": {
                        "customerRut": (
                            primary_customer.get(
                                "customerRut"
                            )
                        ),
                        "customerName": (
                            primary_customer.get(
                                "customerName"
                            )
                        ),
                    },
                    "evidence": {
                        "customerAmount": (
                            _safe_float(
                                primary_customer.get(
                                    "totalAmount"
                                )
                            )
                        ),
                        "documentsCount": (
                            int(
                                primary_customer.get(
                                    "documentsCount",
                                    0,
                                )
                                or 0
                            )
                        ),
                        "concentrationPct": (
                            concentration_pct
                        ),
                    },
                    "suggestedAction": (
                        "prioritize_collection_contact"
                    ),
                    "reason": (
                        f"{customer_name} concentra una "
                        "parte relevante del saldo "
                        "pendiente por cobrar."
                    ),
                }
            )

    # --------------------------------------------------
    # Regla 2:
    # Alta proporción del saldo ya vencida.
    # --------------------------------------------------

    if (
        overdue_pct
        >= RECEIVABLE_HIGH_OVERDUE_PCT
        and overdue_amount > 0
    ):
        proposals.append(
            {
                "proposalType": (
                    "prioritize_overdue_receivables"
                ),
                "priority": "high",
                "target": None,
                "evidence": {
                    "overdueAmount": (
                        overdue_amount
                    ),
                    "overduePct": (
                        overdue_pct
                    ),
                    "overdueDocumentsCount": (
                        int(
                            analysis.get(
                                "overdueDocumentsCount",
                                0,
                            )
                            or 0
                        )
                    ),
                },
                "suggestedAction": (
                    "prioritize_overdue_collection"
                ),
                "reason": (
                    "Una parte relevante del saldo "
                    "pendiente corresponde a documentos "
                    "ya vencidos."
                ),
            }
        )

    # --------------------------------------------------
    # Regla 3:
    # Documento individual de alta exposición.
    # --------------------------------------------------

    if isinstance(
        largest_document,
        dict,
    ):
        largest_amount = _safe_float(
            largest_document.get(
                "amount"
            )
        )

        largest_share_pct = 0.0

        if total_amount > 0:
            largest_share_pct = (
                largest_amount
                / total_amount
            ) * 100

        if largest_share_pct >= 20.0:
            proposals.append(
                {
                    "proposalType": (
                        "prioritize_largest_receivable"
                    ),
                    "priority": "medium",
                    "target": {
                        "customerRut": (
                            largest_document.get(
                                "customerRut"
                            )
                        ),
                        "customerName": (
                            largest_document.get(
                                "customerName"
                            )
                        ),
                        "sourceKey": (
                            largest_document.get(
                                "sourceKey"
                            )
                        ),
                    },
                    "evidence": {
                        "documentAmount": (
                            largest_amount
                        ),
                        "shareOfReceivablePct": (
                            largest_share_pct
                        ),
                        "dueDate": (
                            largest_document.get(
                                "dueDate"
                            )
                        ),
                    },
                    "suggestedAction": (
                        "prioritize_single_receivable"
                    ),
                    "reason": (
                        "Existe un documento individual "
                        "con una exposición relevante "
                        "dentro del saldo pendiente."
                    ),
                }
            )

    # --------------------------------------------------
    # Regla fallback:
    # Hay deuda pendiente, pero sin concentración fuerte.
    # --------------------------------------------------

    if not proposals:
        proposals.append(
            {
                "proposalType": (
                    "review_receivable_portfolio"
                ),
                "priority": "medium",
                "target": None,
                "evidence": {
                    "totalAmount": (
                        total_amount
                    ),
                    "documentsCount": (
                        documents_count
                    ),
                    "overdueAmount": (
                        overdue_amount
                    ),
                    "overduePct": (
                        overdue_pct
                    ),
                },
                "suggestedAction": (
                    "review_receivable_priorities"
                ),
                "reason": (
                    "Existe saldo pendiente, pero no "
                    "se observa una concentración "
                    "suficientemente fuerte como para "
                    "priorizar un único cliente."
                ),
            }
        )

    # --------------------------------------------------
    # Orden de prioridad
    # --------------------------------------------------

    priority_order = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }

    proposals.sort(
        key=lambda item: priority_order.get(
            str(
                item.get(
                    "priority",
                    "low",
                )
            ),
            99,
        )
    )

    primary_proposal = (
        proposals[0]
        if proposals
        else None
    )

    return {
        "proposalType": (
            "receivable_documents_proposal"
        ),
        "businessId": business_id,
        "filters": {
            "year": year,
            "month": month,
        },
        "facts": {
            "explanation": explanation,
        },
        "proposal": {
            "proposalsCount": len(
                proposals
            ),
            "primaryProposal": (
                primary_proposal
            ),
            "proposals": proposals,
        },
        "metadata": {
            "deterministic": True,
            "executed": False,
        },
    }