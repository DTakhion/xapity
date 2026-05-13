# services/sales_service.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from data_loader.movimientos_ventas import cargar_ventas, resumir_ventas


def get_sales_total_for_period(
    *,
    business_id: int,
    start_date: date,
    end_date: date,
    include_documents: List[int] | None = None,
) -> Dict[str, Any]:

    rows = cargar_ventas(
        business_id=business_id,
        start_date=start_date,
        end_date=end_date,
        include_documents=include_documents or [33, 34],
        exclude_documents=[61],
    )

    return resumir_ventas(
        rows=rows,
        business_id=business_id,
        start_date=start_date,
        end_date=end_date,
    )