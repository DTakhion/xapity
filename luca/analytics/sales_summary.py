# luca/analytics/sales_summary.py

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from db.mongo_persistence_luca import (
    find_luca_sales_snapshot,
    insert_luca_sales_summary,
)


def get_libros(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return snapshot.get("data", {}).get("libros", [])


def safe_float(value: Any) -> float:
    return float(value or 0)


def build_sales_summary_from_snapshot(
    snapshot: dict[str, Any],
    requested_by: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    metadata = snapshot.get("metadata", {})
    libros = get_libros(snapshot)

    business_id = snapshot.get("businessId") or metadata.get("businessId")
    year = snapshot.get("year") or metadata.get("year")
    month = snapshot.get("month") or metadata.get("month")
    type_ = snapshot.get("type") or metadata.get("type", "ingreso")

    total_documentos = len(libros)

    monto_total = sum(safe_float(item.get("montoTotal")) for item in libros)
    monto_iva_retenido = sum(safe_float(item.get("montoIvaRetenido")) for item in libros)
    monto_neto_liquido = sum(safe_float(item.get("montoNetoLiquido")) for item in libros)
    monto_exento = sum(safe_float(item.get("montoExento")) for item in libros)

    cobrados = [
        item for item in libros
        if str(item.get("status", "")).upper() == "COBRADO"
    ]

    pendientes = [
        item for item in libros
        if str(item.get("status", "")).upper() != "COBRADO"
    ]

    pendientes_vencidos = [
        item for item in pendientes
        if str(item.get("diasHastaVencimiento", "")).lower() == "vencida"
    ]

    monto_cobrado = sum(safe_float(item.get("montoTotal")) for item in cobrados)
    monto_pendiente = sum(safe_float(item.get("montoTotal")) for item in pendientes)
    monto_pendiente_vencido = sum(
        safe_float(item.get("montoTotal")) for item in pendientes_vencidos
    )

    status_counts: dict[str, int] = defaultdict(int)

    clientes: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "rut": None,
            "razonSocial": None,
            "cantidadDocumentos": 0,
            "montoTotal": 0.0,
            "montoCobrado": 0.0,
            "montoPendiente": 0.0,
        }
    )

    for item in libros:
        status = str(item.get("status") or "SIN_STATUS").upper()
        status_counts[status] += 1

        rut = item.get("rut") or "SIN_RUT"
        razon_social = item.get("razonSocial") or "SIN_RAZON_SOCIAL"
        monto = safe_float(item.get("montoTotal"))

        cliente = clientes[rut]
        cliente["rut"] = rut
        cliente["razonSocial"] = razon_social
        cliente["cantidadDocumentos"] += 1
        cliente["montoTotal"] += monto

        if status == "COBRADO":
            cliente["montoCobrado"] += monto
        else:
            cliente["montoPendiente"] += monto

    top_clientes = sorted(
        clientes.values(),
        key=lambda item: item["montoTotal"],
        reverse=True,
    )

    summary = {
        "businessId": business_id,
        "year": year,
        "month": month,
        "type": type_,
        "requestedBy": requested_by,
        "generatedAt": datetime.now().isoformat(),
        "source": "mongo-snapshot",
        "sourceSnapshotId": str(snapshot.get("_id")) if snapshot.get("_id") else None,
        "recordsCount": total_documentos,
        "resumen": {
            "totalDocumentos": total_documentos,
            "montoTotalVentas": monto_total,
            "montoCobrado": monto_cobrado,
            "montoPendiente": monto_pendiente,
            "montoPendienteVencido": monto_pendiente_vencido,
            "montoIvaRetenido": monto_iva_retenido,
            "montoNetoLiquido": monto_neto_liquido,
            "montoExento": monto_exento,
            "cantidadCobrados": len(cobrados),
            "cantidadPendientes": len(pendientes),
            "cantidadPendientesVencidos": len(pendientes_vencidos),
        },
        "statusCounts": dict(status_counts),
        "topClientes": top_clientes[:3],
    }

    if persist:
        summary_id = insert_luca_sales_summary(summary)
        summary["summaryId"] = summary_id

    return summary


def summarize_sales_from_mongo(
    business_id: int,
    month: int,
    year: int,
    type_: str = "ingreso",
    linkage: bool = True,
    requested_by: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    snapshot = find_luca_sales_snapshot(
        business_id=business_id,
        year=year,
        month=month,
        type_=type_,
        linkage=linkage,
    )

    if not snapshot:
        raise FileNotFoundError(
            f"No existe snapshot Mongo para businessId={business_id}, "
            f"year={year}, month={month}, type={type_}, linkage={linkage}"
        )

    return build_sales_summary_from_snapshot(
        snapshot=snapshot,
        requested_by=requested_by,
        persist=persist,
    )


if __name__ == "__main__":
    summary = summarize_sales_from_mongo(
        business_id=11,
        month=1,
        year=2026,
        requested_by="local-test",
        persist=True,
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))