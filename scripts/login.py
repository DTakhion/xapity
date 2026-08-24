# scripts/login.py

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"
OUTPUT_PATH = ROOT_DIR / "results" / "luca_token.json"

load_dotenv(ENV_PATH)


def find_token_in_storage(page) -> str | None:
    """
    Busca el accessToken dentro de localStorage/sessionStorage.

    Maneja específicamente el formato de Firebase Auth.
    """

    storage_dump = page.evaluate(
        """
        () => {
          const output = {
            localStorage: {},
            sessionStorage: {},
          };

          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            output.localStorage[key] = localStorage.getItem(key);
          }

          for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            output.sessionStorage[key] = sessionStorage.getItem(key);
          }

          return output;
        }
        """
    )

    # Buscar accessToken dentro del JSON de Firebase.
    for storage_name in [
        "localStorage",
        "sessionStorage",
    ]:
        for _, value in storage_dump.get(
            storage_name,
            {},
        ).items():
            if not value:
                continue

            text = str(value)

            try:
                parsed = json.loads(text)

                # Caso Firebase Auth.
                if isinstance(parsed, dict):
                    token = (
                        parsed.get(
                            "stsTokenManager",
                            {},
                        )
                        .get("accessToken")
                    )

                    if token:
                        return token

            except Exception:
                pass

            # Fallback: JWT almacenado directamente.
            if text.startswith("eyJ"):
                return text

    return None


def decode_jwt_payload(
    token: str,
) -> dict:
    """
    Decodifica solamente el payload del JWT para inspeccionar
    metadatos como iat/exp.

    No valida criptográficamente la firma.
    """

    try:
        parts = token.split(".")

        if len(parts) != 3:
            return {}

        payload = parts[1]

        payload += "=" * (
            -len(payload) % 4
        )

        decoded = base64.urlsafe_b64decode(
            payload.encode("utf-8")
        )

        return json.loads(
            decoded.decode("utf-8")
        )

    except Exception:
        return {}


def token_fingerprint(
    token: str | None,
) -> str | None:
    """
    Genera un fingerprint corto para comparar tokens
    sin exponer su contenido.
    """

    if not token:
        return None

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()[:12]


def main() -> None:
    login_url = os.getenv(
        "LUCA_LOGIN_URL"
    )
    username = os.getenv(
        "LUCA_USERNAME"
    )
    password = os.getenv(
        "LUCA_PASSWORD"
    )

    if (
        not login_url
        or not username
        or not password
    ):
        raise RuntimeError(
            "Faltan variables en .env: "
            "LUCA_LOGIN_URL, "
            "LUCA_USERNAME, "
            "LUCA_PASSWORD"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Guardamos URL + Authorization header para poder
    # identificar qué bearer utiliza realmente la API.
    captured_auth_headers: list[
        tuple[str, str]
    ] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context()
        page = context.new_page()

        def on_request(request):
            auth = request.headers.get(
                "authorization"
            )

            if (
                auth
                and auth.lower().startswith(
                    "bearer "
                )
            ):
                captured_auth_headers.append(
                    (
                        request.url,
                        auth,
                    )
                )

        page.on(
            "request",
            on_request,
        )

        page.goto(
            login_url,
            wait_until="networkidle",
        )

        # Login.
        page.get_by_role(
            "textbox"
        ).first.fill(
            username
        )

        password_inputs = page.locator(
            'input[type="password"]'
        )

        password_inputs.first.fill(
            password
        )

        page.get_by_role(
            "button",
            name="Ir a mi cuenta",
        ).click()

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=15000,
            )
        except PlaywrightTimeoutError:
            pass

        # Permitimos que la aplicación haga sus requests
        # iniciales después del login.
        page.wait_for_timeout(3000)

        # ----------------------------------------------------
        # TOKEN FIREBASE STORAGE
        # ----------------------------------------------------

        storage_token = (
            find_token_in_storage(
                page
            )
        )

        # ----------------------------------------------------
        # TOKEN UTILIZADO POR LA API DE LUCA
        # ----------------------------------------------------

        luca_header_token = None
        luca_header_url = None

        # Recorremos desde la request más reciente.
        for (
            request_url,
            auth,
        ) in reversed(
            captured_auth_headers
        ):
            if (
                "gateway.dev"
                in request_url
                or "/v1/business/"
                in request_url
            ):
                luca_header_token = (
                    auth
                    .removeprefix("Bearer ")
                    .removeprefix("bearer ")
                    .strip()
                )

                luca_header_url = (
                    request_url
                )

                break

        # Fallback:
        # si no logramos identificar específicamente
        # una request de Luca, utilizamos el último bearer
        # observado por Playwright.
        header_token = (
            luca_header_token
        )

        if (
            not header_token
            and captured_auth_headers
        ):
            (
                fallback_url,
                fallback_auth,
            ) = captured_auth_headers[-1]

            header_token = (
                fallback_auth
                .removeprefix("Bearer ")
                .removeprefix("bearer ")
                .strip()
            )

            luca_header_url = (
                fallback_url
            )

        # ----------------------------------------------------
        # TOKEN FINAL
        # ----------------------------------------------------

        # Para consumir la API de Luca priorizamos el bearer
        # que la propia aplicación utiliza en sus requests.
        #
        # Firebase storage queda solamente como fallback.
        token = (
            header_token
            or storage_token
        )

        token_source = (
            "api_header"
            if header_token
            else (
                "firebase_storage"
                if storage_token
                else None
            )
        )

        # ----------------------------------------------------
        # DIAGNÓSTICO SEGURO
        # ----------------------------------------------------

        storage_fingerprint = (
            token_fingerprint(
                storage_token
            )
        )

        header_fingerprint = (
            token_fingerprint(
                header_token
            )
        )

        selected_fingerprint = (
            token_fingerprint(
                token
            )
        )

        print(
            "[login] Storage fingerprint:",
            storage_fingerprint,
        )

        print(
            "[login] API header fingerprint:",
            header_fingerprint,
        )

        print(
            "[login] Selected fingerprint:",
            selected_fingerprint,
        )

        print(
            "[login] Storage == API Header:",
            (
                storage_token
                == header_token
                if (
                    storage_token
                    and header_token
                )
                else None
            ),
        )

        print(
            "[login] Token source:",
            token_source,
        )

        print(
            "[login] API request:",
            luca_header_url,
        )

        # ----------------------------------------------------
        # METADATOS JWT
        # ----------------------------------------------------

        token_payload = (
            decode_jwt_payload(
                token
            )
            if token
            else {}
        )

        issued_at = (
            token_payload.get("iat")
        )

        expires_at = (
            token_payload.get("exp")
        )

        token_expired = (
            expires_at is not None
            and int(expires_at)
            <= int(time.time())
        )

        # ----------------------------------------------------
        # RESULTADO
        # ----------------------------------------------------

        result = {
            "login_url": login_url,
            "current_url": page.url,
            "token_found": (
                token is not None
            ),
            "token_source": (
                token_source
            ),
            "access_token": token,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "token_expired": (
                token_expired
            ),
            "api_request_url": (
                luca_header_url
            ),
            "storage_fingerprint": (
                storage_fingerprint
            ),
            "api_header_fingerprint": (
                header_fingerprint
            ),
            "selected_fingerprint": (
                selected_fingerprint
            ),
        }

        OUTPUT_PATH.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            f"Resultado guardado en: "
            f"{OUTPUT_PATH}"
        )

        if token:
            print(
                "Token encontrado"
            )

            if token_expired:
                print(
                    "ADVERTENCIA: "
                    "el token seleccionado "
                    "ya está expirado."
                )
        else:
            print(
                "No se encontró token "
                "automáticamente"
            )

            print(
                "Puede estar en cookies, "
                "IndexedDB o venir en una "
                "respuesta específica."
            )

        browser.close()


if __name__ == "__main__":
    main()