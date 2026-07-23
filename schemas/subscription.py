# schemas/subscription.py

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# TYPES
# ============================================================

PlanCode = Literal[
    "trial",
    "startup",
    "corporate",
]

SubscriptionStatus = Literal[
    "active",
    "exhausted",
    "suspended",
    "expired",
]

SubscriptionPeriodType = Literal[
    "lifetime_trial",
    "monthly",
    "annual",
    "custom",
]

UsageEventStatus = Literal[
    "reserved",
    "completed",
    "released",
]

UsageResourceType = Literal[
    "question",
]

UsageFailureType = Literal[
    "technical_error",
    "timeout",
    "service_unavailable",
    "internal_error",
]


# ============================================================
# QUOTA
# ============================================================

class SubscriptionQuotaResponse(BaseModel):
    """
    Current quota status for an organization subscription.
    """

    limit: int = Field(..., ge=0)
    used: int = Field(..., ge=0)
    reserved: int = Field(..., ge=0)
    remaining: int = Field(..., ge=0)


# ============================================================
# SUBSCRIPTION
# ============================================================

class OrganizationSubscriptionResponse(BaseModel):
    """
    Public representation of an organization's subscription.
    """

    subscriptionId: str
    businessId: str

    planCode: PlanCode
    status: SubscriptionStatus

    quota: SubscriptionQuotaResponse

    periodType: SubscriptionPeriodType
    periodStart: datetime
    periodEnd: Optional[datetime] = None

    createdByUserId: Optional[str] = None

    createdAt: datetime
    updatedAt: datetime

    _id: Optional[str] = None


# ============================================================
# USAGE
# ============================================================

class OrganizationUsageEventResponse(BaseModel):
    """
    Public representation of an organization usage event.
    """

    usageId: str
    requestId: str

    businessId: str
    userId: str

    endpoint: str

    resourceType: UsageResourceType = "question"
    engineMode: Optional[str] = None

    credits: int = Field(default=1, ge=1)

    status: UsageEventStatus

    reservedAt: datetime
    completedAt: Optional[datetime] = None
    releasedAt: Optional[datetime] = None

    failureType: Optional[str] = None

    createdAt: datetime
    updatedAt: datetime

    _id: Optional[str] = None


# ============================================================
# API RESPONSES
# ============================================================

class OrganizationUsageResponse(BaseModel):
    """
    Subscription and quota summary returned by the usage endpoint.
    """

    businessId: str
    planCode: PlanCode
    status: SubscriptionStatus

    quota: SubscriptionQuotaResponse

    periodType: SubscriptionPeriodType
    periodStart: datetime
    periodEnd: Optional[datetime] = None


class CreditReservationResponse(BaseModel):
    """
    Result returned after successfully reserving one or more credits.
    """

    usageId: str
    requestId: str

    businessId: str
    userId: str

    credits: int = Field(..., ge=1)
    status: UsageEventStatus

    quota: SubscriptionQuotaResponse


class CreditCompletionResponse(BaseModel):
    """
    Result returned after confirming a reserved credit as consumed.
    """

    usageId: str
    requestId: str

    businessId: str
    userId: str

    credits: int = Field(..., ge=1)
    status: UsageEventStatus

    engineMode: Optional[str] = None

    quota: SubscriptionQuotaResponse


class CreditReleaseResponse(BaseModel):
    """
    Result returned after releasing a reserved credit due to a
    technical failure.
    """

    usageId: str
    requestId: str

    businessId: str
    userId: str

    credits: int = Field(..., ge=1)
    status: UsageEventStatus

    failureType: Optional[str] = None

    quota: SubscriptionQuotaResponse