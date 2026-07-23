# db/mongo_subscription_persistence.py

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from db.mongo_persistence import (
    get_database,
    serialize_mongo_document,
)


load_dotenv()


# ============================================================
# CONFIGURACIÓN
# ============================================================

ORGANIZATION_SUBSCRIPTIONS_COLLECTION = os.getenv(
    "ORGANIZATION_SUBSCRIPTIONS_COLLECTION",
    "organization_subscriptions",
)

ORGANIZATION_USAGE_EVENTS_COLLECTION = os.getenv(
    "ORGANIZATION_USAGE_EVENTS_COLLECTION",
    "organization_usage_events",
)


# ============================================================
# COLLECTIONS
# ============================================================

def get_organization_subscriptions_collection() -> Collection:
    """
    Returns the MongoDB collection used for organization subscriptions.
    """
    db = get_database()
    return db[ORGANIZATION_SUBSCRIPTIONS_COLLECTION]


def get_organization_usage_events_collection() -> Collection:
    """
    Returns the MongoDB collection used for organization usage events.
    """
    db = get_database()
    return db[ORGANIZATION_USAGE_EVENTS_COLLECTION]


# ============================================================
# INDEXES
# ============================================================

def ensure_subscription_indexes() -> None:
    """
    Creates the indexes required by subscriptions and usage events.

    This function is idempotent and can safely be executed more than once.
    """
    try:
        subscriptions = get_organization_subscriptions_collection()
        usage_events = get_organization_usage_events_collection()

        subscriptions.create_index(
            [("businessId", 1)],
            unique=True,
            name="uq_organization_subscription_business_id",
        )

        subscriptions.create_index(
            [("subscriptionId", 1)],
            unique=True,
            name="uq_organization_subscription_id",
        )

        subscriptions.create_index(
            [("status", 1), ("planCode", 1)],
            name="ix_organization_subscription_status_plan",
        )

        usage_events.create_index(
            [("usageId", 1)],
            unique=True,
            name="uq_organization_usage_id",
        )

        usage_events.create_index(
            [("requestId", 1)],
            unique=True,
            name="uq_organization_usage_request_id",
        )

        usage_events.create_index(
            [("businessId", 1), ("createdAt", -1)],
            name="ix_organization_usage_business_created_at",
        )

        usage_events.create_index(
            [("userId", 1), ("createdAt", -1)],
            name="ix_organization_usage_user_created_at",
        )

        usage_events.create_index(
            [("businessId", 1), ("status", 1)],
            name="ix_organization_usage_business_status",
        )

    except PyMongoError as exc:
        raise RuntimeError(
            "Error creating subscription indexes in MongoDB."
        ) from exc


# ============================================================
# SUBSCRIPTIONS
# ============================================================

def insert_subscription(
    subscription_document: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Inserts an organization subscription document into MongoDB.

    The document must already be constructed and validated by the
    subscription service layer.

    businessId and subscriptionId are protected by unique indexes.
    """
    try:
        collection = get_organization_subscriptions_collection()

        result = collection.insert_one(subscription_document)

        inserted_document = collection.find_one({
            "_id": result.inserted_id,
        })

        if not inserted_document:
            raise RuntimeError(
                "Subscription was inserted but could not be retrieved."
            )

        return serialize_mongo_document(inserted_document)

    except DuplicateKeyError as exc:
        raise RuntimeError(
            "La organización ya tiene una suscripción registrada."
        ) from exc

    except PyMongoError as exc:
        raise RuntimeError(
            "Error inserting organization subscription into MongoDB."
        ) from exc

def get_subscription_by_business_id(
    business_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves the current subscription for an organization.
    """
    try:
        collection = get_organization_subscriptions_collection()

        document = collection.find_one({
            "businessId": business_id,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving organization subscription."
        ) from exc


def reserve_subscription_credits(
    *,
    business_id: str,
    credits: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Atomically reserves credits for an active subscription.

    The reservation succeeds only when:

        quotaUsed + quotaReserved + credits <= quotaLimit

    Returns:
        Updated subscription document when the reservation succeeds.

        None when:
        - the subscription does not exist;
        - the subscription is not active;
        - there are insufficient remaining credits.
    """
    if credits <= 0:
        raise ValueError("credits debe ser mayor que cero")

    try:
        collection = get_organization_subscriptions_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "businessId": business_id,
                "status": "active",
                "$expr": {
                    "$lte": [
                        {
                            "$add": [
                                {"$ifNull": ["$quotaUsed", 0]},
                                {"$ifNull": ["$quotaReserved", 0]},
                                credits,
                            ]
                        },
                        "$quotaLimit",
                    ]
                },
            },
            {
                "$inc": {
                    "quotaReserved": credits,
                },
                "$set": {
                    "updatedAt": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error reserving subscription credits."
        ) from exc


def confirm_subscription_credits(
    *,
    business_id: str,
    credits: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Converts reserved credits into consumed credits.

    Atomically performs:

        quotaReserved -= credits
        quotaUsed += credits

    Returns:
        Updated subscription document.

        None when the organization does not have enough reserved credits.
    """
    if credits <= 0:
        raise ValueError("credits debe ser mayor que cero")

    try:
        collection = get_organization_subscriptions_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "businessId": business_id,
                "quotaReserved": {
                    "$gte": credits,
                },
            },
            {
                "$inc": {
                    "quotaReserved": -credits,
                    "quotaUsed": credits,
                },
                "$set": {
                    "updatedAt": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error confirming subscription credits."
        ) from exc


def release_subscription_credits(
    *,
    business_id: str,
    credits: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Releases credits previously reserved after a technical failure.

    Atomically performs:

        quotaReserved -= credits

    quotaUsed is not modified.
    """
    if credits <= 0:
        raise ValueError("credits debe ser mayor que cero")

    try:
        collection = get_organization_subscriptions_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "businessId": business_id,
                "quotaReserved": {
                    "$gte": credits,
                },
            },
            {
                "$inc": {
                    "quotaReserved": -credits,
                },
                "$set": {
                    "updatedAt": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error releasing subscription credits."
        ) from exc


def update_subscription_status(
    *,
    business_id: str,
    status: str,
) -> Optional[Dict[str, Any]]:
    """
    Updates the status of an organization subscription.

    Expected statuses:
        active
        exhausted
        suspended
        expired
    """
    try:
        collection = get_organization_subscriptions_collection()

        document = collection.find_one_and_update(
            {
                "businessId": business_id,
            },
            {
                "$set": {
                    "status": status,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error updating organization subscription status."
        ) from exc


# ============================================================
# USAGE EVENTS
# ============================================================

def insert_usage_event(
    usage_document: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Inserts an organization usage event.

    requestId must be unique. This protects the system against
    duplicate processing of the same request.
    """
    try:
        collection = get_organization_usage_events_collection()

        result = collection.insert_one(usage_document)

        inserted_document = collection.find_one({
            "_id": result.inserted_id,
        })

        if not inserted_document:
            raise RuntimeError(
                "Usage event was inserted but could not be retrieved."
            )

        return serialize_mongo_document(inserted_document)

    except DuplicateKeyError as exc:
        raise RuntimeError(
            "Ya existe un evento de consumo para este requestId."
        ) from exc

    except PyMongoError as exc:
        raise RuntimeError(
            "Error inserting organization usage event into MongoDB."
        ) from exc


def get_usage_event_by_usage_id(
    usage_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a usage event by its usageId.
    """
    try:
        collection = get_organization_usage_events_collection()

        document = collection.find_one({
            "usageId": usage_id,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving usage event by usageId."
        ) from exc


def get_usage_event_by_request_id(
    request_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a usage event by its requestId.
    """
    try:
        collection = get_organization_usage_events_collection()

        document = collection.find_one({
            "requestId": request_id,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving usage event by requestId."
        ) from exc


def mark_usage_event_completed(
    *,
    request_id: str,
    engine_mode: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Marks a reserved usage event as completed.

    This transition is allowed only from:

        reserved -> completed
    """
    try:
        collection = get_organization_usage_events_collection()

        now = datetime.now(timezone.utc)

        update_fields: Dict[str, Any] = {
            "status": "completed",
            "completedAt": now,
            "updatedAt": now,
        }

        if engine_mode is not None:
            update_fields["engineMode"] = engine_mode

        document = collection.find_one_and_update(
            {
                "requestId": request_id,
                "status": "reserved",
            },
            {
                "$set": update_fields,
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error marking usage event as completed."
        ) from exc


def mark_usage_event_released(
    *,
    request_id: str,
    failure_type: str,
) -> Optional[Dict[str, Any]]:
    """
    Marks a reserved usage event as released.

    This transition is allowed only from:

        reserved -> released
    """
    try:
        collection = get_organization_usage_events_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "requestId": request_id,
                "status": "reserved",
            },
            {
                "$set": {
                    "status": "released",
                    "failureType": failure_type,
                    "releasedAt": now,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error marking usage event as released."
        ) from exc


def get_usage_events_by_business_id(
    business_id: str,
    *,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Retrieves the most recent usage events for an organization.
    """
    if limit <= 0:
        raise ValueError("limit debe ser mayor que cero")

    try:
        collection = get_organization_usage_events_collection()

        documents = (
            collection
            .find({
                "businessId": business_id,
            })
            .sort("createdAt", -1)
            .limit(limit)
        )

        return [
            serialize_mongo_document(document)
            for document in documents
        ]

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving organization usage events."
        ) from exc