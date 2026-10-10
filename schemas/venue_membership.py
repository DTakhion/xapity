
# schemas/venue_membership.py
# ============================================================
# XAPITY ACCESS — VENUE MEMBERSHIP SCHEMAS
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


VenueMembershipRole = Literal[
    "manager",
    "operator",
]


class VenueMembershipCreateRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    role: VenueMembershipRole = "operator"


class VenueMembershipUpdateRequest(BaseModel):
    role: Optional[VenueMembershipRole] = None
    isActive: Optional[bool] = None


class VenueMembershipResponse(BaseModel):
    membershipId: str

    businessId: str
    venueId: str
    userId: str

    role: VenueMembershipRole

    isActive: bool
    isDeleted: bool

    createdByUserId: str

    createdAt: datetime
    updatedAt: datetime


class VenueMembershipsListResponse(BaseModel):
    memberships: list[VenueMembershipResponse]
