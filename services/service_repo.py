# services/service_repo.py

from __future__ import annotations

from typing import Any, Dict, List

# NUEVO:
# El repo no inserta directo con pymongo aquí mismo.
# Reutiliza la capa de persistencia central del proyecto.
from db.mongo_persistence import insert_service, get_services, update_service_by_service_id, soft_delete_service_by_service_id

async def create_service(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persists a service document into MongoDB and returns the inserted document.

    Nota de arquitectura:
    - Este archivo representa la capa "repo" (repository pattern),
      no el repositorio Git.
    - Su responsabilidad es intermediar entre el endpoint y la persistencia.
    - El endpoint no debería conocer detalles de MongoDB.
    """

    try:
        # AJUSTADO:
        # Antes esto podía estar como placeholder (por ejemplo, un print).
        # Ahora el repo realmente delega la inserción a mongo_persistence.
        inserted_service = insert_service(document)

        # Se retorna el documento insertado ya serializado,
        # incluyendo _id como string si corresponde.
        return inserted_service

    except Exception as exc:
        # NUEVO:
        # Dejamos un error controlado y entendible para la capa superior.
        # Más adelante esto podría mejorarse con logging estructurado.
        raise RuntimeError("Error creating service in repository layer.") from exc


async def get_services_list() -> List[Dict[str, Any]]:
    """
    Devuelve una lista de servicios no eliminados desde MongoDB.
    """
    try:
        services = get_services(include_deleted=False)
        return services
    except Exception as exc:
        raise RuntimeError("Error retrieving services in repository layer.") from exc

async def update_service(
    service_id: str,
    update_fields: Dict[str, Any],
) -> Dict[str, Any] | None:
    """
    Updates a service in MongoDB and returns the updated document.
    """
    try:
        updated_service = update_service_by_service_id(service_id, update_fields)
        return updated_service

    except Exception as exc:
        raise RuntimeError("Error updating service in repository layer.") from exc

async def delete_service(service_id: str) -> Dict[str, Any] | None:
    """
    Soft deletes a service in MongoDB and returns the updated document.
    """
    try:
        deleted_service = soft_delete_service_by_service_id(service_id)
        return deleted_service

    except Exception as exc:
        raise RuntimeError("Error deleting service in repository layer.") from exc