# luca/services/luca_movements.py

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from db.mongo_persistence_luca import (
    find_luca_sales_snapshot,
    insert_luca_sales_snapshot,
)
from luca.scripts.login_luca import get_luca_access_token


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)


def is_closed_month(month: int, year: int) -> bool:
    """
    month viene en formato Luca:
    0 = todos los meses
    1 = enero
    2 = febrero
    ...
    12 = diciembre
    """

    if month == 0:
        return False

    now = datetime.now()

    if year < now.year:
        return True

    if year == now.year and month < now.month:
        return True

    return False


def get_default_business_id() -> int:
    business_id_env = os.getenv("LUCA_BUSINESS_ID")

    if not business_id_env:
        raise RuntimeError("Falta variable LUCA_BUSINESS_ID en .env")

    return int(business_id_env)


def build_luca_sales_payload(
    business_id: int,
    month: int,
    year: int,
    type_: str,
    max_results: int,
    page: int,
    linkage: bool,
    data: dict[str, Any],
    requested_by: str | None = None,
    from_cache: bool = False,
) -> dict[str, Any]:
    return {
        "metadata": {
            "businessId": business_id,
            "type": type_,
            "month": month,
            "year": year,
            "max": max_results,
            "page": page,
            "linkage": linkage,
            "closedMonth": is_closed_month(month=month, year=year),
            "source": "mongo-cache" if from_cache else "luca-api",
            "requestedBy": requested_by,
            "requestedAt": datetime.now().isoformat(),
        },
        "data": data,
    }


def get_luca_sales_summary(
    business_id: int | None = None,
    month: int = 1,
    year: int = 2026,
    type_: str = "ingreso",
    max_results: int = 500,
    page: int = 0,
    linkage: bool = True,
    use_cache: bool = True,
    force_refresh: bool = False,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """
    Consulta ventas desde Luca.

    Reglas:
    - month=1 enero, 2 febrero, ..., 12 diciembre.
    - month=0 trae todos los movimientos desde Luca.
    - Mes cerrado: puede reutilizar snapshot Mongo.
    - Mes abierto o force_refresh=True: consulta Luca API.
    """

    base_url = os.getenv("LUCA_API_BASE_URL")

    if not base_url:
        raise RuntimeError("Falta variable LUCA_API_BASE_URL en .env")

    if business_id is None:
        business_id = get_default_business_id()

    closed_month = is_closed_month(month=month, year=year)

    if use_cache and closed_month and not force_refresh:
        cached = find_luca_sales_snapshot(
            business_id=business_id,
            year=year,
            month=month,
            type_=type_,
            linkage=linkage,
        )

        if cached:
            return build_luca_sales_payload(
                business_id=business_id,
                month=month,
                year=year,
                type_=type_,
                max_results=max_results,
                page=page,
                linkage=linkage,
                data=cached.get("data", {}),
                requested_by=requested_by,
                from_cache=True,
            )

    token = get_luca_access_token()
    print("TOKEN PREVIEW:", token[:20], "...", token[-20:])

    url = (
        f"{base_url}"
        f"/v1/business/{business_id}/summary-movements-specific"
    )

    params = {
        "type": type_,
        "month": month,
        "year": year,
        "max": max_results,
        "page": page,
        "linkage": str(linkage).lower(),
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=90,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Error consultando Luca API: "
            f"{response.status_code} - {response.text}"
        )

    data = response.json()

    payload = build_luca_sales_payload(
        business_id=business_id,
        month=month,
        year=year,
        type_=type_,
        max_results=max_results,
        page=page,
        linkage=linkage,
        data=data,
        requested_by=requested_by,
        from_cache=False,
    )

    if closed_month:
        snapshot_id = insert_luca_sales_snapshot(
            payload=payload,
            requested_by=requested_by,
        )
        payload["metadata"]["snapshotId"] = snapshot_id

    return payload


if __name__ == "__main__":
    result = get_luca_sales_summary(
        month=1,
        year=2026,
        requested_by="local-test",
    )

    preview = {
        "metadata": result.get("metadata", {}),
        "count": result.get("data", {}).get("count"),
        "firstItems": result.get("data", {}).get("libros", [])[:2],
    }

    print(json.dumps(preview, indent=2, ensure_ascii=False, default=str))