# data_loader/movimientos_ventas.py

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient


# ==================================================
# ENV / MONGO
# ==================================================

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB")

if not MONGODB_URI:
    raise RuntimeError("Falta MONGODB_URI en .env")

if not MONGODB_DB:
    raise RuntimeError("Falta MONGODB_DB en .env")


client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]


# ==================================================
# FECHAS
# ==================================================

def _parse_fecha(s: str) -> Optional[datetime]:
    if not s:
        return None

    s = str(s).strip()

    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    return None


def _parse_cli_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Fecha inválida: {s}. Usa formato YYYY-MM-DD"
        )


def _iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _months_between(start: date, end: date) -> List[str]:
    """
    Retorna meses en formato MM-YYYY para acotar queries tipo:
    01-2026&document=33
    """
    months: List[str] = []

    y, m = start.year, start.month

    while (y < end.year) or (y == end.year and m <= end.month):
        months.append(f"{m:02d}-{y}")

        m += 1
        if m == 13:
            m = 1
            y += 1

    return months


# ==================================================
# LOADER
# ==================================================

def cargar_ventas(
    business_id: int,
    start_date: date,
    end_date: date,
    include_documents: Optional[Iterable[int]] = None,
    exclude_documents: Optional[Iterable[int]] = (61,),
    limit_docs: int = 100000,
) -> List[Dict]:
    """
    Carga documentos de venta desde Mongo/Luca para un businessId
    y rango de fechas.

    - Filtra por businessId.
    - Acota por meses usando el campo query: MM-YYYY&document=NN.
    - Desanida data.
    - Excluye notas de crédito 61 por defecto.
    - Filtra finalmente por detFchDoc entre start_date y end_date.
    """

    months = _months_between(start_date, end_date)

    doc_whitelist = set(include_documents) if include_documents else None
    doc_blacklist = set(exclude_documents or ())

    query_regexes: List[Dict] = []

    for mm_yyyy in months:
        if doc_whitelist:
            for d in doc_whitelist:
                query_regexes.append(
                    {"query": {"$regex": f"^{mm_yyyy}&document={d}$"}}
                )
        else:
            query_regexes.append(
                {"query": {"$regex": f"^{mm_yyyy}&document=\\d+$"}}
            )

    pipeline: List[Dict] = [
        {"$match": {"businessId": business_id}},
        {"$match": {"$or": query_regexes}},
        {"$unwind": "$data"},
        {
            "$project": {
                "_id": 0,
                "businessId": 1,
                "query": 1,
                "detNroDoc": "$data.detNroDoc",
                "detMntTotal": "$data.detMntTotal",
                "detFchDoc": "$data.detFchDoc",
                "detRznSoc": "$data.detRznSoc",
                "detRutDoc": "$data.detRutDoc",
                "detDvDoc": "$data.detDvDoc",
                "detEventoReceptorLeyenda": "$data.detEventoReceptorLeyenda",
            }
        },
        {"$limit": int(limit_docs)},
    ]

    rows = list(db["ventas"].aggregate(pipeline))

    norm: List[Dict] = []

    for r in rows:
        q = r.get("query") or ""

        try:
            parts = dict(
                p.split("=") if "=" in p else ("month", p)
                for p in q.split("&")
            )
            doc_type = int(parts.get("document", "0"))
        except Exception:
            doc_type = 0

        if doc_type in doc_blacklist:
            continue

        if doc_whitelist and doc_type not in doc_whitelist:
            continue

        dt = _parse_fecha(r.get("detFchDoc"))

        if not dt:
            continue

        doc_date = dt.date()

        if doc_date < start_date or doc_date > end_date:
            continue

        try:
            monto = float(r.get("detMntTotal") or 0)
        except Exception:
            monto = 0.0

        norm.append(
            {
                **r,
                "document_type": doc_type,
                "detMntTotal": monto,
                "detFchDoc_dt": dt,
                "detFchDoc_iso": _iso_date(dt),
            }
        )

    norm.sort(key=lambda x: x["detFchDoc_dt"])

    return norm


# ==================================================
# RESUMEN
# ==================================================

def resumir_ventas(rows: List[Dict], business_id: int, start_date: date, end_date: date) -> Dict:
    total = sum(float(r.get("detMntTotal") or 0) for r in rows)

    by_document_type: Dict[str, Dict] = {}

    for r in rows:
        doc_type = str(r.get("document_type", "unknown"))

        if doc_type not in by_document_type:
            by_document_type[doc_type] = {
                "document_type": r.get("document_type"),
                "count": 0,
                "total": 0.0,
            }

        by_document_type[doc_type]["count"] += 1
        by_document_type[doc_type]["total"] += float(r.get("detMntTotal") or 0)

    return {
        "businessId": business_id,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "totalIngresosVenta": total,
        "totalDocumentos": len(rows),
        "byDocumentType": list(by_document_type.values()),
        "items": rows,
    }


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    return str(obj)


# ==================================================
# CLI
# ==================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consulta ventas Luca desde Mongo por businessId y rango de fechas."
    )

    parser.add_argument("--business-id", type=int, required=True)
    parser.add_argument("--start-date", type=_parse_cli_date, required=True)
    parser.add_argument("--end-date", type=_parse_cli_date, required=True)

    parser.add_argument(
        "--include-documents",
        type=str,
        default=None,
        help="Lista separada por comas. Ej: 33,34,39",
    )

    parser.add_argument(
        "--exclude-documents",
        type=str,
        default="61",
        help="Lista separada por comas. Default: 61",
    )

    parser.add_argument("--limit-docs", type=int, default=100000)
    parser.add_argument("--out-dir", type=str, default="results")

    args = parser.parse_args()

    if args.start_date > args.end_date:
        raise ValueError("start-date no puede ser mayor que end-date")

    include_documents = (
        [int(x.strip()) for x in args.include_documents.split(",") if x.strip()]
        if args.include_documents
        else None
    )

    exclude_documents = (
        [int(x.strip()) for x in args.exclude_documents.split(",") if x.strip()]
        if args.exclude_documents
        else []
    )

    rows = cargar_ventas(
        business_id=args.business_id,
        start_date=args.start_date,
        end_date=args.end_date,
        include_documents=include_documents,
        exclude_documents=exclude_documents,
        limit_docs=args.limit_docs,
    )

    result = resumir_ventas(
        rows=rows,
        business_id=args.business_id,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / (
        f"ventas_business_{args.business_id}_"
        f"{args.start_date.isoformat()}_to_{args.end_date.isoformat()}.json"
    )

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=_json_default)

    print("Consulta ventas completada")
    print(f"businessId: {args.business_id}")
    print(f"desde: {args.start_date.isoformat()}")
    print(f"hasta: {args.end_date.isoformat()}")
    print(f"documentos: {result['totalDocumentos']}")
    print(f"total ingresos venta: {result['totalIngresosVenta']}")
    print(f"archivo: {out_file}")


if __name__ == "__main__":
    main()