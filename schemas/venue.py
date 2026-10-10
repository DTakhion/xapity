
# schemas/venue.py
# ============================================================
# XAPITY ACCESS — VENUE SCHEMAS
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VenueAddress(BaseModel):
    street: Optional[str] = Field(default=None, max_length=200)
    commune: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=120)
    country: str = Field(default="CL", min_length=2, max_length=2)


class VenueCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    address: Optional[VenueAddress] = None
    timezone: str = Field(default="America/Santiago", max_length=100)


class VenueUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    address: Optional[VenueAddress] = None
    timezone: Optional[str] = Field(default=None, max_length=100)
    isActive: Optional[bool] = None


class VenueResponse(BaseModel):
    venueId: str
    businessId: str

    name: str
    description: Optional[str] = None
    address: Optional[VenueAddress] = None
    timezone: str

    isActive: bool
    isDeleted: bool

    createdByUserId: str
    createdAt: datetime
    updatedAt: datetime


class VenuesListResponse(BaseModel):
    venues: list[VenueResponse]
