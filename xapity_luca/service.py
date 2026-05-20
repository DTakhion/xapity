# xapity_luca/service.py

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from luca.analytics.sales_summary import summarize_sales_from_mongo
from luca.reports.sales_excel import generate_sales_excel
from luca.services.luca_movements import get_luca_sales_summary
from schemas.xapity_luca import (
    XapityLucaRequest,
    XapityLucaResponse,
)
from xapity_luca.intent import analyze_xapity_luca_intent


load_dotenv()


MONTH_NAMES = {
    0: "todos los meses",
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


def get_default_business_id() -> int:
    business_id_env = os.getenv("LUCA_BUSINESS_ID")

    if not business_id_env:
        raise RuntimeError("Falta variable LUCA_BUSINESS_ID en .env")

    return int(business_id_env)


def money(value: Any) -> str:
    amount = float(value or 0)

    return f"${amount:,.0f}".replace(",", ".")


def ensure_snapshot_exists(
    business_id: int,
    month: int,
    year: int,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """
    Asegura que exista snapshot en Mongo.
    Si ya existe y el mes está cerrado, get_luca_sales_summary usará cache.
    """

    return get_luca_sales_summary(
        business_id=business_id,
        month=month,
        year=year,
        type_="ingreso",
        max_results=500,
        page=0,
        linkage=True,
        use_cache=True,
        force_refresh=False,
        requested_by=requested_by,
    )


def build_sales_summary_message(
    summary: dict[str, Any],
) -> str:
    resumen = summary.get("resumen", {})
    top_clientes = summary.get("topClientes", [])

    month = summary.get("month")
    year = summary.get("year")
    month_name = MONTH_NAMES.get(month, str(month))

    lines = [
        f"Para {month_name} de {year}, registras {resumen.get('totalDocumentos', 0)} documentos de venta.",
        f"El monto total de ventas es {money(resumen.get('montoTotalVentas'))}.",
        f"El monto cobrado es {money(resumen.get('montoCobrado'))}.",
        f"El monto pendiente es {money(resumen.get('montoPendiente'))}.",
        f"El monto pendiente vencido es {money(resumen.get('montoPendienteVencido'))}.",
    ]

    if top_clientes:
        lines.append("")
        lines.append("Top 3 clientes por monto vendido:")

        for index, cliente in enumerate(top_clientes, start=1):
            lines.append(
                f"{index}. {cliente.get('razonSocial')} "
                f"({cliente.get('rut')}): {money(cliente.get('montoTotal'))}"
            )

    return "\n".join(lines)


def build_pending_payments_message(
    summary: dict[str, Any],
) -> str:
    resumen = summary.get("resumen", {})

    month = summary.get("month")
    year = summary.get("year")
    month_name = MONTH_NAMES.get(month, str(month))

    cantidad_pendientes = resumen.get("cantidadPendientes", 0)
    cantidad_pendientes_vencidos = resumen.get("cantidadPendientesVencidos", 0)

    monto_pendiente = resumen.get("montoPendiente", 0)
    monto_pendiente_vencido = resumen.get("montoPendienteVencido", 0)

    return (
        f"Para {month_name} de {year}, tienes {cantidad_pendientes} documentos "
        f"pendientes de pago por un total de {money(monto_pendiente)}.\n"
        f"De ellos, {cantidad_pendientes_vencidos} están vencidos, "
        f"por un monto de {money(monto_pendiente_vencido)}."
    )


def handle_sales_summary(
    business_id: int,
    month: int,
    year: int,
    requested_by: str | None,
) -> XapityLucaResponse:
    ensure_snapshot_exists(
        business_id=business_id,
        month=month,
        year=year,
        requested_by=requested_by,
    )

    summary = summarize_sales_from_mongo(
        business_id=business_id,
        month=month,
        year=year,
        type_="ingreso",
        linkage=True,
        requested_by=requested_by,
        persist=True,
    )

    return XapityLucaResponse(
        ok=True,
        intent="sales_summary",
        message=build_sales_summary_message(summary),
        business_id=business_id,
        month=month,
        year=year,
        data=summary,
    )


def handle_pending_payments(
    business_id: int,
    month: int,
    year: int,
    requested_by: str | None,
) -> XapityLucaResponse:
    ensure_snapshot_exists(
        business_id=business_id,
        month=month,
        year=year,
        requested_by=requested_by,
    )

    summary = summarize_sales_from_mongo(
        business_id=business_id,
        month=month,
        year=year,
        type_="ingreso",
        linkage=True,
        requested_by=requested_by,
        persist=True,
    )

    return XapityLucaResponse(
        ok=True,
        intent="pending_payments",
        message=build_pending_payments_message(summary),
        business_id=business_id,
        month=month,
        year=year,
        data=summary,
    )


def handle_sales_excel(
    business_id: int,
    month: int,
    year: int,
    requested_by: str | None,
) -> XapityLucaResponse:
    ensure_snapshot_exists(
        business_id=business_id,
        month=month,
        year=year,
        requested_by=requested_by,
    )

    path = generate_sales_excel(
        business_id=business_id,
        month=month,
        year=year,
        type_="ingreso",
        linkage=True,
        requested_by=requested_by,
    )

    month_name = MONTH_NAMES.get(month, str(month))

    return XapityLucaResponse(
        ok=True,
        intent="sales_excel",
        message=(
            f"Listo. Generé el informe Excel de ingresos por ventas "
            f"para {month_name} de {year}."
        ),
        business_id=business_id,
        month=month,
        year=year,
        file_path=str(path),
    )


def handle_xapity_luca_request(
    request: XapityLucaRequest,
) -> XapityLucaResponse:
    business_id = request.business_id or get_default_business_id()

    analysis = analyze_xapity_luca_intent(
        message=request.message,
        business_id=business_id,
    )

    if analysis.needs_clarification:
        return XapityLucaResponse(
            ok=False,
            intent=analysis.intent,
            message="Necesito que me indiques el mes para poder responder correctamente.",
            business_id=business_id,
            month=analysis.month,
            year=analysis.year,
            needs_clarification=True,
            clarification_reason=analysis.clarification_reason,
        )

    if analysis.month is None:
        return XapityLucaResponse(
            ok=False,
            intent=analysis.intent,
            message="No pude identificar el mes solicitado.",
            business_id=business_id,
            year=analysis.year,
            needs_clarification=True,
            clarification_reason="No se detectó el mes solicitado",
        )

    if analysis.intent == "sales_summary":
        return handle_sales_summary(
            business_id=business_id,
            month=analysis.month,
            year=analysis.year,
            requested_by=request.requested_by,
        )

    if analysis.intent == "pending_payments":
        return handle_pending_payments(
            business_id=business_id,
            month=analysis.month,
            year=analysis.year,
            requested_by=request.requested_by,
        )

    if analysis.intent == "sales_excel":
        return handle_sales_excel(
            business_id=business_id,
            month=analysis.month,
            year=analysis.year,
            requested_by=request.requested_by,
        )

    return XapityLucaResponse(
        ok=False,
        intent="unknown",
        message=(
            "Por ahora puedo ayudarte con ventas mensuales, "
            "documentos pendientes de pago o informes Excel de ingresos por ventas."
        ),
        business_id=business_id,
        month=analysis.month,
        year=analysis.year,
    )


if __name__ == "__main__":
    examples = [
        "Hola Xapity, podrias decirme cuanto vendi en febrero?",
        "Podrias decirme cuantos documentos tenemos pendientes de pago en enero y el monto correspondiente?",
        "Me entregas un informe excel con los ingresos por ventas del mes de marzo?",
    ]

    for example in examples:
        print("=" * 80)

        response = handle_xapity_luca_request(
            XapityLucaRequest(
                message=example,
                requested_by="local-test",
            )
        )

        print(response.model_dump_json(indent=2))