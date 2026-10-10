# services/venue_membership_service.py
# ============================================================
# XAPITY ACCESS — VENUE MEMBERSHIP SERVICE
# ============================================================

from __future__ import annotations

import uuid

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.errors import DuplicateKeyError

from schemas.venue_membership import (
    VenueMembershipCreateRequest,
    VenueMembershipUpdateRequest,
)

from db.mongo_persistence import (
    get_user_by_user_id,
    get_venue_by_venue_id,
    get_venues_by_business_id,
    insert_venue_membership,
    get_venue_membership_by_user_and_venue,
    get_venue_membership_by_membership_id,
    get_venue_memberships_by_venue_id,
    get_venue_memberships_by_user_id,
    update_venue_membership_by_membership_id,
    soft_delete_venue_membership_by_membership_id,
)


# ============================================================
# INTERNAL HELPERS
# ============================================================


class VenueMembershipConflictError(Exception):
    """
    Membership already exists or conflicts
    with the requested operation.
    """


def _validate_user_context(
    current_user: Dict[str, Any],
) -> tuple[str, str]:
    """
    Validates an authenticated user and returns
    (business_id, user_id).
    """
    if not current_user:
        raise PermissionError("Authentication required.")

    if current_user.get("isDeleted", False):
        raise PermissionError("User account is deleted.")

    if not current_user.get("isActive", False):
        raise PermissionError("User account is inactive.")

    business_id = current_user.get("businessId")
    user_id = current_user.get("userId")

    if not business_id or not user_id:
        raise PermissionError(
            "Invalid user organization context."
        )

    return str(business_id), str(user_id)


def _validate_admin_context(
    current_user: Dict[str, Any],
) -> tuple[str, str]:
    """
    Requires an active organizational administrator.
    """
    business_id, user_id = _validate_user_context(
        current_user
    )

    if current_user.get("role") != "admin":
        raise PermissionError(
            "Administrator permissions required."
        )

    return business_id, user_id


def _require_active_venue(
    venue_id: str,
    business_id: str,
) -> Dict[str, Any]:
    """
    Ensures the venue exists, belongs to the
    organization and is operational.
    """
    venue = get_venue_by_venue_id(
        venue_id,
        business_id,
    )

    if not venue:
        raise LookupError("Venue not found.")

    if not venue.get("isActive", False):
        raise ValueError(
            "Venue is inactive."
        )

    return venue


def _require_eligible_user(
    user_id: str,
    business_id: str,
) -> Dict[str, Any]:
    """
    Ensures the target user exists, is active,
    belongs to the organization and is eligible
    for operational membership.
    """
    user = get_user_by_user_id(user_id)

    if not user:
        raise LookupError("User not found.")

    if str(user.get("businessId") or "") != business_id:
        raise LookupError("User not found.")

    if not user.get("isActive", False):
        raise ValueError("User is inactive.")

    if user.get("role") == "admin":
        raise ValueError(
            "Organization administrators do not require "
            "venue memberships."
        )

    if user.get("role") != "staff":
        raise ValueError(
            "Only staff users can receive operational "
            "venue memberships."
        )

    return user


# ============================================================
# CREATE / REACTIVATE MEMBERSHIP
# ============================================================


def create_venue_membership(
    venue_id: str,
    payload: VenueMembershipCreateRequest,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Creates a membership or reactivates a
    previously deleted membership.

    Only organizational administrators can
    perform this operation.
    """
    business_id, admin_user_id = _validate_admin_context(
        current_user
    )

    _require_active_venue(venue_id, business_id)

    _require_eligible_user(
        payload.userId,
        business_id,
    )

    existing = get_venue_membership_by_user_and_venue(
        venue_id,
        payload.userId,
        business_id,
        include_deleted=True,
    )

    now = datetime.now(timezone.utc)

    if existing:
        if not existing.get("isDeleted", False):
            raise VenueMembershipConflictError(
                "User already has a membership in this venue."
            )

        updated = update_venue_membership_by_membership_id(
            existing["membershipId"],
            venue_id,
            business_id,
            {
                "role": payload.role,
                "isActive": True,
                "isDeleted": False,
                "updatedAt": now,
            },
            include_deleted=True,
        )

        if not updated:
            raise VenueMembershipConflictError(
                "Membership could not be reactivated."
            )

        return updated

    membership_document = {
        "membershipId": str(uuid.uuid4()),
        "businessId": business_id,
        "venueId": venue_id,
        "userId": payload.userId,
        "role": payload.role,
        "isActive": True,
        "isDeleted": False,
        "createdByUserId": admin_user_id,
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        return insert_venue_membership(
            membership_document
        )
    except DuplicateKeyError as exc:
        raise VenueMembershipConflictError(
            "User already has a membership in this venue."
        ) from exc


# ============================================================
# LIST MEMBERSHIPS BY VENUE
# ============================================================


def list_venue_memberships(
    venue_id: str,
    current_user: Dict[str, Any],
    *,
    only_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Lists memberships for one venue.
    Administrator only.
    """
    business_id, _ = _validate_admin_context(
        current_user
    )

    _require_active_venue(venue_id, business_id)

    return get_venue_memberships_by_venue_id(
        venue_id,
        business_id,
        only_active=only_active,
    )


# ============================================================
# GET MEMBERSHIP
# ============================================================


def get_venue_membership(
    venue_id: str,
    membership_id: str,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Retrieves one membership.
    Administrator only.
    """
    business_id, _ = _validate_admin_context(
        current_user
    )

    _require_active_venue(venue_id, business_id)

    membership = get_venue_membership_by_membership_id(
        membership_id,
        venue_id,
        business_id,
    )

    if not membership:
        raise LookupError("Venue membership not found.")

    return membership


# ============================================================
# UPDATE MEMBERSHIP
# ============================================================


def update_venue_membership(
    venue_id: str,
    membership_id: str,
    payload: VenueMembershipUpdateRequest,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Updates membership role or active status.
    Administrator only.
    """
    business_id, _ = _validate_admin_context(
        current_user
    )

    _require_active_venue(venue_id, business_id)

    update_fields = payload.model_dump(
        exclude_unset=True
    )

    if not update_fields:
        raise ValueError(
            "No membership fields provided for update."
        )

    if any(value is None for value in update_fields.values()):
        raise ValueError(
            "Membership fields cannot be null."
        )

    update_fields["updatedAt"] = datetime.now(
        timezone.utc
    )

    membership = update_venue_membership_by_membership_id(
        membership_id,
        venue_id,
        business_id,
        update_fields,
    )

    if not membership:
        raise LookupError("Venue membership not found.")

    return membership


# ============================================================
# DELETE MEMBERSHIP
# ============================================================


def delete_venue_membership(
    venue_id: str,
    membership_id: str,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Soft deletes a membership.
    Administrator only.
    """
    business_id, _ = _validate_admin_context(
        current_user
    )

    _require_active_venue(venue_id, business_id)

    membership = soft_delete_venue_membership_by_membership_id(
        membership_id,
        venue_id,
        business_id,
    )

    if not membership:
        raise LookupError("Venue membership not found.")

    return membership


# ============================================================
# LIST MY VENUES
# ============================================================


def list_my_venues(
    current_user: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Returns accessible venues for the authenticated user.

    Organizational administrators can access
    all active venues within their organization.

    Staff users can access only active venues
    with an active membership.
    """
    business_id, user_id = _validate_user_context(
        current_user
    )

    if current_user.get("role") == "admin":
        return get_venues_by_business_id(
            business_id,
            only_active=True,
        )

    if current_user.get("role") != "staff":
        return []

    memberships = get_venue_memberships_by_user_id(
        user_id,
        business_id,
        only_active=True,
    )

    venues = []

    for membership in memberships:
        venue = get_venue_by_venue_id(
            membership["venueId"],
            business_id,
        )

        if not venue:
            continue

        if not venue.get("isActive", False):
            continue

        venues.append(venue)

    return venues
