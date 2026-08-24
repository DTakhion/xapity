# luca/sales_analysis_service.py

from __future__ import annotations

from datetime import date
from typing import Any

from dateutil.relativedelta import relativedelta
from pymongo.collection import Collection

from luca.sales_query_service import (
    get_monthly_sales,
    get_monthly_sales_by_customer,
    get_receivable_documents,
    get_sales_trend,
)


def explain_monthly_sales(
    *,
    business_id: int,
    year: int,
    month: int,
    collection: Collection | None = None,
) -> dict[str, Any]:

    current = get_monthly_sales(
        business_id=business_id,
        year=year,
        month=month,
        collection=collection,
    )

    current_period = date(year, month, 1)

    previous_period = (
        current_period
        - relativedelta(months=1)
    )

    previous = get_monthly_sales(
        business_id=business_id,
        year=previous_period.year,
        month=previous_period.month,
        collection=collection,
    )

    current_amount = float(
        current["result"]["totalAmount"]
    )

    previous_amount = float(
        previous["result"]["totalAmount"]
    )

    variation_amount = (
        current_amount
        - previous_amount
    )

    variation_pct = None

    if previous_amount != 0:
        variation_pct = (
            variation_amount
            / previous_amount
        ) * 100

    return {
        "analysisType": "monthly_sales_explanation",
        "businessId": business_id,
        "period": {
            "year": year,
            "month": month,
        },
        "comparisonPeriod": {
            "year": previous_period.year,
            "month": previous_period.month,
        },
        "facts": {
            "current": current,
            "previous": previous,
        },
        "analysis": {
            "currentAmount": current_amount,
            "previousAmount": previous_amount,
            "variationAmount": variation_amount,
            "variationPct": variation_pct,
        },
        "metadata": {
            "deterministic": True,
        },
    }

def explain_sales_trend(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Explica determinísticamente la tendencia de ventas.

    Calcula:

    - variaciones entre períodos consecutivos;
    - dirección general de la serie;
    - mayor aumento;
    - mayor caída.
    """

    trend = get_sales_trend(
        business_id=business_id,
        year=year,
        month=month,
        collection=collection,
    )

    periods = trend["result"]["periods"]

    variations: list[dict[str, Any]] = []

    for previous, current in zip(
        periods,
        periods[1:],
    ):
        previous_amount = float(
            previous["totalAmount"]
        )

        current_amount = float(
            current["totalAmount"]
        )

        variation_amount = (
            current_amount
            - previous_amount
        )

        variation_pct = None

        if previous_amount != 0:
            variation_pct = (
                variation_amount
                / previous_amount
            ) * 100

        variations.append(
            {
                "from": {
                    "year": previous["year"],
                    "month": previous["month"],
                },
                "to": {
                    "year": current["year"],
                    "month": current["month"],
                },
                "previousAmount": previous_amount,
                "currentAmount": current_amount,
                "variationAmount": variation_amount,
                "variationPct": variation_pct,
            }
        )

    first_amount = (
        float(periods[0]["totalAmount"])
        if periods
        else 0.0
    )

    last_amount = (
        float(periods[-1]["totalAmount"])
        if periods
        else 0.0
    )

    total_variation_amount = (
        last_amount
        - first_amount
    )

    total_variation_pct = None

    if first_amount != 0:
        total_variation_pct = (
            total_variation_amount
            / first_amount
        ) * 100

    if total_variation_amount > 0:
        direction = "up"
    elif total_variation_amount < 0:
        direction = "down"
    else:
        direction = "flat"

    largest_increase = None
    largest_drop = None

    positive_variations = [
        item
        for item in variations
        if item["variationAmount"] > 0
    ]

    negative_variations = [
        item
        for item in variations
        if item["variationAmount"] < 0
    ]

    if positive_variations:
        largest_increase = max(
            positive_variations,
            key=lambda item: item[
                "variationAmount"
            ],
        )

    if negative_variations:
        largest_drop = min(
            negative_variations,
            key=lambda item: item[
                "variationAmount"
            ],
        )

    customer_drivers: list[dict[str, Any]] = []
    customer_facts: dict[str, Any] = {}

    if largest_drop is not None:
        from_period = largest_drop["from"]
        to_period = largest_drop["to"]

        previous_customers = get_monthly_sales_by_customer(
            business_id=business_id,
            year=from_period["year"],
            month=from_period["month"],
            collection=collection,
        )

        current_customers = get_monthly_sales_by_customer(
            business_id=business_id,
            year=to_period["year"],
            month=to_period["month"],
            collection=collection,
        )

        customer_facts = {
            "previous": previous_customers,
            "current": current_customers,
        }

        previous_map = {
            (
                customer.get("customerRut")
                or customer.get("customerName")
            ): customer
            for customer in previous_customers[
                "result"
            ]["customers"]
            if (
                customer.get("customerRut")
                or customer.get("customerName")
            )
        }

        current_map = {
            (
                customer.get("customerRut")
                or customer.get("customerName")
            ): customer
            for customer in current_customers[
                "result"
            ]["customers"]
            if (
                customer.get("customerRut")
                or customer.get("customerName")
            )
        }

        all_customer_keys = (
            set(previous_map)
            | set(current_map)
        )

        total_drop = abs(
            float(
                largest_drop["variationAmount"]
            )
        )

        for customer_key in all_customer_keys:
            previous_customer = previous_map.get(
                customer_key,
                {},
            )

            current_customer = current_map.get(
                customer_key,
                {},
            )

            previous_amount = float(
                previous_customer.get(
                    "totalAmount",
                    0.0,
                )
            )

            current_amount = float(
                current_customer.get(
                    "totalAmount",
                    0.0,
                )
            )

            variation_amount = (
                current_amount
                - previous_amount
            )

            if variation_amount >= 0:
                continue

            contribution_pct = None

            if total_drop > 0:
                contribution_pct = (
                    abs(variation_amount)
                    / total_drop
                ) * 100

            customer_drivers.append(
                {
                    "customerRut": (
                        current_customer.get(
                            "customerRut"
                        )
                        or previous_customer.get(
                            "customerRut"
                        )
                    ),
                    "customerName": (
                        current_customer.get(
                            "customerName"
                        )
                        or previous_customer.get(
                            "customerName"
                        )
                    ),
                    "previousAmount": (
                        previous_amount
                    ),
                    "currentAmount": (
                        current_amount
                    ),
                    "variationAmount": (
                        variation_amount
                    ),
                    "contributionPct": (
                        contribution_pct
                    ),
                }
            )

        customer_drivers.sort(
            key=lambda item: item[
                "variationAmount"
            ]
        )

    return {
        "analysisType": "sales_trend_explanation",
        "businessId": business_id,
        "filters": {
            "year": year,
            "month": month,
        },
        "facts": {
            "trend": trend,
            "customerComparison": customer_facts,
        },
        "analysis": {
            "periodsCount": len(periods),
            "direction": direction,
            "firstAmount": first_amount,
            "lastAmount": last_amount,
            "totalVariationAmount": total_variation_amount,
            "totalVariationPct": total_variation_pct,
            "variations": variations,
            "largestIncrease": largest_increase,
            "largestDrop": largest_drop,
            "customerDrivers": customer_drivers,
            "primaryCustomerDriver": (
                customer_drivers[0]
                if customer_drivers
                else None
            ),
        },
        "metadata": {
            "deterministic": True,
        },
    }

def explain_receivable_documents(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Explica determinísticamente dónde se concentra
    lo pendiente por cobrar.

    Calcula:

    - monto total pendiente;
    - concentración por cliente;
    - documentos vencidos;
    - monto vencido;
    - porcentaje del saldo vencido;
    - principal cliente deudor;
    - documento pendiente de mayor monto.
    """

    receivables = get_receivable_documents(
        business_id=business_id,
        year=year,
        month=month,
        collection=collection,
        limit=None,
    )

    result = receivables.get(
        "result",
        {},
    )

    documents = result.get(
        "documents",
        [],
    )

    if not isinstance(documents, list):
        documents = []

    total_amount = float(
        result.get(
            "totalAmount",
            0.0,
        )
    )

    # --------------------------------------------------
    # Concentración por cliente
    # --------------------------------------------------

    customer_groups: dict[
        str,
        dict[str, Any],
    ] = {}

    for document in documents:
        customer_rut = document.get(
            "customerRut"
        )

        customer_name = document.get(
            "customerName"
        )

        customer_key = (
            customer_rut
            or customer_name
            or "SIN_CLIENTE"
        )

        normalized_key = str(
            customer_key
        ).upper()

        if normalized_key not in customer_groups:
            customer_groups[normalized_key] = {
                "customerRut": customer_rut,
                "customerName": customer_name,
                "documentsCount": 0,
                "totalAmount": 0.0,
            }

        customer_groups[
            normalized_key
        ]["documentsCount"] += 1

        customer_groups[
            normalized_key
        ]["totalAmount"] += float(
            document.get(
                "amount",
                0.0,
            )
        )

    customers = list(
        customer_groups.values()
    )

    for customer in customers:
        concentration_pct = None

        if total_amount > 0:
            concentration_pct = (
                float(
                    customer[
                        "totalAmount"
                    ]
                )
                / total_amount
            ) * 100

        customer[
            "concentrationPct"
        ] = concentration_pct

    customers.sort(
        key=lambda item: item[
            "totalAmount"
        ],
        reverse=True,
    )

    primary_customer = (
        customers[0]
        if customers
        else None
    )

    # --------------------------------------------------
    # Vencimientos
    # --------------------------------------------------

    now = date.today()

    overdue_documents: list[
        dict[str, Any]
    ] = []

    for document in documents:
        due_date_raw = document.get(
            "dueDate"
        )

        if not due_date_raw:
            continue

        try:
            due_date = date.fromisoformat(
                str(due_date_raw)[:10]
            )
        except ValueError:
            continue

        if due_date >= now:
            continue

        days_overdue = (
            now
            - due_date
        ).days

        overdue_documents.append(
            {
                **document,
                "daysOverdue": days_overdue,
            }
        )

    overdue_amount = sum(
        float(
            document.get(
                "amount",
                0.0,
            )
        )
        for document in overdue_documents
    )

    overdue_pct = None

    if total_amount > 0:
        overdue_pct = (
            overdue_amount
            / total_amount
        ) * 100

    overdue_documents.sort(
        key=lambda item: (
            item.get(
                "daysOverdue",
                0,
            ),
            float(
                item.get(
                    "amount",
                    0.0,
                )
            ),
        ),
        reverse=True,
    )

    # --------------------------------------------------
    # Documento de mayor exposición
    # --------------------------------------------------

    largest_document = None

    if documents:
        largest_document = max(
            documents,
            key=lambda item: float(
                item.get(
                    "amount",
                    0.0,
                )
            ),
        )

    return {
        "analysisType": (
            "receivable_documents_explanation"
        ),
        "businessId": business_id,
        "filters": {
            "year": year,
            "month": month,
        },
        "facts": {
            "receivables": receivables,
        },
        "analysis": {
            "documentsCount": len(
                documents
            ),
            "totalAmount": total_amount,
            "customersCount": len(
                customers
            ),
            "customers": customers,
            "primaryCustomer": (
                primary_customer
            ),
            "overdueDocumentsCount": len(
                overdue_documents
            ),
            "overdueAmount": overdue_amount,
            "overduePct": overdue_pct,
            "overdueDocuments": (
                overdue_documents
            ),
            "largestDocument": (
                largest_document
            ),
        },
        "metadata": {
            "deterministic": True,
        },
    }