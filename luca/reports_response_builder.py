# luca/reports_response_builder.py

"""
Construcción determinista de respuestas para el agente de reportes.

Responsabilidad:

    ReportsQueryResult
        ↓
    interpretación estructural
        ↓
    respuesta humana

Este módulo:

- NO consulta MongoDB.
- NO consulta Luca API.
- NO recalcula el reporte.
- NO utiliza LLM.

Los cálculos contables pertenecen a reports_query_service.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


from luca.reports_intents import (
    ReportsIntent,
)

from luca.reports_query_service import (
    ReportsQueryResult,
)


# ==================================================
# TIPOS
# ==================================================


@dataclass(
    frozen=True,
    slots=True,
)
class ReportsResponseBuildResult:
    """
    Resultado de la construcción de una respuesta
    humana para el agente de reportes.
    """

    answer: str
    intent: str
    builder: str
    deterministic: bool = True

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "intent": self.intent,
            "builder": self.builder,
            "deterministic": (
                self.deterministic
            ),
        }


ReportsResponseBuilder = Callable[
    [ReportsQueryResult],
    ReportsResponseBuildResult,
]


# ==================================================
# UTILIDADES
# ==================================================


def _as_number(
    value: Any,
) -> float | int:
    """
    Convierte un valor a número seguro
    exclusivamente para presentación.
    """

    if value is None:
        return 0

    if isinstance(
        value,
        bool,
    ):
        return 0

    if isinstance(
        value,
        int,
    ):
        return value

    if isinstance(
        value,
        float,
    ):
        return value

    try:
        numeric = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0

    if numeric.is_integer():
        return int(
            numeric
        )

    return numeric


def _format_amount(
    value: Any,
) -> str:
    """
    Formatea montos utilizando separador de miles
    compatible con presentación chilena.

    Ejemplo:

        218436873 -> $218.436.873
    """

    number = _as_number(
        value
    )

    if isinstance(
        number,
        float,
    ) and not number.is_integer():
        formatted = (
            f"{number:,.2f}"
            .replace(",", "_")
            .replace(".", ",")
            .replace("_", ".")
        )

        return f"${formatted}"

    integer_value = int(
        number
    )

    formatted = (
        f"{integer_value:,}"
        .replace(",", ".")
    )

    return f"${formatted}"


def _format_date(
    value: str | None,
) -> str:
    """
    Convierte YYYY-MM-DD a DD-MM-YYYY
    para presentación.

    Si el valor no tiene el formato esperado,
    se conserva sin modificar.
    """

    if not value:
        return ""

    parts = value.split(
        "-"
    )

    if len(parts) != 3:
        return value

    year, month, day = parts

    if not (
        len(year) == 4
        and len(month) == 2
        and len(day) == 2
    ):
        return value

    return (
        f"{day}-{month}-{year}"
    )


def _safe_dict(
    value: Any,
) -> dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def _safe_list(
    value: Any,
) -> list[dict[str, Any]]:
    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        item
        for item in value
        if isinstance(
            item,
            dict,
        )
    ]


def _account_label(
    account: dict[str, Any],
) -> str:
    """
    Construye una etiqueta legible para una cuenta.
    """

    name = account.get(
        "nameCuenta"
    )

    number = account.get(
        "numCuenta"
    )

    if name:
        return str(
            name
        )

    if number:
        return (
            f"Cuenta {number}"
        )

    return "Cuenta sin nombre"


def _format_account_ranking(
    accounts: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> str:
    """
    Convierte un ranking de cuentas a una frase compacta.

    Ejemplo:

        Cargos por Aclarar ($206.061.221),
        Clientes Ventas ($134.118.961) y
        Banco Estado CLP ($16.960.476)
    """

    if not accounts:
        return ""

    selected = accounts[
        :limit
    ]

    labels = [
        (
            f"{_account_label(account)} "
            f"({_format_amount(account.get('amount'))})"
        )
        for account in selected
    ]

    if len(labels) == 1:
        return labels[0]

    if len(labels) == 2:
        return (
            f"{labels[0]} y {labels[1]}"
        )

    return (
        ", ".join(
            labels[:-1]
        )
        + f" y {labels[-1]}"
    )


# ==================================================
# EXTRACCIÓN DEL ANÁLISIS
# ==================================================


def _get_general_balance_analysis(
    query_result: ReportsQueryResult,
) -> dict[str, Any]:
    """
    Obtiene el análisis determinista generado
    por reports_query_service.py.
    """

    if not isinstance(
        query_result.data,
        dict,
    ):
        raise ValueError(
            "El resultado del Balance General "
            "no contiene data válida."
        )

    analysis = query_result.data.get(
        "analysis"
    )

    if not isinstance(
        analysis,
        dict,
    ):
        raise ValueError(
            "El resultado del Balance General "
            "no contiene analysis válido."
        )

    return analysis


# ==================================================
# BUILDER — BALANCE GENERAL
# ==================================================


def build_general_balance_response(
    query_result: ReportsQueryResult,
) -> ReportsResponseBuildResult:
    """
    Construye una respuesta ejecutiva y determinista
    para el Balance General.

    Para la lectura económica se utilizan los
    subtotales previos a la fila Resultado:

        - activo
        - pasivo
        - pérdida
        - ganancia

    El resultado del período se obtiene desde el
    cálculo determinista realizado por
    reports_query_service.py.

    Los totales finales se utilizan únicamente para
    informar si el reporte queda balanceado después
    de la fila Resultado.
    """

    analysis = (
        _get_general_balance_analysis(
            query_result
        )
    )

    reported = _safe_dict(
        analysis.get(
            "reported"
        )
    )

    subtotal = _safe_dict(
        reported.get(
            "subtotal"
        )
    )

    calculated = _safe_dict(
        analysis.get(
            "calculated"
        )
    )

    preclosing_difference = (
        _safe_dict(
            calculated.get(
                "preclosingDifference"
            )
        )
    )

    balance_checks = _safe_dict(
        analysis.get(
            "balanceChecks"
        )
    )

    top_assets = _safe_list(
        analysis.get(
            "topAssets"
        )
    )

    top_liabilities = _safe_list(
        analysis.get(
            "topLiabilities"
        )
    )

    accounts_count = int(
        _as_number(
            analysis.get(
                "accountsCount"
            )
        )
    )

    assets = _as_number(
        subtotal.get(
            "activo"
        )
    )

    liabilities = _as_number(
        subtotal.get(
            "pasivo"
        )
    )

    gains = _as_number(
        subtotal.get(
            "ganancia"
        )
    )

    losses = _as_number(
        subtotal.get(
            "perdida"
        )
    )

    period_result = _as_number(
        calculated.get(
            "periodResult"
        )
    )

    debit_credit_difference = (
        _as_number(
            preclosing_difference.get(
                "debitMinusCredit"
            )
        )
    )

    debtor_creditor_difference = (
        _as_number(
            preclosing_difference.get(
                "debtorMinusCreditor"
            )
        )
    )

    all_balance_checks_pass = (
        bool(balance_checks)
        and all(
            bool(value)
            for value
            in balance_checks.values()
        )
    )

    period_from = _format_date(
        query_result.query_from
    )

    period_to = _format_date(
        query_result.query_to
    )

    if (
        period_from
        and period_to
    ):
        period_text = (
            f"para el período entre "
            f"{period_from} y {period_to}"
        )

    elif period_to:
        period_text = (
            f"al {period_to}"
        )

    else:
        period_text = (
            "para el período disponible"
        )

    if period_result > 0:
        result_text = (
            "El resultado del período es una "
            f"ganancia de {_format_amount(period_result)}"
        )

    elif period_result < 0:
        result_text = (
            "El resultado del período es una "
            f"pérdida de "
            f"{_format_amount(abs(period_result))}"
        )

    else:
        result_text = (
            "El resultado del período es $0"
        )

    answer_parts = [
        (
            f"El Balance General {period_text} "
            f"considera {accounts_count} cuentas."
        ),
        (
            f"Antes de incorporar el resultado del período, "
            f"presenta activos por {_format_amount(assets)} "
            f"y pasivos por {_format_amount(liabilities)}."
        ),
        (
            f"Registra ganancias por "
            f"{_format_amount(gains)} y pérdidas por "
            f"{_format_amount(losses)}. "
            f"{result_text}."
        ),
    ]

    top_assets_text = (
        _format_account_ranking(
            top_assets,
            limit=3,
        )
    )

    if top_assets_text:
        answer_parts.append(
            "Los principales activos informados "
            f"son {top_assets_text}."
        )

    top_liabilities_text = (
        _format_account_ranking(
            top_liabilities,
            limit=3,
        )
    )

    if top_liabilities_text:
        answer_parts.append(
            "Los principales pasivos informados "
            f"son {top_liabilities_text}."
        )

    if all_balance_checks_pass:
        answer_parts.append(
            "Luego de incorporar la fila Resultado, "
            "el reporte queda balanceado en sus "
            "igualdades finales."
        )
    else:
        answer_parts.append(
            "Las igualdades finales del reporte no "
            "se encuentran completamente balanceadas."
        )

    if (
        debit_credit_difference != 0
        or debtor_creditor_difference != 0
    ):
        differences = []

        if debit_credit_difference != 0:
            differences.append(
                "Debe/Haber "
                f"{_format_amount(abs(debit_credit_difference))}"
            )

        if debtor_creditor_difference != 0:
            differences.append(
                "Deudor/Acreedor "
                f"{_format_amount(abs(debtor_creditor_difference))}"
            )

        answer_parts.append(
            "Antes del cierre se observa una diferencia "
            + " y ".join(
                differences
            )
            + ", que es absorbida por la fila Resultado "
            "del reporte."
        )

    answer = " ".join(
        answer_parts
    )

    return ReportsResponseBuildResult(
        answer=answer,
        intent=(
            ReportsIntent.GENERAL_BALANCE.value
        ),
        builder=(
            "build_general_balance_response"
        ),
        deterministic=True,
    )


# ==================================================
# REGISTRO DE BUILDERS
# ==================================================


RESPONSE_BUILDERS: dict[
    ReportsIntent,
    ReportsResponseBuilder,
] = {
    ReportsIntent.GENERAL_BALANCE:
        build_general_balance_response,
}


# ==================================================
# BUILDER PÚBLICO
# ==================================================


def build_reports_response_result(
    *,
    intent: ReportsIntent,
    query_result: ReportsQueryResult,
) -> ReportsResponseBuildResult:
    """
    Resuelve y ejecuta el builder correspondiente
    a una intención de reportes.
    """

    if not isinstance(
        intent,
        ReportsIntent,
    ):
        raise TypeError(
            "intent debe ser una instancia "
            "de ReportsIntent."
        )

    if not isinstance(
        query_result,
        ReportsQueryResult,
    ):
        raise TypeError(
            "query_result debe ser una instancia "
            "de ReportsQueryResult."
        )

    builder = RESPONSE_BUILDERS.get(
        intent
    )

    if builder is None:
        raise ValueError(
            "No existe un response builder "
            f"para el intent {intent.value}."
        )

    return builder(
        query_result
    )