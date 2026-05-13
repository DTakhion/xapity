from pymongo import MongoClient
from datetime import datetime
import uuid

client = MongoClient("mongodb://localhost:27017")
db = client["xapity"]
collection = db["staff"]


def create_staff(data: dict) -> dict:
    now = datetime.utcnow()

    staff = {
        "staffId": str(uuid.uuid4()),
        "businessId": "1",

        "name": data["name"],
        "role": data["role"],
        "email": data.get("email"),
        "phone": data.get("phone"),
        "specialties": data.get("specialties", []),
        "serviceIds": data.get("serviceIds", []),
        "notes": data.get("notes"),

        "isActive": True,
        "isDeleted": False,

        "createdAt": now,
        "updatedAt": now
    }

    collection.insert_one(staff)

    # Convertimos datetime a string para respuesta
    staff["createdAt"] = staff["createdAt"].isoformat()
    staff["updatedAt"] = staff["updatedAt"].isoformat()

    return staff

def delete_staff(data: str) -> dict:
    now = datetime.utcnow()

    borrar = collection.find_one_and_update(
        {
            "staffId": data,
            "isDeleted": False  # evita eliminar dos veces
        },
        {
            "$set": {
                "isDeleted": True,
                "isActive": False,
                "updatedAt": now
            }
        },
        return_document=True
    )

    if not borrar:
        return None

    # formateo para respuesta
    borrar["createdAt"] = borrar["createdAt"].isoformat()
    borrar["updatedAt"] = borrar["updatedAt"].isoformat()

    return borrar