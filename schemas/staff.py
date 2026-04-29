# schemas/staff.py

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# Comentarios
# ============================================================
# 1. Se cambia StaffCreate -> StaffCreateRequest para mantener
#    consistencia con schemas/service.py, donde usamos nombres
#    tipo ServiceCreateRequest.
#
# 2. Se evita usar Optional[List[str]] = [].
#    Aunque funciona, no es buena práctica usar listas mutables
#    como valor por defecto.
#    Mejor: Field(default_factory=list).
#
# 3. Se cambia createdAt / updatedAt desde str a datetime.
#    Esto mantiene mejor consistencia semántica con timestamps.
#
# 4. Se agrega workingHours para soportar disponibilidad semanal.
#    La estructura permite definir lunes, martes, miércoles, etc.
#
# 5. Cada día puede tener múltiples bloques horarios.
#    Ejemplo:
#    lunes 09:00-14:00 y 15:00-18:00.
#
# 6. Por ahora start/end quedan como str en formato "HH:MM".
#    Más adelante podríamos agregar validación estricta con regex
#    o usar tipos específicos si fuera necesario.
#
# 7. Los puntos 4, 5 y 6 no estaban considerados en la tarea de Trello actual, sin embargo, 
#    me parecio necesario incorporarlos desde ya. 
# ============================================================


class WorkingBlock(BaseModel):
    """
    Representa una ventana de trabajo dentro de un día.

    Ejemplo:
    {
        "start": "09:00",
        "end": "14:00"
    }
    """

    start: str
    end: str


class WorkingDay(BaseModel):
    """
    Representa la disponibilidad de un día específico.

    Permite:
    - marcar si ese día trabaja o no
    - definir una o más ventanas horarias
    """

    isWorking: bool = True
    blocks: List[WorkingBlock] = Field(default_factory=list)


class WorkingHours(BaseModel):
    """
    Representa la disponibilidad semanal del staff.

    Cada día es opcional. Si un día viene en None,
    se interpreta como no definido todavía.
    """

    monday: Optional[WorkingDay] = None
    tuesday: Optional[WorkingDay] = None
    wednesday: Optional[WorkingDay] = None
    thursday: Optional[WorkingDay] = None
    friday: Optional[WorkingDay] = None
    saturday: Optional[WorkingDay] = None
    sunday: Optional[WorkingDay] = None


# Entrada
class StaffCreateRequest(BaseModel):
    """
    Schema usado para crear un nuevo miembro del staff.

    Campos obligatorios:
    - name
    - role

    Campos opcionales:
    - email
    - phone
    - specialties
    - serviceIds
    - notes
    - workingHours
    """

    name: str
    role: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialties: List[str] = Field(default_factory=list)
    serviceIds: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    workingHours: Optional[WorkingHours] = None


# Salida
class StaffResponse(BaseModel):
    """
    Schema usado para responder al frontend después de crear,
    listar o consultar un staff.

    Incluye campos internos generados por backend:
    - staffId
    - businessId
    - isActive
    - isDeleted
    - createdAt
    - updatedAt
    """

    staffId: str
    businessId: str
    name: str
    role: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialties: List[str] = Field(default_factory=list)
    serviceIds: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    workingHours: Optional[WorkingHours] = None
    isActive: bool
    isDeleted: bool
    createdAt: datetime
    updatedAt: datetime