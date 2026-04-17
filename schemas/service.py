# schemas/service.py

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ServiceCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=80)
    description: str = Field(..., min_length=3, max_length=300)
    category: str = Field(..., min_length=2, max_length=40)


class ServiceResponse(BaseModel):
    serviceId: str
    businessId: str
    name: str
    slug: str
    description: str
    category: str
    tags: List[str]
    isActive: bool
    isDeleted: bool
    createdAt: datetime
    updatedAt: datetime
    _id: Optional[str] = None


class ServicesListResponse(BaseModel):
    items: List[ServiceResponse]
    total: int

class ServiceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=80)
    description: Optional[str] = Field(None, min_length=3, max_length=300)
    category: Optional[str] = Field(None, min_length=2, max_length=40)
    isActive: Optional[bool] = None