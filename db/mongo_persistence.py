# db/mongo_persistence.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError, DuplicateKeyError

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


# ============================================================
# XAPITY ACCESS — GLOBAL VISITOR REGISTRATIONS
# ============================================================

VISITOR_PENDING_REGISTRATIONS_COLLECTION = os.getenv(
    "VISITOR_PENDING_REGISTRATIONS_COLLECTION",
    "visitor_pending_registrations",
)


MAF_RAG_QUERY_LOGS_COLLECTION = os.getenv(
    "MAF_RAG_QUERY_LOGS_COLLECTION",
    "maf_rag_query_logs",
)

PASSWORD_RESET_CODES_COLLECTION = os.getenv(
    "PASSWORD_RESET_CODES_COLLECTION",
    "password_reset_codes",
)

USER_INVITATIONS_COLLECTION = os.getenv(
    "USER_INVITATIONS_COLLECTION",
    "user_invitations",
)


# ============================================================
# XAPITY ACCESS — ADMIN PROVISIONING
# ============================================================

ADMIN_PROVISIONING_TOKENS_COLLECTION = os.getenv(
    "ADMIN_PROVISIONING_TOKENS_COLLECTION",
    "admin_provisioning_tokens",
)

# ============================================================
# XAPITY ACCESS — VENUES
# ============================================================

VENUES_COLLECTION = os.getenv(
    "VENUES_COLLECTION",
    "venues",
)

# ============================================================
# XAPITY ACCESS — VENUE MEMBERSHIPS
# ============================================================

VENUE_MEMBERSHIPS_COLLECTION = os.getenv(
    "VENUE_MEMBERSHIPS_COLLECTION",
    "venue_memberships",
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


def get_visitor_pending_registrations_collection() -> Collection:
    """
    Returns the MongoDB collection used for
    autonomous global visitor registrations.
    """
    db = get_database()
    return db[VISITOR_PENDING_REGISTRATIONS_COLLECTION]


def initialize_visitor_pending_registrations_storage() -> None:
    """
    Creates indexes for visitor registration requests.
    """
    try:
        collection = get_visitor_pending_registrations_collection()

        collection.create_index(
            "email",
            unique=True,
            name="ux_visitor_pending_email",
        )

    except PyMongoError as exc:
        raise RuntimeError(
            "Error initializing visitor registration storage."
        ) from exc


def get_password_reset_codes_collection() -> Collection:
    """
    Returns the MongoDB collection used for password reset codes.
    """
    db = get_database()
    return db[PASSWORD_RESET_CODES_COLLECTION]

def get_user_invitations_collection() -> Collection:
    """
    Returns the MongoDB collection used for user invitations.
    """
    db = get_database()
    return db[USER_INVITATIONS_COLLECTION]


def get_admin_provisioning_tokens_collection() -> Collection:
    """
    Returns the collection used for controlled
    administrator provisioning.
    """
    db = get_database()
    return db[ADMIN_PROVISIONING_TOKENS_COLLECTION]

def get_venues_collection() -> Collection:
    """
    Returns the MongoDB collection used for Xapity venues.
    """
    db = get_database()
    return db[VENUES_COLLECTION]

def get_venue_memberships_collection() -> Collection:
    """
    Returns the MongoDB collection used for
    Xapity venue memberships.
    """
    db = get_database()
    return db[VENUE_MEMBERSHIPS_COLLECTION]


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



# ============================================================
# XAPITY ACCESS — GLOBAL USER IDENTITY INDEXES
# ============================================================

def initialize_global_users_storage() -> None:
    """
    Creates unique indexes for global Xapity identities.

    Run only after auditing existing users for duplicates.
    """
    try:
        collection = get_users_collection()

        collection.create_index(
            "userId",
            unique=True,
            name="ux_global_users_user_id",
        )

        collection.create_index(
            "email",
            unique=True,
            name="ux_global_users_email",
        )

        collection.create_index(
            "rut",
            unique=True,
            partialFilterExpression={
                "rut": {"$type": "string"},
            },
            name="ux_global_users_rut",
        )

    except PyMongoError as exc:
        raise RuntimeError(
            "Error initializing global users storage."
        ) from exc


def insert_user(user_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a user document into MongoDB.

    Preserves DuplicateKeyError so the service layer
    can handle identity conflicts explicitly.
    """
    try:
        collection = get_users_collection()

        result = collection.insert_one(user_document)

        inserted_document = collection.find_one({
            "_id": result.inserted_id,
        })

        if not inserted_document:
            raise RuntimeError(
                "User was inserted but could not be retrieved."
            )

        return serialize_mongo_document(inserted_document)

    except DuplicateKeyError:
        raise

    except PyMongoError as exc:
        raise RuntimeError(
            "Error inserting user into MongoDB."
        ) from exc

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

def upsert_password_reset_code(
    reset_document: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Creates or replaces a password reset code by email.
    """
    try:
        collection = get_password_reset_codes_collection()

        email = reset_document["email"]

        document = collection.find_one_and_replace(
            {"email": email},
            reset_document,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            document = collection.find_one({"email": email})

        if not document:
            raise RuntimeError("Password reset code was upserted but could not be retrieved.")

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error upserting password reset code into MongoDB.") from exc


def get_password_reset_code_by_email(
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves an active password reset code by email.
    """
    try:
        collection = get_password_reset_codes_collection()

        document = collection.find_one({
            "email": email,
            "usedAt": None,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving password reset code by email.") from exc


def mark_password_reset_code_used(
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Marks a password reset code as used after successful password reset.
    """
    try:
        collection = get_password_reset_codes_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "email": email,
                "usedAt": None,
            },
            {
                "$set": {
                    "usedAt": now,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error marking password reset code as used.") from exc


def increment_password_reset_attempts(
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Increments failed verification attempts for a password reset code.
    """
    try:
        collection = get_password_reset_codes_collection()

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
        raise RuntimeError("Error incrementing password reset attempts.") from exc


def update_user_password_by_email(
    email: str,
    password_hash: str,
) -> Optional[Dict[str, Any]]:
    """
    Updates a non-deleted user's password hash by email.
    """
    try:
        collection = get_users_collection()

        document = collection.find_one_and_update(
            {
                "email": email,
                "isDeleted": False,
            },
            {
                "$set": {
                    "passwordHash": password_hash,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error updating user password by email.") from exc
    
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

def insert_user_invitation(invitation_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a user invitation document into MongoDB.
    """
    try:
        collection = get_user_invitations_collection()

        result = collection.insert_one(invitation_document)

        inserted_document = collection.find_one({"_id": result.inserted_id})
        if not inserted_document:
            raise RuntimeError("User invitation was inserted but could not be retrieved.")

        return serialize_mongo_document(inserted_document)

    except PyMongoError as exc:
        raise RuntimeError("Error inserting user invitation into MongoDB.") from exc

def get_user_invitation_by_token(
    token: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves an active user invitation by token.
    """
    try:
        collection = get_user_invitations_collection()

        document = collection.find_one({
            "token": token,
            "usedAt": None,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error retrieving user invitation by token.") from exc


def mark_user_invitation_used(
    token: str,
) -> Optional[Dict[str, Any]]:
    """
    Marks a user invitation as used after successful acceptance.
    """
    try:
        collection = get_user_invitations_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "token": token,
                "usedAt": None,
            },
            {
                "$set": {
                    "usedAt": now,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError("Error marking user invitation as used.") from exc


# ============================================================
# XAPITY ACCESS — ADMIN PROVISIONING TOKENS
# ============================================================

def initialize_admin_provisioning_storage() -> None:
    """
    Creates indexes for administrator provisioning tokens.
    """
    try:
        collection = get_admin_provisioning_tokens_collection()

        collection.create_index(
            "tokenHash",
            unique=True,
        )

        collection.create_index(
            "email",
        )

    except PyMongoError as exc:
        raise RuntimeError(
            "Error initializing admin provisioning storage."
        ) from exc


def insert_admin_provisioning_token(
    token_document: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Stores an administrator provisioning authorization.

    The document must contain a tokenHash, not a raw token.
    """
    try:
        collection = get_admin_provisioning_tokens_collection()

        result = collection.insert_one(token_document)

        document = collection.find_one(
            {"_id": result.inserted_id}
        )

        if not document:
            raise RuntimeError(
                "Admin provisioning token could not be retrieved."
            )

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error inserting admin provisioning token."
        ) from exc


def get_admin_provisioning_token(
    token_hash: str,
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a valid, unused administrator authorization.
    """
    try:
        collection = get_admin_provisioning_tokens_collection()

        document = collection.find_one({
            "tokenHash": token_hash,
            "email": email.strip().lower(),
            "usedAt": None,
            "expiresAt": {
                "$gt": datetime.now(timezone.utc),
            },
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving admin provisioning token."
        ) from exc


def mark_admin_provisioning_token_used(
    token_hash: str,
    email: str,
) -> Optional[Dict[str, Any]]:
    """
    Atomically marks a valid provisioning token as used.
    """
    try:
        collection = get_admin_provisioning_tokens_collection()
        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "tokenHash": token_hash,
                "email": email.strip().lower(),
                "usedAt": None,
                "expiresAt": {"$gt": now},
            },
            {
                "$set": {
                    "usedAt": now,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error consuming admin provisioning token."
        ) from exc


# ============================================================
# XAPITY ACCESS — VENUES PERSISTENCE
# ============================================================


def initialize_venues_storage() -> None:
    """
    Creates MongoDB indexes for venues.
    """
    try:
        collection = get_venues_collection()

        collection.create_index(
            "venueId",
            unique=True,
        )

        collection.create_index(
            [
                ("businessId", 1),
                ("isDeleted", 1),
                ("createdAt", -1),
            ]
        )

    except PyMongoError as exc:
        raise RuntimeError(
            "Error initializing venues storage."
        ) from exc


def insert_venue(
    venue_document: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Inserts a venue document into MongoDB.
    """
    try:
        collection = get_venues_collection()

        result = collection.insert_one(venue_document)

        document = collection.find_one(
            {"_id": result.inserted_id}
        )

        if not document:
            raise RuntimeError(
                "Venue was inserted but could not be retrieved."
            )

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error inserting venue into MongoDB."
        ) from exc


def get_venues_by_business_id(
    business_id: str,
    *,
    include_deleted: bool = False,
    only_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves venues belonging to one organization.
    """
    try:
        collection = get_venues_collection()

        query: Dict[str, Any] = {
            "businessId": business_id,
        }

        if not include_deleted:
            query["isDeleted"] = False

        if only_active is not None:
            query["isActive"] = only_active

        documents = collection.find(query).sort(
            "createdAt",
            -1,
        )

        return [
            serialize_mongo_document(doc)
            for doc in documents
        ]

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving venues by businessId."
        ) from exc


def get_venue_by_venue_id(
    venue_id: str,
    business_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a non-deleted venue within its organization.

    The businessId condition prevents cross-organization
    access at the persistence layer.
    """
    try:
        collection = get_venues_collection()

        document = collection.find_one({
            "venueId": venue_id,
            "businessId": business_id,
            "isDeleted": False,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving venue by venueId."
        ) from exc


def update_venue_by_venue_id(
    venue_id: str,
    business_id: str,
    update_fields: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Updates a non-deleted venue within its organization.

    Only permitted fields should be supplied by
    the venue service layer.
    """
    try:
        collection = get_venues_collection()

        document = collection.find_one_and_update(
            {
                "venueId": venue_id,
                "businessId": business_id,
                "isDeleted": False,
            },
            {
                "$set": update_fields,
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error updating venue by venueId."
        ) from exc


def soft_delete_venue_by_venue_id(
    venue_id: str,
    business_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Soft deletes a venue within its organization.
    """
    try:
        collection = get_venues_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "venueId": venue_id,
                "businessId": business_id,
                "isDeleted": False,
            },
            {
                "$set": {
                    "isDeleted": True,
                    "isActive": False,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error soft deleting venue by venueId."
        ) from exc


# ============================================================
# XAPITY ACCESS — VENUE MEMBERSHIPS PERSISTENCE
# ============================================================


def initialize_venue_memberships_storage() -> None:
    """
    Creates MongoDB indexes for venue memberships.

    One membership document per venueId + userId.
    """
    try:
        collection = get_venue_memberships_collection()

        collection.create_index(
            "membershipId",
            unique=True,
        )

        collection.create_index(
            [
                ("venueId", 1),
                ("userId", 1),
            ],
            unique=True,
        )

        collection.create_index(
            [
                ("businessId", 1),
                ("venueId", 1),
                ("isDeleted", 1),
            ]
        )

        collection.create_index(
            [
                ("businessId", 1),
                ("userId", 1),
                ("isDeleted", 1),
            ]
        )

    except PyMongoError as exc:
        raise RuntimeError(
            "Error initializing venue memberships storage."
        ) from exc


def insert_venue_membership(
    membership_document: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Inserts a new venue membership.

    Unique indexes prevent duplicate venueId + userId
    combinations, including logically deleted records.
    """
    try:
        collection = get_venue_memberships_collection()

        result = collection.insert_one(membership_document)

        document = collection.find_one(
            {"_id": result.inserted_id}
        )

        if not document:
            raise RuntimeError(
                "Venue membership was inserted but could not be retrieved."
            )

        return serialize_mongo_document(document)
    
    except DuplicateKeyError:
        raise

    except PyMongoError as exc:
        raise RuntimeError(
            "Error inserting venue membership into MongoDB."
        ) from exc


def get_venue_membership_by_user_and_venue(
    venue_id: str,
    user_id: str,
    business_id: str,
    *,
    include_deleted: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a user's membership within a venue.

    Can include deleted memberships to support
    controlled reactivation.
    """
    try:
        collection = get_venue_memberships_collection()

        query: Dict[str, Any] = {
            "venueId": venue_id,
            "userId": user_id,
            "businessId": business_id,
        }

        if not include_deleted:
            query["isDeleted"] = False

        document = collection.find_one(query)

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving membership by user and venue."
        ) from exc


def get_venue_membership_by_membership_id(
    membership_id: str,
    venue_id: str,
    business_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a non-deleted membership within
    the specified venue and organization.
    """
    try:
        collection = get_venue_memberships_collection()

        document = collection.find_one({
            "membershipId": membership_id,
            "venueId": venue_id,
            "businessId": business_id,
            "isDeleted": False,
        })

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving venue membership."
        ) from exc


def get_venue_memberships_by_venue_id(
    venue_id: str,
    business_id: str,
    *,
    include_deleted: bool = False,
    only_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Lists memberships belonging to one venue
    within its organization.
    """
    try:
        collection = get_venue_memberships_collection()

        query: Dict[str, Any] = {
            "venueId": venue_id,
            "businessId": business_id,
        }

        if not include_deleted:
            query["isDeleted"] = False

        if only_active is not None:
            query["isActive"] = only_active

        documents = collection.find(query).sort(
            "createdAt",
            -1,
        )

        return [
            serialize_mongo_document(doc)
            for doc in documents
        ]

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving venue memberships."
        ) from exc


def get_venue_memberships_by_user_id(
    user_id: str,
    business_id: str,
    *,
    only_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Lists non-deleted venue memberships
    belonging to one user within an organization.
    """
    try:
        collection = get_venue_memberships_collection()

        query: Dict[str, Any] = {
            "userId": user_id,
            "businessId": business_id,
            "isDeleted": False,
        }

        if only_active is not None:
            query["isActive"] = only_active

        documents = collection.find(query).sort(
            "createdAt",
            -1,
        )

        return [
            serialize_mongo_document(doc)
            for doc in documents
        ]

    except PyMongoError as exc:
        raise RuntimeError(
            "Error retrieving user venue memberships."
        ) from exc


def update_venue_membership_by_membership_id(
    membership_id: str,
    venue_id: str,
    business_id: str,
    update_fields: Dict[str, Any],
    *,
    include_deleted: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Updates a membership within its venue
    and organization.

    include_deleted=True permits controlled
    reactivation by the service layer.
    """
    try:
        collection = get_venue_memberships_collection()

        query: Dict[str, Any] = {
            "membershipId": membership_id,
            "venueId": venue_id,
            "businessId": business_id,
        }

        if not include_deleted:
            query["isDeleted"] = False

        document = collection.find_one_and_update(
            query,
            {
                "$set": update_fields,
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error updating venue membership."
        ) from exc


def soft_delete_venue_membership_by_membership_id(
    membership_id: str,
    venue_id: str,
    business_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Soft deletes a membership without removing
    its historical record.
    """
    try:
        collection = get_venue_memberships_collection()

        now = datetime.now(timezone.utc)

        document = collection.find_one_and_update(
            {
                "membershipId": membership_id,
                "venueId": venue_id,
                "businessId": business_id,
                "isDeleted": False,
            },
            {
                "$set": {
                    "isDeleted": True,
                    "isActive": False,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not document:
            return None

        return serialize_mongo_document(document)

    except PyMongoError as exc:
        raise RuntimeError(
            "Error soft deleting venue membership."
        ) from exc