# schemas/availability.py

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class AvailabilityRequest(BaseModel):
    """
    Request para consultar disponibilidad de agenda.

    Puede consultarse por:
    - serviceId obligatorio
    - fecha específica opcional
    - rango de fechas opcional
    - staffId opcional, si se quiere filtrar por un trabajador específico
    """

    serviceId: str = Field(..., min_length=1)
    staffId: Optional[str] = None

    # Opción A: consultar un día específico
    targetDate: Optional[date] = None

    # Opción B: consultar un rango de fechas
    startDate: Optional[date] = None
    endDate: Optional[date] = None


class AvailabilitySlot(BaseModel):
    """
    Bloque horario disponible calculado para un servicio y staff.
    """

    serviceId: str
    serviceName: str
    durationMinutes: int

    staffId: str
    staffName: str

    date: date
    start: str
    end: str


class AvailabilityResponse(BaseModel):
    """
    Respuesta con los slots disponibles.
    """

    serviceId: str
    serviceName: str
    durationMinutes: int

    staffId: Optional[str] = None
    staffName: Optional[str] = None

    startDate: Optional[date] = None
    endDate: Optional[date] = None
    targetDate: Optional[date] = None

    availableSlots: List[AvailabilitySlot] = Field(default_factory=list)
    total: int