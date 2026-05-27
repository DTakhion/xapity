# services/staff_repo.py

from __future__ import annotations

from typing import Any, Dict, List

from db.mongo_persistence import (
    insert_staff,
    get_staff,
    get_staff_by_staff_id,
    soft_delete_staff_by_staff_id,
)

async def create_staff(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persists a staff document into MongoDB and returns the inserted document.

    Nota de arquitectura:
    - Este archivo representa la capa repo/repository.
    - Su responsabilidad es intermediar entre el endpoint y la persistencia.
    - El endpoint no debería conocer detalles de MongoDB.
    """

    try:
        inserted_staff = insert_staff(document)
        return inserted_staff

    except Exception as exc:
        raise RuntimeError("Error creating staff in repository layer.") from exc


async def get_staff_list() -> List[Dict[str, Any]]:
    """
    Devuelve una lista de staff no eliminado desde MongoDB.
    """
    try:
        staff = get_staff(include_deleted=False)
        return staff

    except Exception as exc:
        raise RuntimeError("Error retrieving staff in repository layer.") from exc

async def get_staff_by_id(staff_id: str) -> Dict[str, Any] | None:
    """
    Devuelve un miembro específico del staff por staffId,
    validando que no esté eliminado.
    """
    try:
        staff = get_staff_by_staff_id(staff_id)
        return staff

    except Exception as exc:
        raise RuntimeError("Error retrieving staff by staffId in repository layer.") from exc

async def delete_staff(staff_id: str) -> Dict[str, Any] | None:
    """
    Aplica DELETE suave a un miembro del staff.
    """
    try:
        deleted_staff = soft_delete_staff_by_staff_id(staff_id)
        return deleted_staff

    except Exception as exc:
        raise RuntimeError("Error soft deleting staff in repository layer.") from exc