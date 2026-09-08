# luca/reports_query_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from db.mongo_persistence_luca import (
    find_latest_luca_report,
    find_luca_report,
)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

GENERAL_BALANCE_REPORT_TYPE = "general_balance"

GENERAL_BALANCE_ACCOUNT_FIELDS = (
    "debe",
    "haber",
    "deudor",
    "acreedor",
    "activo",
    "pasivo",
    "perdida",
    "ganancia",
)


# ---------------------------------------------------------------------------
# Resultado público
# ---------------------------------------------------------------------------

@dataclass(
    frozen=True,
    slots=True,
)
class ReportsQueryResult:
    """
    Resultado determinista de una consulta sobre reportes
    persistidos en Mongo.
    """

    report_type: str
    business_id: int
    query_from: str
    query_to: str
    data: dict[str, Any]
    source: str
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reportType": self.report_type,
            "businessId": self.business_id,
            "queryFrom": self.query_from,
            "queryTo": self.query_to,
            "data": self.data,
            "source": self.source,
            "trace": self.trace,
        }


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

def _validate_business_id(
    business_id: int,
) -> int:
    if isinstance(
        business_id,
        bool,
    ) or not isinstance(
        business_id,
        int,
    ):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    return business_id


def _validate_date_string(
    value: str,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} debe ser str."
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{field_name} no puede estar vacío."
        )

    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} debe tener formato YYYY-MM-DD."
        ) from exc

    return value


# ---------------------------------------------------------------------------
# Utilidades numéricas
# ---------------------------------------------------------------------------

def _as_number(
    value: Any,
) -> float | int:
    """
    Convierte un valor numérico de Luca a int/float seguro.

    Valores None o no numéricos se interpretan como cero.
    """
    if value is None:
        return 0

    if isinstance(value, bool):
        return 0

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return value

    try:
        numeric = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0

    if numeric.is_integer():
        return int(numeric)

    return numeric


def _account_amount(
    account: dict[str, Any],
    field: str,
) -> float | int:
    return _as_number(
        account.get(field)
    )


# ---------------------------------------------------------------------------
# Lectura y normalización del snapshot
# ---------------------------------------------------------------------------

def _extract_report_document(
    mongo_document: dict[str, Any],
) -> dict[str, Any]:
    report = mongo_document.get(
        "report"
    )

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError(
            "El snapshot del reporte no contiene "
            "un objeto report válido."
        )

    return report


def _extract_accounts(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    accounts = report.get(
        "accounts"
    )

    if accounts is None:
        return []

    if not isinstance(
        accounts,
        list,
    ):
        raise ValueError(
            "report.accounts debe ser una lista."
        )

    normalized_accounts: list[
        dict[str, Any]
    ] = []

    for account in accounts:
        if not isinstance(
            account,
            dict,
        ):
            continue

        normalized_accounts.append(
            account
        )

    return normalized_accounts


def _extract_summary_row(
    report: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    value = report.get(key)

    if not isinstance(
        value,
        dict,
    ):
        return {}

    return value


# ---------------------------------------------------------------------------
# Cálculos base
# ---------------------------------------------------------------------------

def _calculate_totals_from_accounts(
    accounts: list[dict[str, Any]],
) -> dict[str, float | int]:
    """
    Calcula directamente desde las cuentas las sumas principales.

    Esto constituye el motor de cálculo independiente del summary
    persistido.
    """
    totals = {
        field: 0
        for field
        in GENERAL_BALANCE_ACCOUNT_FIELDS
    }

    for account in accounts:
        for field in (
            GENERAL_BALANCE_ACCOUNT_FIELDS
        ):
            totals[field] += (
                _account_amount(
                    account,
                    field,
                )
            )

    return totals


def _calculate_period_result(
    subtotal: dict[str, Any],
    calculated_accounts: dict[
        str,
        float | int
    ],
) -> float | int:
    """
    Resultado del período:

        ganancias - pérdidas

    Se privilegia la fila Sub Totales informada por Luca.
    Si no existe, se utilizan los valores calculados desde cuentas.
    """
    if subtotal:
        gain = _as_number(
            subtotal.get("ganancia")
        )

        loss = _as_number(
            subtotal.get("perdida")
        )

    else:
        gain = calculated_accounts[
            "ganancia"
        ]

        loss = calculated_accounts[
            "perdida"
        ]

    return gain - loss


def _calculate_preclosing_difference(
    subtotal: dict[str, Any],
    calculated_accounts: dict[
        str,
        float | int
    ],
) -> dict[str, float | int]:
    """
    Calcula diferencias visibles antes de la fila Resultado.

    No las interpreta como error contable.
    Solamente expone las diferencias matemáticas del reporte.
    """
    if subtotal:
        debit = _as_number(
            subtotal.get("debe")
        )

        credit = _as_number(
            subtotal.get("haber")
        )

        debtor = _as_number(
            subtotal.get("deudor")
        )

        creditor = _as_number(
            subtotal.get("acreedor")
        )

    else:
        debit = calculated_accounts[
            "debe"
        ]

        credit = calculated_accounts[
            "haber"
        ]

        debtor = calculated_accounts[
            "deudor"
        ]

        creditor = calculated_accounts[
            "acreedor"
        ]

    return {
        "debitMinusCredit": (
            debit - credit
        ),
        "debtorMinusCreditor": (
            debtor - creditor
        ),
    }


def _calculate_balance_checks(
    totals: dict[str, Any],
) -> dict[str, bool]:
    """
    Verifica las igualdades finales del Balance General.
    """
    return {
        "debitEqualsCredit": (
            _as_number(
                totals.get("debe")
            )
            ==
            _as_number(
                totals.get("haber")
            )
        ),
        "debtorEqualsCreditor": (
            _as_number(
                totals.get("deudor")
            )
            ==
            _as_number(
                totals.get("acreedor")
            )
        ),
        "assetsEqualLiabilities": (
            _as_number(
                totals.get("activo")
            )
            ==
            _as_number(
                totals.get("pasivo")
            )
        ),
        "lossEqualsGain": (
            _as_number(
                totals.get("perdida")
            )
            ==
            _as_number(
                totals.get("ganancia")
            )
        ),
    }


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

def _top_accounts(
    accounts: list[dict[str, Any]],
    *,
    field: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Retorna las cuentas con mayor monto para un campo determinado.
    """
    if field not in (
        GENERAL_BALANCE_ACCOUNT_FIELDS
    ):
        raise ValueError(
            f"Campo contable no soportado: {field}"
        )

    if isinstance(
        limit,
        bool,
    ) or not isinstance(
        limit,
        int,
    ):
        raise TypeError(
            "limit debe ser un entero."
        )

    if limit <= 0:
        raise ValueError(
            "limit debe ser mayor que cero."
        )

    candidates = []

    for account in accounts:
        amount = _account_amount(
            account,
            field,
        )

        if amount <= 0:
            continue

        candidates.append(
            {
                "numCuenta": (
                    account.get(
                        "numCuenta"
                    )
                ),
                "nameCuenta": (
                    account.get(
                        "nameCuenta"
                    )
                ),
                "amount": amount,
            }
        )

    candidates.sort(
        key=lambda item: item["amount"],
        reverse=True,
    )

    return candidates[:limit]


# ---------------------------------------------------------------------------
# Motor determinista — Balance General
# ---------------------------------------------------------------------------

def build_general_balance_analysis(
    report: dict[str, Any],
    *,
    top_limit: int = 10,
) -> dict[str, Any]:
    """
    Construye el análisis determinista del Balance General.

    No utiliza LLM.

    Parte del reporte normalizado persistido en Mongo y calcula:

        - número de cuentas
        - totales desde cuentas
        - subtotales informados por Luca
        - resultado del período
        - diferencias previas al cierre
        - validaciones de balance final
        - principales activos
        - principales pasivos
        - principales pérdidas/gastos
        - principales ganancias/ingresos
        - principales saldos deudores
        - principales saldos acreedores
    """
    accounts = _extract_accounts(
        report
    )

    subtotal = _extract_summary_row(
        report,
        "subtotal",
    )

    reported_result = (
        _extract_summary_row(
            report,
            "result",
        )
    )

    totals = _extract_summary_row(
        report,
        "totals",
    )

    calculated_accounts = (
        _calculate_totals_from_accounts(
            accounts
        )
    )

    period_result = (
        _calculate_period_result(
            subtotal,
            calculated_accounts,
        )
    )

    preclosing_difference = (
        _calculate_preclosing_difference(
            subtotal,
            calculated_accounts,
        )
    )

    balance_checks = (
        _calculate_balance_checks(
            totals
            if totals
            else calculated_accounts
        )
    )

    return {
        "accountsCount": len(
            accounts
        ),

        "reported": {
            "subtotal": subtotal,
            "result": reported_result,
            "totals": totals,
        },

        "calculated": {
            "accountsTotals": (
                calculated_accounts
            ),
            "periodResult": (
                period_result
            ),
            "preclosingDifference": (
                preclosing_difference
            ),
        },

        "balanceChecks": (
            balance_checks
        ),

        "topAssets": _top_accounts(
            accounts,
            field="activo",
            limit=top_limit,
        ),

        "topLiabilities": _top_accounts(
            accounts,
            field="pasivo",
            limit=top_limit,
        ),

        "topLosses": _top_accounts(
            accounts,
            field="perdida",
            limit=top_limit,
        ),

        "topGains": _top_accounts(
            accounts,
            field="ganancia",
            limit=top_limit,
        ),

        "topDebtorBalances": (
            _top_accounts(
                accounts,
                field="deudor",
                limit=top_limit,
            )
        ),

        "topCreditorBalances": (
            _top_accounts(
                accounts,
                field="acreedor",
                limit=top_limit,
            )
        ),
    }


# ---------------------------------------------------------------------------
# Resolución del snapshot
# ---------------------------------------------------------------------------

def _resolve_general_balance_snapshot(
    *,
    business_id: int,
    query_from: str | None = None,
    query_to: str | None = None,
) -> dict[str, Any]:
    """
    Resuelve qué snapshot de Balance General utilizar.

    Si query_from y query_to vienen informados:
        → busca exactamente ese período.

    Si no:
        → utiliza el snapshot más reciente disponible.
    """
    business_id = (
        _validate_business_id(
            business_id
        )
    )

    if (
        query_from is None
        and query_to is None
    ):
        document = (
            find_latest_luca_report(
                business_id=business_id,
                report_type=(
                    GENERAL_BALANCE_REPORT_TYPE
                ),
            )
        )

        if document is None:
            raise LookupError(
                "No existe un Balance General "
                "sincronizado para la empresa."
            )

        return document

    if (
        query_from is None
        or query_to is None
    ):
        raise ValueError(
            "query_from y query_to deben "
            "informarse juntos."
        )

    query_from = _validate_date_string(
        query_from,
        "query_from",
    )

    query_to = _validate_date_string(
        query_to,
        "query_to",
    )

    if (
        date.fromisoformat(
            query_from
        )
        >
        date.fromisoformat(
            query_to
        )
    ):
        raise ValueError(
            "query_from no puede ser posterior "
            "a query_to."
        )

    document = find_luca_report(
        business_id=business_id,
        report_type=(
            GENERAL_BALANCE_REPORT_TYPE
        ),
        query_from=query_from,
        query_to=query_to,
    )

    if document is None:
        raise LookupError(
            "No existe un Balance General "
            "sincronizado para el período solicitado."
        )

    return document


# ---------------------------------------------------------------------------
# Consulta pública — Balance General
# ---------------------------------------------------------------------------

def query_general_balance(
    *,
    business_id: int,
    query_from: str | None = None,
    query_to: str | None = None,
    top_limit: int = 10,
) -> ReportsQueryResult:
    """
    Consulta un Balance General persistido en Mongo
    y ejecuta el motor determinista de cálculo.

    Esta función NO consulta Luca API.
    """
    business_id = (
        _validate_business_id(
            business_id
        )
    )

    document = (
        _resolve_general_balance_snapshot(
            business_id=business_id,
            query_from=query_from,
            query_to=query_to,
        )
    )

    report = _extract_report_document(
        document
    )

    analysis = (
        build_general_balance_analysis(
            report,
            top_limit=top_limit,
        )
    )

    stored_summary = (
        document.get("summary")
        if isinstance(
            document.get("summary"),
            dict,
        )
        else {}
    )

    resolved_query_from = str(
        document.get(
            "queryFrom",
            "",
        )
    )

    resolved_query_to = str(
        document.get(
            "queryTo",
            "",
        )
    )

    data = {
        "analysis": analysis,
        "storedSummary": stored_summary,
    }

    trace = {
        "reportType": (
            GENERAL_BALANCE_REPORT_TYPE
        ),
        "source": "mongodb",
        "collection": "luca_reports",
        "mongoId": (
            str(document["_id"])
            if document.get("_id")
            is not None
            else None
        ),
        "version": (
            document.get(
                "version"
            )
        ),
        "contentHash": (
            document.get(
                "contentHash"
            )
        ),
        "queryFrom": (
            resolved_query_from
        ),
        "queryTo": (
            resolved_query_to
        ),
        "loadedAt": (
            (
                document.get(
                    "metadata"
                )
                or {}
            ).get(
                "loadedAt"
            )
            if isinstance(
                document.get(
                    "metadata"
                ),
                dict,
            )
            else None
        ),
        "deterministic": True,
    }

    return ReportsQueryResult(
        report_type=(
            GENERAL_BALANCE_REPORT_TYPE
        ),
        business_id=business_id,
        query_from=(
            resolved_query_from
        ),
        query_to=(
            resolved_query_to
        ),
        data=data,
        source="mongodb",
        trace=trace,
    )