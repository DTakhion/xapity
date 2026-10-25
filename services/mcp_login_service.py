
# services/mcp_login_service.py
# ============================================================
# XAPITY — MCP USER LOGIN
# ============================================================

from db.mongo_mcp_registration import get_mcp_user_by_email
from services.auth_service import verify_password


def authenticate_mcp_user(email: str, password: str) -> dict:
    normalized_email = str(email).strip().lower()

    user = get_mcp_user_by_email(normalized_email)

    if (
        not user
        or user.get("accountType") != "mcp"
        or user.get("isActive") is not True
        or user.get("isDeleted") is not False
    ):
        raise ValueError("Credenciales inválidas")

    if not verify_password(password, user["passwordHash"]):
        raise ValueError("Credenciales inválidas")

    return {
        "userId": user["userId"],
        "email": user["email"],
        "accountType": "mcp",
        "allowedScopes": user.get("allowedScopes", []),
    }
