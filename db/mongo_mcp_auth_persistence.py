# db/mongo_mcp_auth_persistence.py
# ============================================================
# XAPITY LUCA MCP — USER PROVISIONING PERSISTENCE
# ============================================================

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from db.mongo_persistence import (
    get_database,
    serialize_mongo_document,
)


MCP_PROVISIONING_TOKENS_COLLECTION = os.getenv(
    "MCP_PROVISIONING_TOKENS_COLLECTION",
    "mcp_user_provisioning_tokens",
)

MCP_PROVISIONING_PURPOSE = "mcp_user_registration"


def get_mcp_provisioning_collection() -> Collection:
    return get_database()[MCP_PROVISIONING_TOKENS_COLLECTION]


def initialize_mcp_provisioning_storage() -> None:
    try:
        collection = get_mcp_provisioning_collection()

        collection.create_index(
            "tokenHash",
            unique=True,
            name="ux_mcp_provisioning_token_hash",
        )

        collection.create_index(
            "email",
            name="ix_mcp_provisioning_email",
        )

        collection.create_index(
            "expiresAt",
            expireAfterSeconds=0,
            name="ttl_mcp_provisioning_expires_at",
        )

    except PyMongoError as exc:
        raise RuntimeError(
            "Error initializing MCP provisioning storage."
        ) from exc


def insert_mcp_provisioning_token(
    token_document: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        collection = get_mcp_provisioning_collection()

        if (
            not token_document.get("tokenHash")
            or token_document.get("purpose")
            != MCP_PROVISIONING_PURPOSE
        ):
            raise ValueError(
                "Invalid MCP provisioning document."
            )

        result = collection.insert_one(token_document)

        document = collection.find_one({
            "_id": result.inserted_id,
        })

        if document is None:
            raise RuntimeError(
                "MCP provisioning token could not be retrieved."
            )

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error inserting MCP provisioning token."
        ) from exc


def get_mcp_provisioning_token(
    token_hash: str,
    email: str,
) -> Optional[Dict[str, Any]]:
    try:
        collection = get_mcp_provisioning_collection()

        document = collection.find_one({
            "tokenHash": token_hash,
            "email": email.strip().lower(),
            "purpose": MCP_PROVISIONING_PURPOSE,
            "usedAt": None,
            "expiresAt": {
                "$gt": datetime.now(timezone.utc),
            },
        })

        if document is None:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving MCP provisioning token."
        ) from exc


def mark_mcp_provisioning_token_used(
    token_hash: str,
    email: str,
) -> Optional[Dict[str, Any]]:
    try:
        collection = get_mcp_provisioning_collection()
        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "tokenHash": token_hash,
                "email": email.strip().lower(),
                "purpose": MCP_PROVISIONING_PURPOSE,
                "usedAt": None,
                "expiresAt": {"$gt": now},
            },
            {
                "$set": {
                    "usedAt": now,
                    "updatedAt": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )

        if document is None:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error consuming MCP provisioning token."
        ) from exc
