# services/appointment_repo.py

from __future__ import annotations

from typing import Any, Dict, List

from db.mongo_persistence import (
    insert_appointment,
    get_appointments,
    get_appointment_by_appointment_id,
    update_appointment_by_appointment_id,
    soft_delete_appointment_by_appointment_id,
)


async def create_appointment(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persists an appointment document into MongoDB and returns the inserted document.
    """
    try:
        inserted_appointment = insert_appointment(document)
        return inserted_appointment

    except Exception as exc:
        raise RuntimeError("Error creating appointment in repository layer.") from exc


async def get_appointments_list() -> List[Dict[str, Any]]:
    """
    Returns non-deleted appointments from MongoDB.
    """
    try:
        appointments = get_appointments(include_deleted=False)
        return appointments

    except Exception as exc:
        raise RuntimeError("Error retrieving appointments in repository layer.") from exc


async def get_appointment(appointment_id: str) -> Dict[str, Any] | None:
    """
    Returns a single appointment by appointmentId.
    """
    try:
        appointment = get_appointment_by_appointment_id(appointment_id)
        return appointment

    except Exception as exc:
        raise RuntimeError("Error retrieving appointment in repository layer.") from exc


async def update_appointment(
    appointment_id: str,
    update_fields: Dict[str, Any],
) -> Dict[str, Any] | None:
    """
    Updates an appointment in MongoDB and returns the updated document.
    """
    try:
        updated_appointment = update_appointment_by_appointment_id(
            appointment_id,
            update_fields,
        )
        return updated_appointment

    except Exception as exc:
        raise RuntimeError("Error updating appointment in repository layer.") from exc


async def delete_appointment(appointment_id: str) -> Dict[str, Any] | None:
    """
    Soft deletes an appointment in MongoDB and returns the updated document.
    """
    try:
        deleted_appointment = soft_delete_appointment_by_appointment_id(
            appointment_id
        )
        return deleted_appointment

    except Exception as exc:
        raise RuntimeError("Error deleting appointment in repository layer.") from exc