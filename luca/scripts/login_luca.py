# luca/scripts/login_luca.py

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
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

    # Buscar accessToken dentro del JSON de Firebase
    for storage_name in ["localStorage", "sessionStorage"]:
        for key, value in storage_dump.get(storage_name, {}).items():
            if not value:
                continue

            text = str(value)

            try:
                parsed = json.loads(text)

                # Caso Firebase Auth
                if isinstance(parsed, dict):
                    token = (
                        parsed.get("stsTokenManager", {})
                        .get("accessToken")
                    )

                    if token:
                        return token

            except Exception:
                pass

            # Fallback: si es JWT directo
            if text.startswith("eyJ"):
                return text

    return None


def get_luca_access_token(headless: bool = True) -> str:
    """
    Realiza login en Luca y retorna el Bearer Token.
    """

    login_url = os.getenv("LUCA_LOGIN_URL")
    username = os.getenv("LUCA_USERNAME")
    password = os.getenv("LUCA_PASSWORD")

    if not login_url or not username or not password:
        raise RuntimeError(
            "Faltan variables en .env: "
            "LUCA_LOGIN_URL, LUCA_USERNAME, LUCA_PASSWORD"
        )

    captured_auth_headers: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        context = browser.new_context()

        page = context.new_page()

        def on_request(request):
            auth = request.headers.get("authorization")

            if auth and auth.lower().startswith("bearer "):
                captured_auth_headers.append(auth)

        page.on("request", on_request)

        page.goto(login_url, wait_until="networkidle")

        # Username
        page.get_by_role("textbox").first.fill(username)

        # Password
        password_inputs = page.locator('input[type="password"]')
        password_inputs.first.fill(password)

        # Login
        page.get_by_role("button", name="Ir a mi cuenta").click()

        try:
            page.wait_for_load_state("networkidle", timeout=15000)

        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(3000)

        token = None

        # Intentar capturar desde Authorization Header
        if captured_auth_headers:
            token = (
                captured_auth_headers[-1]
                .replace("Bearer ", "")
                .strip()
            )

        # Fallback: localStorage/sessionStorage
        if not token:
            token = find_token_in_storage(page)

        browser.close()

    if not token:
        raise RuntimeError(
            "No se encontró token automáticamente después del login"
        )

    return token


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    token = get_luca_access_token(headless=False)

    result = {
        "login_url": os.getenv("LUCA_LOGIN_URL"),
        "token_found": token is not None,
        "access_token": token,
    }

    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Resultado guardado en: {OUTPUT_PATH}")

    if token:
        print("Token encontrado")
    else:
        print("No se encontró token")


if __name__ == "__main__":
    main()