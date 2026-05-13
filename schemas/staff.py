# schemas/staff.py

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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

    @field_validator("start", "end")
    @classmethod
    def validate_hh_mm(cls, value: str) -> str:
        """
        Valida que las horas vengan en formato HH:MM.
        Evita valores placeholder de Swagger como 'string'.
        """

        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            raise ValueError("La hora debe venir en formato HH:MM, por ejemplo '09:00'.")

        return value

    @model_validator(mode="after")
    def validate_start_before_end(self):
        """
        Valida que el bloque tenga sentido horario:
        start debe ser menor que end.
        """

        start_time = datetime.strptime(self.start, "%H:%M").time()
        end_time = datetime.strptime(self.end, "%H:%M").time()

        if start_time >= end_time:
            raise ValueError("La hora start debe ser menor que la hora end.")

        return self


class WorkingDay(BaseModel):
    """
    Representa la disponibilidad de un día específico.

    Reglas:
    - Si isWorking=False, se limpian los bloques automáticamente.
    - Si isWorking=True, debe existir al menos un bloque válido.
    - Los bloques no pueden solaparse.
    """

    isWorking: bool = False
    blocks: List[WorkingBlock] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def clean_blocks_when_not_working(cls, data):
        """
        Limpia bloques cuando el día no es laboral.

        Esto evita errores típicos de Swagger/frontend como:
        {
            "isWorking": false,
            "blocks": [{"start": "string", "end": "string"}]
        }
        """

        if isinstance(data, dict) and data.get("isWorking") is False:
            data["blocks"] = []

        return data

    @model_validator(mode="after")
    def validate_working_day_consistency(self):
        """
        Valida consistencia semántica del día laboral.
        """

        if self.isWorking and not self.blocks:
            raise ValueError(
                "Si isWorking es true, debe existir al menos un bloque horario."
            )

        sorted_blocks = sorted(
            self.blocks,
            key=lambda block: datetime.strptime(block.start, "%H:%M").time(),
        )

        for previous_block, current_block in zip(sorted_blocks, sorted_blocks[1:]):
            previous_end = datetime.strptime(previous_block.end, "%H:%M").time()
            current_start = datetime.strptime(current_block.start, "%H:%M").time()

            if current_start < previous_end:
                raise ValueError(
                    "Los bloques horarios no pueden solaparse dentro del mismo día."
                )

        self.blocks = sorted_blocks
        return self


class WorkingHours(BaseModel):
    """
    Representa la disponibilidad semanal del staff.

    Cada día queda definido por defecto como no laboral.
    Esto evita None y evita placeholders tipo 'string'.
    """

    monday: WorkingDay = Field(default_factory=WorkingDay)
    tuesday: WorkingDay = Field(default_factory=WorkingDay)
    wednesday: WorkingDay = Field(default_factory=WorkingDay)
    thursday: WorkingDay = Field(default_factory=WorkingDay)
    friday: WorkingDay = Field(default_factory=WorkingDay)
    saturday: WorkingDay = Field(default_factory=WorkingDay)
    sunday: WorkingDay = Field(default_factory=WorkingDay)


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