# schemas/appointment.py

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AppointmentCreateRequest(BaseModel):
    """
    Request para crear una reserva/agendamiento real.

    Importante:
    - El frontend solo envía date + start.
    - El backend calcula end usando durationMinutes del servicio.
    - Esta entidad sí se guarda en Mongo.
    """

    serviceId: str = Field(..., min_length=1)
    staffId: str = Field(..., min_length=1)

    customerName: str = Field(..., min_length=2, max_length=120)
    customerPhone: Optional[str] = None
    customerEmail: Optional[EmailStr] = None

    date: date
    start: str = Field(..., min_length=5, max_length=5)

    notes: Optional[str] = None


class AppointmentUpdateRequest(BaseModel):
    """
    Request para actualización parcial de una reserva.

    None = no modificar.

    Nota:
    - En creación, end lo calcula backend.
    - En actualización, por ahora mantenemos start/end opcionales
      para permitir ajustes administrativos.
    """

    serviceId: Optional[str] = Field(None, min_length=1)
    staffId: Optional[str] = Field(None, min_length=1)

    customerName: Optional[str] = Field(None, min_length=2, max_length=120)
    customerPhone: Optional[str] = None
    customerEmail: Optional[EmailStr] = None

    date: Optional[date] = None
    start: Optional[str] = Field(None, min_length=5, max_length=5)
    end: Optional[str] = Field(None, min_length=5, max_length=5)

    status: Optional[str] = None
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    """
    Respuesta de una reserva/agendamiento.

    Incluye datos internos generados por backend.
    """

    appointmentId: str
    businessId: str

    serviceId: str
    serviceName: Optional[str] = None

    staffId: str
    staffName: Optional[str] = None

    customerName: str
    customerPhone: Optional[str] = None
    customerEmail: Optional[EmailStr] = None

    date: date
    start: str
    end: str

    status: str = "scheduled"
    notes: Optional[str] = None

    isDeleted: bool = False
    createdAt: datetime
    updatedAt: datetime

    _id: Optional[str] = None


class AppointmentsListResponse(BaseModel):
    items: list[AppointmentResponse]
    total: int