
# services/venue_service.py
# ============================================================
# XAPITY ACCESS — VENUE SERVICE
# ============================================================

from __future__ import annotations

import uuid

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from schemas.venue import (
    VenueCreateRequest,
    VenueUpdateRequest,
)

from db.mongo_persistence import (
    insert_venue,
    get_venues_by_business_id,
    get_venue_by_venue_id,
    update_venue_by_venue_id,
    soft_delete_venue_by_venue_id,
)


# ============================================================
# INTERNAL HELPERS
# ============================================================


def _validate_timezone(timezone_name: str) -> str:
    """
    Validates an IANA timezone.
    """
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(
            "Invalid venue timezone."
        ) from exc

    return timezone_name


def _validate_admin_context(
    current_user: Dict[str, Any],
) -> tuple[str, str]:
    """
    Validates the administrator and returns
    (business_id, user_id).

    The caller must provide the user retrieved
    from the authenticated request context.
    """
    if not current_user:
        raise PermissionError(
            "Authentication required."
        )

    if current_user.get("isDeleted", False):
        raise PermissionError(
            "User account is deleted."
        )

    if not current_user.get("isActive", False):
        raise PermissionError(
            "User account is inactive."
        )

    if current_user.get("role") != "admin":
        raise PermissionError(
            "Administrator permissions required."
        )

    business_id = current_user.get("businessId")
    user_id = current_user.get("userId")

    if not business_id or not user_id:
        raise PermissionError(
            "Invalid administrator organization context."
        )

    return str(business_id), str(user_id)


def _validate_user_context(
    current_user: Dict[str, Any],
) -> str:
    """
    Returns the businessId of an authenticated,
    active, non-deleted user.
    """
    if not current_user:
        raise PermissionError(
            "Authentication required."
        )

    if current_user.get("isDeleted", False):
        raise PermissionError(
            "User account is deleted."
        )

    if not current_user.get("isActive", False):
        raise PermissionError(
            "User account is inactive."
        )

    business_id = current_user.get("businessId")

    if not business_id:
        raise PermissionError(
            "User has no organization assigned."
        )

    return str(business_id)


# ============================================================
# CREATE VENUE
# ============================================================


def create_venue(
    payload: VenueCreateRequest,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Creates a venue within the administrator's
    organization.
    """
    business_id, user_id = _validate_admin_context(
        current_user
    )

    now = datetime.now(timezone.utc)

    timezone_name = _validate_timezone(
        payload.timezone
    )

    venue_document = {
        "venueId": str(uuid.uuid4()),
        "businessId": business_id,
        "name": payload.name.strip(),
        "description": payload.description,
        "address": (
            payload.address.model_dump()
            if payload.address is not None
            else None
        ),
        "timezone": timezone_name,
        "isActive": True,
        "isDeleted": False,
        "createdByUserId": user_id,
        "createdAt": now,
        "updatedAt": now,
    }

    return insert_venue(venue_document)


# ============================================================
# LIST VENUES
# ============================================================


def list_venues(
    current_user: Dict[str, Any],
    *,
    only_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Lists venues belonging to the authenticated
    user's organization.
    """
    business_id = _validate_user_context(
        current_user
    )

    return get_venues_by_business_id(
        business_id,
        only_active=only_active,
    )


# ============================================================
# GET VENUE
# ============================================================


def get_venue(
    venue_id: str,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Retrieves a venue belonging to the
    authenticated user's organization.
    """
    business_id = _validate_user_context(
        current_user
    )

    venue = get_venue_by_venue_id(
        venue_id,
        business_id,
    )

    if not venue:
        raise LookupError(
            "Venue not found."
        )

    return venue


# ============================================================
# UPDATE VENUE
# ============================================================


def update_venue(
    venue_id: str,
    payload: VenueUpdateRequest,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Updates a venue belonging to the
    administrator's organization.
    """
    business_id, _ = _validate_admin_context(
        current_user
    )

    update_fields = payload.model_dump(
        exclude_unset=True
    )

    if not update_fields:
        raise ValueError(
            "No venue fields provided for update."
        )

    if "name" in update_fields:
        name = update_fields["name"]

        if name is None or not name.strip():
            raise ValueError(
                "Venue name cannot be empty."
            )

        update_fields["name"] = name.strip()

    if "timezone" in update_fields:
        timezone_name = update_fields["timezone"]

        if timezone_name is None:
            raise ValueError(
                "Venue timezone cannot be null."
            )

        update_fields["timezone"] = _validate_timezone(
            timezone_name
        )

    if update_fields.get("isActive") is None:
        update_fields.pop("isActive", None)

    update_fields["updatedAt"] = datetime.now(
        timezone.utc
    )

    venue = update_venue_by_venue_id(
        venue_id,
        business_id,
        update_fields,
    )

    if not venue:
        raise LookupError(
            "Venue not found."
        )

    return venue


# ============================================================
# DELETE VENUE (SOFT DELETE)
# ============================================================


def delete_venue(
    venue_id: str,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Soft deletes a venue belonging to the
    administrator's organization.
    """
    business_id, _ = _validate_admin_context(
        current_user
    )

    venue = soft_delete_venue_by_venue_id(
        venue_id,
        business_id,
    )

    if not venue:
        raise LookupError(
            "Venue not found."
        )

    return venue
