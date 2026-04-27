# schemas/service.py

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ServiceCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=80)
    description: str = Field(..., min_length=3, max_length=300)
    category: str = Field(..., min_length=2, max_length=40)

    #OPERATIVOS------------------------
    durationMinutes: int = Field(...,gt=0)
    basePrice: int = Field(..., ge=0)
    beforeCareInstructions: Optional[str] = None
    afterCareInstructions: Optional[str] = None
    isBookableOnline: bool = True
    #COMERCIALES-----------------------
    includes: Optional[List[str]] = []
    products: Optional[List[str]] = []

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

    #OPERATIVOS-------------------------------
    durationMinutes: int
    basePrice: int
    beforeCareInstructions: Optional[str] = None
    afterCareInstructions: Optional[str] = None
    isBookableOnline: bool
    #COMERCIALES-------------------------------
    includes: List[str] = []
    products: List[str] = []

class ServicesListResponse(BaseModel):
    items: List[ServiceResponse]
    total: int

class ServiceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=80)
    description: Optional[str] = Field(None, min_length=3, max_length=300)
    category: Optional[str] = Field(None, min_length=2, max_length=40)
    isActive: Optional[bool] = None

