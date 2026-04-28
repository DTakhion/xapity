from pydantic import BaseModel, EmailStr
from typing import List, Optional


# 🔹 Entrada
class StaffCreate(BaseModel):
    name: str
    role: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialties: Optional[List[str]] = []
    serviceIds: Optional[List[str]] = []
    notes: Optional[str] = None


# 🔹 Salida
class StaffResponse(BaseModel):
    staffId: str
    businessId: str
    name: str
    role: str
    email: Optional[str]
    phone: Optional[str]
    specialties: List[str]
    serviceIds: List[str]
    notes: Optional[str]
    isActive: bool
    isDeleted: bool
    createdAt: str
    updatedAt: str