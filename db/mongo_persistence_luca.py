# db/mongo_persistence_luca.py

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING


load_dotenv()

_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    global _client

    if _client is None:
        mongo_uri = os.getenv("MONGO_URI")

        if not mongo_uri:
            raise RuntimeError("Falta variable MONGO_URI en .env")

        _client = MongoClient(mongo_uri)

    return _client


def get_luca_db():
    mongo_db = os.getenv("MONGO_DB")

    if not mongo_db:
        raise RuntimeError("Falta variable MONGO_DB en .env")

    return get_mongo_client()[mongo_db]


def get_luca_sales_collection():
    db = get_luca_db()
    collection = db["luca_sales_snapshots"]

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("year", ASCENDING),
            ("month", ASCENDING),
            ("type", ASCENDING),
            ("linkage", ASCENDING),
        ],
        unique=False,
        name="idx_luca_sales_period",
    )

    return collection


def find_luca_sales_snapshot(
    business_id: int,
    year: int,
    month: int,
    type_: str,
    linkage: bool,
) -> dict[str, Any] | None:
    collection = get_luca_sales_collection()

    return collection.find_one(
        {
            "businessId": business_id,
            "year": year,
            "month": month,
            "type": type_,
            "linkage": linkage,
            "isActive": True,
        },
        sort=[("createdAt", -1)],
    )


def insert_luca_sales_snapshot(
    payload: dict[str, Any],
    requested_by: str | None = None,
) -> str:
    collection = get_luca_sales_collection()

    metadata = payload.get("metadata", {})
    data = payload.get("data", {})

    document = {
        "businessId": metadata.get("businessId"),
        "year": metadata.get("year"),
        "month": metadata.get("month"),
        "type": metadata.get("type"),
        "linkage": metadata.get("linkage"),
        "requestedBy": requested_by,
        "requestedAt": datetime.now(),
        "createdAt": datetime.now(),
        "updatedAt": datetime.now(),
        "isActive": True,
        "source": metadata.get("source", "luca-api"),
        "recordsCount": data.get("count"),
        "metadata": metadata,
        "data": data,
    }

    result = collection.insert_one(document)

    return str(result.inserted_id)

def get_luca_sales_summary_collection():
    db = get_luca_db()
    collection = db["luca_sales_summaries"]

    collection.create_index(
        [
            ("businessId", ASCENDING),
            ("year", ASCENDING),
            ("month", ASCENDING),
            ("type", ASCENDING),
        ],
        unique=False,
        name="idx_luca_sales_summary_period",
    )

    return collection


def insert_luca_sales_summary(summary: dict[str, Any]) -> str:
    collection = get_luca_sales_summary_collection()

    document = {
        **summary,
        "createdAt": datetime.now(),
        "updatedAt": datetime.now(),
        "isActive": True,
    }

    result = collection.insert_one(document)

    return str(result.inserted_id)

def insert_luca_report_metadata(report: dict[str, Any]) -> str:
    db = get_luca_db()
    collection = db["luca_reports"]

    document = {
        **report,
        "createdAt": datetime.now(),
        "updatedAt": datetime.now(),
        "isActive": True,
    }

    result = collection.insert_one(document)

    return str(result.inserted_id)