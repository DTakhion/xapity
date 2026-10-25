# luca_mcp/oauth_provider.py
# ============================================================
# XAPITY — LUCA OAUTH AUTHORIZATION PROVIDER
# ============================================================

from datetime import timezone

from mcp.server.auth.provider import (
    OAuthAuthorizationServerProvider,
)

from mcp.shared.auth import OAuthClientInformationFull

from db.mongo_oauth_persistence import (
    register_oauth_client,
    get_oauth_client,
)

from mcp.server.auth.provider import AuthorizationCode

from db.mongo_oauth_persistence import (
    get_oauth_authorization_code,
)

from mcp.shared.auth import OAuthToken

from mcp.server.auth.provider import (
    AuthorizationCode,
    RefreshToken,
    TokenError,
)

from db.mongo_oauth_persistence import (
    exchange_oauth_authorization_code,
    ACCESS_TOKEN_TTL_SECONDS,
    get_oauth_token,
    rotate_oauth_refresh_token_pair,
    detect_oauth_refresh_token_replay,
)


from urllib.parse import urlencode

from mcp.server.auth.provider import (
    AuthorizationParams,
    AuthorizeError,
)

from db.mongo_mcp_oauth_requests import (
    create_mcp_oauth_request,
)


XAPITY_ISSUER_URL = (
    "https://xapity-api-dev-179536772092.us-central1.run.app"
)

XAPITY_MCP_RESOURCE_URL = (
    f"{XAPITY_ISSUER_URL}/mcp"
)

MCP_ALLOWED_SCOPES = {"luca:sales:read"}



class LucaOAuthProvider(OAuthAuthorizationServerProvider):
    """
    Proveedor OAuth de Xapity para ChatGPT ↔ Luca.

    Primera etapa:
    - Registro de clientes OAuth.
    - Recuperación de clientes OAuth.

    Las operaciones de autorización y emisión de tokens
    permanecerán deshabilitadas hasta implementar
    autenticación, consentimiento y controles de seguridad.
    """
    
    
    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        """
        Inicia la autorización OAuth de ChatGPT.

        Guarda una solicitud temporal y devuelve
        la URL de login MCP.

        No autentica usuarios ni emite tokens.
        """

        redirect_uri = str(params.redirect_uri)

        registered_redirect_uris = {
            str(uri) for uri in client.redirect_uris
        }

        if redirect_uri not in registered_redirect_uris:
            raise AuthorizeError(
                error="invalid_request",
                error_description="Invalid redirect URI.",
            )

        if not params.code_challenge:
            raise AuthorizeError(
                error="invalid_request",
                error_description="PKCE is required.",
            )

        scopes = list(params.scopes or [])

        if not scopes:
            raise AuthorizeError(
                error="invalid_scope",
                error_description="OAuth scope is required.",
            )

        if not set(scopes).issubset(MCP_ALLOWED_SCOPES):
            raise AuthorizeError(
                error="invalid_scope",
                error_description="Unsupported OAuth scope.",
            )

        resource = params.resource

        if resource != XAPITY_MCP_RESOURCE_URL:
            raise AuthorizeError(
                error="invalid_target",
                error_description="Invalid MCP resource.",
            )

        request_id = create_mcp_oauth_request(
            client_id=client.client_id,
            redirect_uri=redirect_uri,
            redirect_uri_provided_explicitly=(
                params.redirect_uri_provided_explicitly
            ),
            code_challenge=params.code_challenge,
            state=params.state,
            scopes=scopes,
            resource=resource,
        )

        query = urlencode({"request_id": request_id})

        return (
            f"{XAPITY_ISSUER_URL}/auth/mcp/oauth/login"
            f"?{query}"
        )


    async def register_client(
        self,
        client_info: OAuthClientInformationFull,
    ) -> None:
        register_oauth_client(client_info)

    async def get_client(
        self,
        client_id: str,
    ) -> OAuthClientInformationFull | None:
        return get_oauth_client(client_id)
    
    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        """
        Recupera un código OAuth sin consumirlo.

        El SDK MCP valida posteriormente:
        - Cliente.
        - Expiración.
        - Redirect URI.
        - PKCE.
        """

        code = get_oauth_authorization_code(
            authorization_code
        )

        if code is None:
            return None

        if code.client_id != client.client_id:
            return None

        return code
    
    
    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        """
        Intercambia un código previamente validado
        por el SDK MCP.

        MongoDB consume el código y emite ambos tokens
        en una única transacción.
        """

        if authorization_code.client_id != client.client_id:
            raise TokenError(
                error="invalid_grant",
                error_description="Invalid authorization code.",
            )

        
        result = exchange_oauth_authorization_code(
            authorization_code.code,
            client_id=client.client_id,
            expected_code_challenge=(
                authorization_code.code_challenge
            ),
            expected_redirect_uri=str(
                authorization_code.redirect_uri
            ),
            expected_redirect_uri_provided_explicitly=(
                authorization_code.redirect_uri_provided_explicitly
            ),
            expected_resource=authorization_code.resource,
            expected_subject=authorization_code.subject,
            expected_scopes=authorization_code.scopes,
        )


        if result is None:
            raise TokenError(
                error="invalid_grant",
                error_description=(
                    "Authorization code expired, "
                    "invalid or already consumed."
                ),
            )

        access_token, refresh_token = result

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            scope=" ".join(authorization_code.scopes),
            refresh_token=refresh_token,
        )
    
    
    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        """
        Recupera un refresh token vigente
        y asociado al cliente OAuth.
        """

        document = get_oauth_token(
            refresh_token,
            token_type="refresh",
        )

        if document is None:
            detect_oauth_refresh_token_replay(
                refresh_token,
                client_id=client.client_id,
            )
            return None

        if document["clientId"] != client.client_id:
            return None

        expires_at = document["expiresAt"]

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        return RefreshToken(
            token=refresh_token,
            client_id=document["clientId"],
            scopes=document["scopes"],
            expires_at=int(expires_at.timestamp()),
            resource=document["resource"],
            subject=document["subject"],
        )
    
    
    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """
        Rota un refresh token y entrega
        nuevas credenciales OAuth.
        """

        if refresh_token.client_id != client.client_id:
            raise TokenError(
                error="invalid_grant",
                error_description="Invalid refresh token.",
            )

        # La implementación actual no admite reducir
        # scopes durante la renovación.
        # Rechazamos cualquier solicitud diferente.
        if scopes and set(scopes) != set(refresh_token.scopes):
            raise TokenError(
                error="invalid_scope",
                error_description=(
                    "Scope changes during refresh "
                    "are not supported."
                ),
            )

        result = rotate_oauth_refresh_token_pair(
            refresh_token.token,
            client_id=client.client_id,
        )

        if result is None:
            raise TokenError(
                error="invalid_grant",
                error_description=(
                    "Refresh token invalid, expired "
                    "or already consumed."
                ),
            )

        access_token, new_refresh_token = result

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            scope=" ".join(refresh_token.scopes),
            refresh_token=new_refresh_token,
        )



