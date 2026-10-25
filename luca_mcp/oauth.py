# luca_mcp/oauth.py
# ============================================================
# XAPITY — LUCA MCP OAUTH
# Verificación de access tokens persistidos en MongoDB
# ============================================================

from mcp.server.auth.provider import (
    TokenVerifier,
    AccessToken,
)

from db.mongo_oauth_persistence import get_oauth_token


class LucaTokenVerifier(TokenVerifier):
    """
    Verifica access tokens OAuth emitidos por Xapity.

    Solo acepta tokens:
    - Existentes en MongoDB.
    - No expirados.
    - No revocados.
    - De tipo access.
    - Asociados al recurso MCP autorizado.
    """

    def __init__(self, resource: str):
        self.resource = resource.rstrip("/")

    async def verify_token(
        self,
        token: str,
    ) -> AccessToken | None:

        if not token:
            return None

        document = get_oauth_token(
            token,
            token_type="access",
        )

        if document is None:
            return None

        if document.get("resource") != self.resource:
            return None

        return AccessToken(
            token=token,
            client_id=document["clientId"],
            scopes=document["scopes"],
            expires_at=int(
                document["expiresAt"].timestamp()
            ),
            resource=document["resource"],
            subject=document["subject"],
        )
