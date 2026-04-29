# db/mongo_persistence.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "xapity_db")
SERVICES_COLLECTION = os.getenv("SERVICES_COLLECTION", "services")
STAFF_COLLECTION = os.getenv("STAFF_COLLECTION", "staff")
APPOINTMENTS_COLLECTION = os.getenv("APPOINTMENTS_COLLECTION", "appointments")

_client: Optional[MongoClient] = None


def get_mongo_client() -> MongoClient:
    """
    Returns a singleton MongoDB client instance.
    """
    global _client

    if _client is None:
        _client = MongoClient(MONGO_URI)

    return _client


def get_database() -> Database:
    """
    Returns the configured MongoDB database.
    """
    client = get_mongo_client()
    return client[MONGO_DB]


def get_services_collection() -> Collection:
    """
    Returns the MongoDB collection used for services.
    """
    db = get_database()
    return db[SERVICES_COLLECTION]

def get_staff_collection() -> Collection:
    """
    Returns the MongoDB collection used for staff.
    """
    db = get_database()
    return db[STAFF_COLLECTION]

def get_appointments_collection() -> Collection:
    """
    Returns the MongoDB collection used for appointments.
    """
    db = get_database()
    return db[APPOINTMENTS_COLLECTION]

def serialize_mongo_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts MongoDB ObjectId fields to string so they can be returned by the API.
    """
    if not document:
        return document

    serialized = dict(document)

    if "_id" in serialized:
        serialized["_id"] = str(serialized["_id"])

    return serialized


   
def insert_service(service_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a service document into MongoDB and returns the inserted document.

    Nota:
    El documento ya viene validado desde schemas/service.py y construido
    desde api/main.py. Esta capa no filtra campos, por lo que soporta
    nuevos atributos operativos/comerciales sin cambios adicionales.
    """
    try:
        collection = get_services_collection()

        result = collection.insert_one(service_document)

        inserted_document = collection.find_one({"_id": result.inserted_id})
        if not inserted_document:
            raise RuntimeError("Service was inserted but could not be retrieved.")

        return serialize_mongo_document(inserted_document)

    except PyMongoError as exc:
        raise RuntimeError("Error inserting service into MongoDB.") from exc


def get_services(
    *,
    include_deleted: bool = False,
    only_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves services from MongoDB.

    Parameters:
        include_deleted:
            If False, excludes documents with isDeleted=True.
        only_active:
            If True, returns only active services.
            If False, returns only inactive services.
            If None, does not filter by isActive.

    Returns:
        A list of serialized service documents.
    """
    try:
        collection = get_services_collection()

        query: Dict[str, Any] = {}

        if not include_deleted:
            query["isDeleted"] = False

        if only_active is not None:
            query["isActive"] = only_active

        documents = collection.find(query).sort("createdAt", -1)

        return [serialize_mongo_document(doc) for doc in documents]

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving services from MongoDB.") from exc


def get_service_by_service_id(service_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single service by its internal serviceId.
    """
    try:
        collection = get_services_collection()
        #document = collection.find_one({"serviceId": service_id})
        document = collection.find_one({"serviceId": service_id, "isDeleted": False})

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving service by serviceId.") from exc


def service_name_exists(name: str, business_id: str) -> bool:
    """
    Checks if a non-deleted service with the same name already exists
    for the given business.
    """
    try:
        collection = get_services_collection()

        query = {
            "name": name,
            "businessId": business_id,
            "isDeleted": False,
        }

        existing = collection.find_one(query)
        return existing is not None

    except PyMongoError as exc:
        raise RuntimeError("Error checking if service name exists.") from exc

def update_service_by_service_id(
    service_id: str,
    update_fields: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Updates a service by serviceId and returns the updated document.

    Nota:
    update_fields puede incluir campos base, operativos o comerciales.
    La validación de campos permitidos debe ocurrir en la capa schema/API.
    """
    try:
        collection = get_services_collection()

        document = collection.find_one_and_update(
            {"serviceId": service_id, "isDeleted": False},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error updating service by serviceId.") from exc

def soft_delete_service_by_service_id(service_id: str) -> Optional[Dict[str, Any]]:
    """
    Soft deletes a service by serviceId and returns the updated document.
    """
    try:
        collection = get_services_collection()

        document = collection.find_one_and_update(
            {"serviceId": service_id, "isDeleted": False},
            {
                "$set": {
                    "isDeleted": True,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error soft deleting service by serviceId.") from exc

def insert_staff(staff_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a staff document into MongoDB and returns the inserted document.
    """
    try:
        collection = get_staff_collection()

        result = collection.insert_one(staff_document)

        inserted_document = collection.find_one({"_id": result.inserted_id})
        if not inserted_document:
            raise RuntimeError("Staff was inserted but could not be retrieved.")

        return serialize_mongo_document(inserted_document)

    except PyMongoError as exc:
        raise RuntimeError("Error inserting staff into MongoDB.") from exc

def get_staff(
    *,
    include_deleted: bool = False,
    only_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves staff from MongoDB.
    """
    try:
        collection = get_staff_collection()

        query: Dict[str, Any] = {}

        if not include_deleted:
            query["isDeleted"] = False

        if only_active is not None:
            query["isActive"] = only_active

        documents = collection.find(query).sort("createdAt", -1)

        return [serialize_mongo_document(doc) for doc in documents]

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving staff from MongoDB.") from exc

def insert_appointment(appointment_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts an appointment document into MongoDB and returns the inserted document.
    """
    try:
        collection = get_appointments_collection()

        result = collection.insert_one(appointment_document)

        inserted_document = collection.find_one({"_id": result.inserted_id})
        if not inserted_document:
            raise RuntimeError("Appointment was inserted but could not be retrieved.")

        return serialize_mongo_document(inserted_document)

    except PyMongoError as exc:
        raise RuntimeError("Error inserting appointment into MongoDB.") from exc


def get_appointments(
    *,
    include_deleted: bool = False,
    business_id: Optional[str] = None,
    staff_id: Optional[str] = None,
    service_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves appointments from MongoDB.
    """
    try:
        collection = get_appointments_collection()

        query: Dict[str, Any] = {}

        if not include_deleted:
            query["isDeleted"] = False

        if business_id is not None:
            query["businessId"] = business_id

        if staff_id is not None:
            query["staffId"] = staff_id

        if service_id is not None:
            query["serviceId"] = service_id

        documents = collection.find(query).sort("createdAt", -1)

        return [serialize_mongo_document(doc) for doc in documents]

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving appointments from MongoDB.") from exc


def get_appointment_by_appointment_id(
    appointment_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single appointment by appointmentId.
    """
    try:
        collection = get_appointments_collection()

        document = collection.find_one(
            {"appointmentId": appointment_id, "isDeleted": False}
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving appointment by appointmentId.") from exc


def update_appointment_by_appointment_id(
    appointment_id: str,
    update_fields: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Updates an appointment by appointmentId and returns the updated document.
    """
    try:
        collection = get_appointments_collection()

        document = collection.find_one_and_update(
            {"appointmentId": appointment_id, "isDeleted": False},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error updating appointment by appointmentId.") from exc


def soft_delete_appointment_by_appointment_id(
    appointment_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Soft deletes an appointment by appointmentId and returns the updated document.
    """
    try:
        collection = get_appointments_collection()

        document = collection.find_one_and_update(
            {"appointmentId": appointment_id, "isDeleted": False},
            {
                "$set": {
                    "isDeleted": True,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error soft deleting appointment by appointmentId.") from exc