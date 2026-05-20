# xapity_luca/intent.py

from __future__ import annotations

import re
import unicodedata

from schemas.xapity_luca import (
    XapityLucaIntentAnalysis,
)


MONTHS = {
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


def normalize_text(text: str) -> str:
    text = text.lower().strip()

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")

    return text


def detect_month(message: str) -> int | None:
    normalized = normalize_text(message)

    for month_name, month_number in MONTHS.items():
        if month_name in normalized:
            return month_number

    return None


def detect_requested_format(message: str) -> str:
    normalized = normalize_text(message)

    if "excel" in normalized or ".xlsx" in normalized:
        return "excel"

    if "pdf" in normalized:
        return "pdf"

    return "text"


def analyze_xapity_luca_intent(
    message: str,
    business_id: int | None = None,
) -> XapityLucaIntentAnalysis:
    normalized = normalize_text(message)

    month = detect_month(normalized)
    requested_format = detect_requested_format(normalized)

    # ==========================================
    # SALES EXCEL
    # ==========================================

    if (
        "excel" in normalized
        and (
            "venta" in normalized
            or "ventas" in normalized
            or "ingreso" in normalized
            or "ingresos" in normalized
        )
    ):
        return XapityLucaIntentAnalysis(
            intent="sales_excel",
            confidence=0.98,
            month=month,
            business_id=business_id,
            requested_format="excel",
            original_message=message,
            normalized_message=normalized,
            needs_clarification=month is None,
            clarification_reason=(
                "No se detectó el mes solicitado"
                if month is None
                else None
            ),
        )

    # ==========================================
    # PENDING PAYMENTS
    # ==========================================

    if (
        "pendiente" in normalized
        or "pendientes" in normalized
        or "pago" in normalized
        or "pagos" in normalized
        or "vencid" in normalized
    ):
        return XapityLucaIntentAnalysis(
            intent="pending_payments",
            confidence=0.95,
            month=month,
            business_id=business_id,
            requested_format=requested_format,
            original_message=message,
            normalized_message=normalized,
            needs_clarification=month is None,
            clarification_reason=(
                "No se detectó el mes solicitado"
                if month is None
                else None
            ),
        )

    # ==========================================
    # SALES SUMMARY
    # ==========================================

    if (
        "venta" in normalized
        or "ventas" in normalized
        or "ingreso" in normalized
        or "ingresos" in normalized
        or "vendi" in normalized
    ):
        return XapityLucaIntentAnalysis(
            intent="sales_summary",
            confidence=0.95,
            month=month,
            business_id=business_id,
            requested_format=requested_format,
            original_message=message,
            normalized_message=normalized,
            needs_clarification=month is None,
            clarification_reason=(
                "No se detectó el mes solicitado"
                if month is None
                else None
            ),
        )

    # ==========================================
    # UNKNOWN
    # ==========================================

    return XapityLucaIntentAnalysis(
        intent="unknown",
        confidence=0.2,
        month=month,
        business_id=business_id,
        requested_format=requested_format,
        original_message=message,
        normalized_message=normalized,
        needs_clarification=False,
    )


if __name__ == "__main__":

    examples = [
        "Hola Xapity, cuanto vendi en febrero?",
        "Cuantos pagos pendientes tenemos en enero?",
        "Generame un excel de ventas de marzo",
    ]

    for example in examples:
        result = analyze_xapity_luca_intent(example)

        print("=" * 80)
        print(result.model_dump_json(indent=2))