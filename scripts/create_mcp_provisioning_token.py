
# scripts/create_mcp_provisioning_token.py
# ============================================================
# XAPITY LUCA MCP — USER PROVISIONING INVITATION
# ============================================================

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from services.mcp_auth_service import (
    create_mcp_provisioning_token,
    MCP_PROVISIONING_EXPIRE_HOURS,
)

from services.email_service import (
    send_mcp_provisioning_email,
)

from db.mongo_mcp_auth_persistence import (
    initialize_mcp_provisioning_storage,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and email a user provisioning "
            "invitation for Xapity Luca MCP."
        )
    )

    parser.add_argument(
        "--email",
        required=True,
        help="Email authorized to register for Xapity Luca MCP.",
    )

    args = parser.parse_args()
    email = args.email.strip().lower()

    api_base_url = os.getenv(
        "XAPITY_API_BASE_URL",
        "http://localhost:8000",
    ).rstrip("/")

    registration_url = f"{api_base_url}/docs"

    try:
        initialize_mcp_provisioning_storage()

        token = create_mcp_provisioning_token(email)

        send_mcp_provisioning_email(
            to_email=email,
            token=token,
            expires_hours=MCP_PROVISIONING_EXPIRE_HOURS,
            registration_url=registration_url,
        )

    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 64)
    print("XAPITY LUCA MCP — USER INVITATION")
    print("=" * 64)
    print(f"Email      : {email}")
    print(f"Expires in : {MCP_PROVISIONING_EXPIRE_HOURS} hours")
    print(f"Register   : {registration_url}")
    print()
    print("Invitation processed successfully.")
    print("Check EMAIL_MODE to confirm delivery method.")
    print("=" * 64)


if __name__ == "__main__":
    main()
