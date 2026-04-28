# schemas/service.py

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

class ServiceCreateRequest(BaseModel):
    # IDENTIDAD BASE DEL SERVICIO
    name: str = Field(..., min_length=3, max_length=80)
    description: str = Field(..., min_length=3, max_length=300)
    category: str = Field(..., min_length=2, max_length=40)

    # ==================================================
    # OPERATIVOS
    # ==================================================

    # AJUSTADO:
    # Antes estaba obligatorio ahora opcional.
    # Se cambia a default=60 para mantener compatibilidad con frontend
    durationMinutes: int = Field(60, gt=0)

    # AJUSTADO:
    # Se deja default=0 para no romper integraciones actuales.
    basePrice: int = Field(0, ge=0)

    # Opcionales por definición, 
    # no todos los servicios requieren instrucciones.
    beforeCareInstructions: Optional[str] = None
    afterCareInstructions: Optional[str] = None

    # Default True:
    # comportamiento esperado para MVP salvo casos especiales.
    isBookableOnline: bool = True

    # ==================================================
    # COMERCIALES
    # ==================================================

    # AJUSTADO:
    # Se usa default_factory=list en vez de []
    # para evitar listas mutables compartidas entre instancias.
    includes: List[str] = Field(default_factory=list)

    # AJUSTADO:
    # misma razón técnica que includes.
    products: List[str] = Field(default_factory=list)

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

    # OPERATIVOS
    durationMinutes: int
    basePrice: int
    beforeCareInstructions: Optional[str] = None
    afterCareInstructions: Optional[str] = None
    isBookableOnline: bool

    # COMERCIALES
    # AJUSTADO:
    # Se usa default_factory=list en vez de []
    # para evitar listas mutables compartidas entre instancias.
    includes: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)

class ServicesListResponse(BaseModel):
    items: List[ServiceResponse]
    total: int
    
class ServiceUpdateRequest(BaseModel):
    # ==================================================
    # CAMPOS BASE YA EXISTENTES
    # ==================================================

    # Todos opcionales:
    # update parcial tipo PATCH semántico.
    name: Optional[str] = Field(None, min_length=3, max_length=80)
    description: Optional[str] = Field(None, min_length=3, max_length=300)
    category: Optional[str] = Field(None, min_length=2, max_length=40)
    isActive: Optional[bool] = None

    # ==================================================
    # NUEVOS CAMPOS OPERATIVOS
    # ==================================================

    # Optional None:
    # si no viene en request, no se modifica en Mongo.
    durationMinutes: Optional[int] = Field(None, gt=0)
    basePrice: Optional[int] = Field(None, ge=0)

    beforeCareInstructions: Optional[str] = None
    afterCareInstructions: Optional[str] = None
    isBookableOnline: Optional[bool] = None

    # ==================================================
    # NUEVOS CAMPOS COMERCIALES
    # ==================================================

    # Optional None:
    # diferencia importante entre:
    # None = no actualizar
    # [] = limpiar lista explícitamente
    includes: Optional[List[str]] = None
    products: Optional[List[str]] = None



