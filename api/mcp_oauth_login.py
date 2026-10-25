# api/mcp_oauth_login.py

import html
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.mcp_login_service import authenticate_mcp_user
from db.mongo_mcp_oauth_requests import (
    get_mcp_oauth_request,
    consume_mcp_oauth_request,
)
from db.mongo_oauth_persistence import (
    create_oauth_authorization_code,
)

from typing import Callable


import secrets
import hmac


router = APIRouter(prefix="/auth/mcp/oauth", tags=["MCP OAuth"])


_auth_rate_limiter: Callable | None = None


def configure_mcp_oauth_login(
    rate_limiter: Callable,
) -> None:
    global _auth_rate_limiter
    _auth_rate_limiter = rate_limiter



def _render_login(
    request_id: str,
    error: str = "",
    csrf_token: str = "",
) -> str:
    safe_id = html.escape(request_id, quote=True)
    safe_error = html.escape(error)
    safe_csrf = html.escape(csrf_token, quote=True)

    error_html = (
        f'<p style="color:#b91c1c">{safe_error}</p>'
        if error else ""
    )

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Xapity — Autorizar ChatGPT</title>
      <style>
        body {{
          font-family: system-ui, sans-serif;
          background: #f5f6fa;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          margin: 0;
        }}
        main {{
          background: white;
          padding: 32px;
          border-radius: 12px;
          width: min(380px, 90vw);
          box-shadow: 0 8px 28px #00000012;
        }}
        input, button {{
          box-sizing: border-box;
          display: block;
          width: 100%;
          padding: 12px;
          margin-top: 12px;
          border-radius: 7px;
        }}
        input {{ border: 1px solid #ccc; }}
        button {{
          background: #171717;
          color: white;
          border: 0;
          cursor: pointer;
        }}
        label {{ display: block; margin-top: 14px; }}
        .consent {{ display: flex; gap: 8px; align-items: start; }}
        .consent input {{ width: auto; margin-top: 4px; }}
        small {{ color: #555; }}
      </style>
    </head>
    <body>
      <main>
        <h2>Conectar ChatGPT con Luca</h2>
        <p>Ingresa con tu cuenta Xapity MCP.</p>
        {error_html}
        <form method="post" action="/auth/mcp/oauth/login">
          <input type="hidden" name="request_id" value="{safe_id}">
          <input type="hidden" name="csrf_token" value="{safe_csrf}">
          <label>Correo electrónico
            <input type="email" name="email" required autocomplete="username">
          </label>
          <label>Contraseña
            <input type="password" name="password" required
                   autocomplete="current-password">
          </label>
          <label class="consent">
            <input type="checkbox" name="consent" value="yes" required>
            <span>
              Autorizo a ChatGPT a consultar mis datos de ventas
              mediante Xapity Luca.
            </span>
          </label>
          <button type="submit">Autorizar conexión</button>
        </form>
        <p><small>Permiso solicitado: luca:sales:read</small></p>
      </main>
    </body>
    </html>
    """


# @router.get("/login", response_class=HTMLResponse)
# def oauth_login_page(request_id: str):
#     pending = get_mcp_oauth_request(request_id)

#     if pending is None:
#         raise HTTPException(
#             status_code=400,
#             detail="Solicitud OAuth inválida o expirada.",
#         )

#     return HTMLResponse(
#         _render_login(request_id),
#         headers={"Cache-Control": "no-store"},
#     )


@router.get("/login", response_class=HTMLResponse)
def oauth_login_page(request_id: str):
    pending = get_mcp_oauth_request(request_id)

    if pending is None:
        raise HTTPException(
            status_code=400,
            detail="Solicitud OAuth inválida o expirada.",
        )

    csrf_token = secrets.token_urlsafe(32)

    response = HTMLResponse(
        _render_login(
            request_id=request_id,
            csrf_token=csrf_token,
        ),
        headers={"Cache-Control": "no-store"},
    )

    response.set_cookie(
        key="xapity_mcp_csrf",
        value=csrf_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=300,
        path="/auth/mcp/oauth/login",
    )

    return response


@router.post("/login")
def oauth_login_submit(
    request: Request,
    request_id: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    consent: str = Form(...),
    csrf_token: str = Form(...),
):
    
    cookie_csrf = request.cookies.get("xapity_mcp_csrf")

    if (
        not cookie_csrf
        or not hmac.compare_digest(cookie_csrf, csrf_token)
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid CSRF token.",
        )

    expected_origin = (
        "https://xapity-api-dev-179536772092.us-central1.run.app"
    )

    origin = request.headers.get("origin")

    if origin != expected_origin:
        raise HTTPException(
            status_code=403,
            detail="Invalid request origin.",
        )
    
    pending = get_mcp_oauth_request(request_id)

    if pending is None:
        raise HTTPException(
            status_code=400,
            detail="Solicitud OAuth inválida o expirada.",
        )

    if consent != "yes":
        raise HTTPException(
            status_code=400,
            detail="Debes autorizar el permiso solicitado.",
        )

    
    if _auth_rate_limiter is None:
        raise HTTPException(
            status_code=503,
            detail="OAuth login rate limiter not configured.",
        )

    _auth_rate_limiter(
        request=request,
        email=email,
        scope="mcp_oauth_login",
        ip_limit=10,
        email_limit=5,
        window_seconds=60,
    )


    try:
        user = authenticate_mcp_user(
            email=email,
            password=password,
        )
    except ValueError:
        return HTMLResponse(
            _render_login(
                request_id,
                "Credenciales inválidas.",
                csrf_token=csrf_token,
            ),
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )

    allowed_scopes = set(user.get("allowedScopes", []))
    requested_scopes = set(pending["scopes"])

    if not requested_scopes.issubset(allowed_scopes):
        raise HTTPException(
            status_code=403,
            detail="El usuario no tiene los permisos solicitados.",
        )

    # Consumo atómico: evita reutilizar una misma solicitud.
    pending = consume_mcp_oauth_request(request_id)

    if pending is None:
        raise HTTPException(
            status_code=409,
            detail="Solicitud OAuth ya utilizada o expirada.",
        )

    authorization_code = create_oauth_authorization_code(
        client_id=pending["clientId"],
        subject=user["userId"],
        scopes=pending["scopes"],
        code_challenge=pending["codeChallenge"],
        redirect_uri=pending["redirectUri"],
        redirect_uri_provided_explicitly=(
            pending["redirectUriProvidedExplicitly"]
        ),
        resource=pending["resource"],
    )

    # Preserva cualquier query string del callback registrado.
    parts = urlsplit(pending["redirectUri"])
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("code", authorization_code))

    if pending.get("state") is not None:
        query.append(("state", pending["state"]))

    redirect_url = urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(query),
        parts.fragment,
    ))

    return RedirectResponse(
        url=redirect_url,
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
