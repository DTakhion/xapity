# services/subscription_service.py

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from db.mongo_subscription_persistence import (
    ensure_subscription_indexes,
    insert_subscription,
    get_subscription_by_business_id,
    reserve_subscription_credits,
    confirm_subscription_credits,
    release_subscription_credits,
    insert_usage_event,
    get_usage_event_by_request_id,
    mark_usage_event_completed,
    mark_usage_event_released,
    get_usage_events_by_business_id,
)


load_dotenv()


# ============================================================
# CONFIGURACIÓN
# ============================================================

TRIAL_QUOTA_LIMIT = int(
    os.getenv("TRIAL_QUOTA_LIMIT", "100")
)


# ============================================================
# DOMAIN ERRORS
# ============================================================

class SubscriptionError(Exception):
    """
    Base exception for subscription domain errors.
    """


class SubscriptionNotFoundError(SubscriptionError):
    """
    Raised when an organization does not have a subscription.
    """


class SubscriptionInactiveError(SubscriptionError):
    """
    Raised when a subscription is not active.
    """


class QuotaExceededError(SubscriptionError):
    """
    Raised when the organization does not have enough available credits.
    """


class UsageEventNotFoundError(SubscriptionError):
    """
    Raised when a usage event cannot be found.
    """


class InvalidUsageEventStateError(SubscriptionError):
    """
    Raised when a usage event cannot transition from its current state.
    """


class UsageRequestConflictError(SubscriptionError):
    """
    Raised when a requestId belongs to another user or organization.
    """


# ============================================================
# HELPERS
# ============================================================

def _validate_non_empty(value: str, field_name: str) -> str:
    """
    Validates and normalizes required string values.
    """
    normalized_value = str(value or "").strip()

    if not normalized_value:
        raise ValueError(f"{field_name} es obligatorio")

    return normalized_value


def _validate_credits(credits: int) -> int:
    """
    Validates the amount of credits involved in an operation.
    """
    if credits <= 0:
        raise ValueError("credits debe ser mayor que cero")

    return credits


def _build_quota(
    subscription: Dict[str, Any],
) -> Dict[str, int]:
    """
    Builds a public quota representation from a subscription document.

    Remaining credits consider both completed consumption and credits
    currently reserved by requests that are still being processed.
    """
    quota_limit = int(subscription.get("quotaLimit") or 0)
    quota_used = int(subscription.get("quotaUsed") or 0)
    quota_reserved = int(subscription.get("quotaReserved") or 0)

    remaining = max(
        quota_limit - quota_used - quota_reserved,
        0,
    )

    return {
        "limit": quota_limit,
        "used": quota_used,
        "reserved": quota_reserved,
        "remaining": remaining,
    }


def _build_public_subscription_status(
    subscription: Dict[str, Any],
) -> str:
    """
    Returns the public subscription status.

    An active subscription with no available credits is exposed as
    exhausted without changing the persisted status. This allows a
    released reservation to make credits available again.
    """
    persisted_status = str(
        subscription.get("status") or "active"
    )

    quota = _build_quota(subscription)

    if persisted_status == "active" and quota["remaining"] == 0:
        return "exhausted"

    return persisted_status


def _build_usage_summary(
    subscription: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Builds the subscription and quota summary returned to the API.
    """
    return {
        "businessId": subscription["businessId"],
        "planCode": subscription["planCode"],
        "status": _build_public_subscription_status(subscription),
        "quota": _build_quota(subscription),
        "periodType": subscription["periodType"],
        "periodStart": subscription["periodStart"],
        "periodEnd": subscription.get("periodEnd"),
    }


def _validate_usage_event_owner(
    usage_event: Dict[str, Any],
    *,
    business_id: str,
    user_id: Optional[str] = None,
) -> None:
    """
    Ensures that a usage event belongs to the expected organization
    and optionally to the expected user.
    """
    if usage_event.get("businessId") != business_id:
        raise UsageRequestConflictError(
            "El requestId pertenece a otra organización."
        )

    if (
        user_id is not None
        and usage_event.get("userId") != user_id
    ):
        raise UsageRequestConflictError(
            "El requestId pertenece a otro usuario."
        )


# ============================================================
# INITIALIZATION
# ============================================================

def initialize_subscription_storage() -> None:
    """
    Creates the MongoDB indexes required by the subscription domain.

    This function is idempotent and should normally be called during
    application startup.
    """
    ensure_subscription_indexes()


# ============================================================
# TRIAL SUBSCRIPTION
# ============================================================

def create_trial_for_organization(
    *,
    business_id: str,
    created_by_user_id: str,
    quota_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Creates the initial Trial subscription for an organization.

    The operation is idempotent:
    if the organization already has a subscription, the existing
    document is returned.

    Business rules:
    - planCode: trial
    - status: active
    - periodType: lifetime_trial
    - quotaUsed: 0
    - quotaReserved: 0
    """
    normalized_business_id = _validate_non_empty(
        business_id,
        "business_id",
    )

    normalized_user_id = _validate_non_empty(
        created_by_user_id,
        "created_by_user_id",
    )

    resolved_quota_limit = (
        quota_limit
        if quota_limit is not None
        else TRIAL_QUOTA_LIMIT
    )

    if resolved_quota_limit <= 0:
        raise ValueError(
            "El límite de consultas del Trial debe ser mayor que cero"
        )

    existing_subscription = get_subscription_by_business_id(
        normalized_business_id
    )

    if existing_subscription:
        return existing_subscription

    now = datetime.now(timezone.utc)

    subscription_document = {
        "subscriptionId": str(uuid.uuid4()),
        "businessId": normalized_business_id,
        "planCode": "trial",
        "status": "active",
        "quotaLimit": resolved_quota_limit,
        "quotaUsed": 0,
        "quotaReserved": 0,
        "periodType": "lifetime_trial",
        "periodStart": now,
        "periodEnd": None,
        "createdByUserId": normalized_user_id,
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        return insert_subscription(subscription_document)

    except RuntimeError:
        # Protection against two concurrent attempts to create the
        # same subscription. The unique businessId index allows only
        # one insert; the other execution retrieves the winner.
        existing_subscription = get_subscription_by_business_id(
            normalized_business_id
        )

        if existing_subscription:
            return existing_subscription

        raise


# ============================================================
# SUBSCRIPTION QUOTA
# ============================================================

def get_organization_usage(
    *,
    business_id: str,
) -> Dict[str, Any]:
    """
    Returns the current plan and quota status for an organization.
    """
    normalized_business_id = _validate_non_empty(
        business_id,
        "business_id",
    )

    subscription = get_subscription_by_business_id(
        normalized_business_id
    )

    if not subscription:
        raise SubscriptionNotFoundError(
            "La organización no tiene una suscripción registrada."
        )

    return _build_usage_summary(subscription)


# ============================================================
# RESERVE CREDIT
# ============================================================

def reserve_question_credit(
    *,
    business_id: str,
    user_id: str,
    endpoint: str,
    request_id: Optional[str] = None,
    credits: int = 1,
) -> Dict[str, Any]:
    """
    Atomically reserves credits before executing a question.

    Flow:
        1. Validate request identity.
        2. Protect against duplicate requestId.
        3. Atomically reserve subscription credits.
        4. Create a usage event with status=reserved.

    If the usage event cannot be created after reserving the credits,
    the reservation is compensated and released.
    """
    normalized_business_id = _validate_non_empty(
        business_id,
        "business_id",
    )

    normalized_user_id = _validate_non_empty(
        user_id,
        "user_id",
    )

    normalized_endpoint = _validate_non_empty(
        endpoint,
        "endpoint",
    )

    resolved_credits = _validate_credits(credits)

    resolved_request_id = (
        str(request_id).strip()
        if request_id is not None
        else str(uuid.uuid4())
    )

    if not resolved_request_id:
        raise ValueError("request_id no puede estar vacío")

    existing_event = get_usage_event_by_request_id(
        resolved_request_id
    )

    if existing_event:
        _validate_usage_event_owner(
            existing_event,
            business_id=normalized_business_id,
            user_id=normalized_user_id,
        )

        existing_subscription = get_subscription_by_business_id(
            normalized_business_id
        )

        if not existing_subscription:
            raise SubscriptionNotFoundError(
                "La organización no tiene una suscripción registrada."
            )

        return {
            "usageId": existing_event["usageId"],
            "requestId": existing_event["requestId"],
            "businessId": existing_event["businessId"],
            "userId": existing_event["userId"],
            "credits": int(existing_event.get("credits") or 1),
            "status": existing_event["status"],
            "quota": _build_quota(existing_subscription),
        }

    updated_subscription = reserve_subscription_credits(
        business_id=normalized_business_id,
        credits=resolved_credits,
    )

    if not updated_subscription:
        subscription = get_subscription_by_business_id(
            normalized_business_id
        )

        if not subscription:
            raise SubscriptionNotFoundError(
                "La organización no tiene una suscripción registrada."
            )

        subscription_status = str(
            subscription.get("status") or ""
        )

        if subscription_status != "active":
            raise SubscriptionInactiveError(
                "La suscripción de la organización no está activa."
            )

        raise QuotaExceededError(
            "La organización agotó su cuota disponible."
        )

    now = datetime.now(timezone.utc)

    usage_document = {
        "usageId": str(uuid.uuid4()),
        "requestId": resolved_request_id,
        "businessId": normalized_business_id,
        "userId": normalized_user_id,
        "endpoint": normalized_endpoint,
        "resourceType": "question",
        "engineMode": None,
        "credits": resolved_credits,
        "status": "reserved",
        "reservedAt": now,
        "completedAt": None,
        "releasedAt": None,
        "failureType": None,
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        inserted_event = insert_usage_event(
            usage_document
        )

    except Exception:
        released_subscription = release_subscription_credits(
            business_id=normalized_business_id,
            credits=resolved_credits,
        )

        if not released_subscription:
            raise RuntimeError(
                "No fue posible registrar el evento de consumo ni "
                "compensar la reserva de créditos."
            )

        # Another concurrent request may have inserted the same
        # requestId after our initial existence check.
        duplicated_event = get_usage_event_by_request_id(
            resolved_request_id
        )

        if duplicated_event:
            _validate_usage_event_owner(
                duplicated_event,
                business_id=normalized_business_id,
                user_id=normalized_user_id,
            )

            current_subscription = get_subscription_by_business_id(
                normalized_business_id
            )

            if not current_subscription:
                raise SubscriptionNotFoundError(
                    "La organización no tiene una suscripción registrada."
                )

            return {
                "usageId": duplicated_event["usageId"],
                "requestId": duplicated_event["requestId"],
                "businessId": duplicated_event["businessId"],
                "userId": duplicated_event["userId"],
                "credits": int(
                    duplicated_event.get("credits") or 1
                ),
                "status": duplicated_event["status"],
                "quota": _build_quota(current_subscription),
            }

        raise

    return {
        "usageId": inserted_event["usageId"],
        "requestId": inserted_event["requestId"],
        "businessId": inserted_event["businessId"],
        "userId": inserted_event["userId"],
        "credits": int(inserted_event["credits"]),
        "status": inserted_event["status"],
        "quota": _build_quota(updated_subscription),
    }


# ============================================================
# COMPLETE CREDIT
# ============================================================

def complete_question_credit(
    *,
    business_id: str,
    request_id: str,
    engine_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Confirms a reserved credit after a successful response.

    Flow:
        reserved subscription credit
        -> quotaReserved decreases
        -> quotaUsed increases
        -> usage event becomes completed

    Calling this function again for an already completed event is
    idempotent and does not consume a second credit.
    """
    normalized_business_id = _validate_non_empty(
        business_id,
        "business_id",
    )

    normalized_request_id = _validate_non_empty(
        request_id,
        "request_id",
    )

    usage_event = get_usage_event_by_request_id(
        normalized_request_id
    )

    if not usage_event:
        raise UsageEventNotFoundError(
            "No existe un evento de consumo para este requestId."
        )

    _validate_usage_event_owner(
        usage_event,
        business_id=normalized_business_id,
    )

    current_status = usage_event.get("status")

    if current_status == "completed":
        subscription = get_subscription_by_business_id(
            normalized_business_id
        )

        if not subscription:
            raise SubscriptionNotFoundError(
                "La organización no tiene una suscripción registrada."
            )

        return {
            "usageId": usage_event["usageId"],
            "requestId": usage_event["requestId"],
            "businessId": usage_event["businessId"],
            "userId": usage_event["userId"],
            "credits": int(usage_event.get("credits") or 1),
            "status": "completed",
            "engineMode": usage_event.get("engineMode"),
            "quota": _build_quota(subscription),
        }

    if current_status != "reserved":
        raise InvalidUsageEventStateError(
            f"No es posible completar un evento con estado "
            f"'{current_status}'."
        )

    credits = int(usage_event.get("credits") or 1)

    updated_subscription = confirm_subscription_credits(
        business_id=normalized_business_id,
        credits=credits,
    )

    if not updated_subscription:
        raise InvalidUsageEventStateError(
            "La organización no tiene suficientes créditos reservados "
            "para completar la operación."
        )

    completed_event = mark_usage_event_completed(
        request_id=normalized_request_id,
        engine_mode=engine_mode,
    )

    if not completed_event:
        raise RuntimeError(
            "El crédito fue confirmado, pero no fue posible marcar "
            "el evento de consumo como completado."
        )

    return {
        "usageId": completed_event["usageId"],
        "requestId": completed_event["requestId"],
        "businessId": completed_event["businessId"],
        "userId": completed_event["userId"],
        "credits": int(completed_event.get("credits") or 1),
        "status": completed_event["status"],
        "engineMode": completed_event.get("engineMode"),
        "quota": _build_quota(updated_subscription),
    }


# ============================================================
# RELEASE CREDIT
# ============================================================

def release_question_credit(
    *,
    business_id: str,
    request_id: str,
    failure_type: str = "technical_error",
) -> Dict[str, Any]:
    """
    Releases a reserved credit after a technical execution failure.

    Flow:
        quotaReserved decreases
        quotaUsed remains unchanged
        usage event becomes released

    Calling this function again for an already released event is
    idempotent.
    """
    normalized_business_id = _validate_non_empty(
        business_id,
        "business_id",
    )

    normalized_request_id = _validate_non_empty(
        request_id,
        "request_id",
    )

    normalized_failure_type = _validate_non_empty(
        failure_type,
        "failure_type",
    )

    usage_event = get_usage_event_by_request_id(
        normalized_request_id
    )

    if not usage_event:
        raise UsageEventNotFoundError(
            "No existe un evento de consumo para este requestId."
        )

    _validate_usage_event_owner(
        usage_event,
        business_id=normalized_business_id,
    )

    current_status = usage_event.get("status")

    if current_status == "released":
        subscription = get_subscription_by_business_id(
            normalized_business_id
        )

        if not subscription:
            raise SubscriptionNotFoundError(
                "La organización no tiene una suscripción registrada."
            )

        return {
            "usageId": usage_event["usageId"],
            "requestId": usage_event["requestId"],
            "businessId": usage_event["businessId"],
            "userId": usage_event["userId"],
            "credits": int(usage_event.get("credits") or 1),
            "status": "released",
            "failureType": usage_event.get("failureType"),
            "quota": _build_quota(subscription),
        }

    if current_status != "reserved":
        raise InvalidUsageEventStateError(
            f"No es posible liberar un evento con estado "
            f"'{current_status}'."
        )

    credits = int(usage_event.get("credits") or 1)

    updated_subscription = release_subscription_credits(
        business_id=normalized_business_id,
        credits=credits,
    )

    if not updated_subscription:
        raise InvalidUsageEventStateError(
            "La organización no tiene suficientes créditos reservados "
            "para liberar la operación."
        )

    released_event = mark_usage_event_released(
        request_id=normalized_request_id,
        failure_type=normalized_failure_type,
    )

    if not released_event:
        raise RuntimeError(
            "El crédito fue liberado, pero no fue posible marcar "
            "el evento de consumo como liberado."
        )

    return {
        "usageId": released_event["usageId"],
        "requestId": released_event["requestId"],
        "businessId": released_event["businessId"],
        "userId": released_event["userId"],
        "credits": int(released_event.get("credits") or 1),
        "status": released_event["status"],
        "failureType": released_event.get("failureType"),
        "quota": _build_quota(updated_subscription),
    }


# ============================================================
# USAGE HISTORY
# ============================================================

def get_organization_usage_events(
    *,
    business_id: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Returns the most recent usage events for an organization.
    """
    normalized_business_id = _validate_non_empty(
        business_id,
        "business_id",
    )

    if limit <= 0:
        raise ValueError("limit debe ser mayor que cero")

    return get_usage_events_by_business_id(
        normalized_business_id,
        limit=limit,
    )