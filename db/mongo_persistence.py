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
USERS_COLLECTION = os.getenv("USERS_COLLECTION", "users")

PENDING_REGISTRATIONS_COLLECTION = os.getenv(
    "PENDING_REGISTRATIONS_COLLECTION",
    "pending_registrations",
)

MAF_RAG_QUERY_LOGS_COLLECTION = os.getenv(
    "MAF_RAG_QUERY_LOGS_COLLECTION",
    "maf_rag_query_logs",
)

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

def get_users_collection() -> Collection:
    """
    Returns the MongoDB collection used for authenticated users.
    """
    db = get_database()
    return db[USERS_COLLECTION]

def get_pending_registrations_collection() -> Collection:
    """
    Returns the MongoDB collection used for pending email registrations.
    """
    db = get_database()
    return db[PENDING_REGISTRATIONS_COLLECTION]

def get_maf_rag_query_logs_collection() -> Collection:
    """
    Returns the MongoDB collection used for MAF RAG query logs.
    """
    db = get_database()
    return db[MAF_RAG_QUERY_LOGS_COLLECTION]

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

def get_staff_by_staff_id(staff_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single staff member by its internal staffId.
    """
    try:
        collection = get_staff_collection()

        document = collection.find_one({
            "staffId": staff_id,
            "isDeleted": False,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving staff by staffId.") from exc

def update_staff_by_staff_id(
    staff_id: str,
    update_fields: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Updates a staff member by staffId and returns the updated document.
    """
    try:
        collection = get_staff_collection()

        document = collection.find_one_and_update(
            {"staffId": staff_id, "isDeleted": False, "isActive": True},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error updating staff by staffId.") from exc

def soft_delete_staff_by_staff_id(staff_id: str) -> Optional[Dict[str, Any]]:
    """
    Soft deletes a staff member by staffId and returns the updated document.
    """
    try:
        collection = get_staff_collection()

        document = collection.find_one_and_update(
            {"staffId": staff_id, "isDeleted": False},
            {
                "$set": {
                    "isDeleted": True,
                    "isActive": False,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error soft deleting staff by staffId.") from exc

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

def insert_user(user_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a user document into MongoDB and returns the inserted document.
    """
    try:
        collection = get_users_collection()

        result = collection.insert_one(user_document)

        inserted_document = collection.find_one({"_id": result.inserted_id})
        if not inserted_document:
            raise RuntimeError("User was inserted but could not be retrieved.")

        return serialize_mongo_document(inserted_document)

    except PyMongoError as exc:
        raise RuntimeError("Error inserting user into MongoDB.") from exc


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a non-deleted user by email.
    """
    try:
        collection = get_users_collection()

        document = collection.find_one({
            "email": email,
            "isDeleted": False,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving user by email.") from exc


def get_user_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a non-deleted user by userId.
    """
    try:
        collection = get_users_collection()

        document = collection.find_one({
            "userId": user_id,
            "isDeleted": False,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving user by userId.") from exc

def upsert_pending_registration(
    pending_document: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Creates or replaces a pending registration by email.

    Nota:
    Si el usuario solicita registro varias veces con el mismo correo,
    reemplazamos la solicitud pendiente anterior por la nueva.
    """
    try:
        collection = get_pending_registrations_collection()

        email = pending_document["email"]

        document = collection.find_one_and_replace(
            {"email": email},
            pending_document,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            document = collection.find_one({"email": email})

        if not document:
            raise RuntimeError("Pending registration was upserted but could not be retrieved.")

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error upserting pending registration into MongoDB.") from exc


def get_pending_registration_by_email(
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a pending registration by email.
    """
    try:
        collection = get_pending_registrations_collection()

        document = collection.find_one({
            "email": email,
            "usedAt": None,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving pending registration by email.") from exc


def mark_pending_registration_used(
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Marks a pending registration as used after successful verification.
    """
    try:
        collection = get_pending_registrations_collection()

        document = collection.find_one_and_update(
            {
                "email": email,
                "usedAt": None,
            },
            {
                "$set": {
                    "usedAt": datetime.now(timezone.utc),
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error marking pending registration as used.") from exc


def increment_pending_registration_attempts(
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Increments failed verification attempts for a pending registration.
    """
    try:
        collection = get_pending_registrations_collection()

        document = collection.find_one_and_update(
            {
                "email": email,
                "usedAt": None,
            },
            {
                "$inc": {
                    "attempts": 1,
                },
                "$set": {
                    "updatedAt": datetime.now(timezone.utc),
                },
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error incrementing pending registration attempts.") from exc


def delete_pending_registration_by_email(
    email: str,
) -> bool:
    """
    Deletes a pending registration by email.
    Useful for cleanup or re-registration flows.
    """
    try:
        collection = get_pending_registrations_collection()

        result = collection.delete_one({"email": email})

        return result.deleted_count > 0

    except PyMongoError as exc:
        raise RuntimeError("Error deleting pending registration.") from exc
    
def insert_maf_rag_query_log(log_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a MAF RAG query log document into MongoDB and returns the inserted document.

    Nota:
    Esta colección permite auditar preguntas, respuestas, fuentes recuperadas,
    confidence y trazabilidad del endpoint /xapity-maf/chat.
    """
    try:
        collection = get_maf_rag_query_logs_collection()

        result = collection.insert_one(log_document)

        inserted_document = collection.find_one({"_id": result.inserted_id})
        if not inserted_document:
            raise RuntimeError("MAF RAG query log was inserted but could not be retrieved.")

        return serialize_mongo_document(inserted_document)

    except PyMongoError as exc:
        raise RuntimeError("Error inserting MAF RAG query log into MongoDB.") from exc