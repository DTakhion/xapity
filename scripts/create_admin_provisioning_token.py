# scripts/create_admin_provisioning_token.py
# ============================================================
# XAPITY ACCESS — ADMIN PROVISIONING INVITATION
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

from services.auth_service import (
    create_admin_provisioning_token,
    ADMIN_PROVISIONING_EXPIRE_HOURS,
)

from services.email_service import (
    send_admin_provisioning_email,
)

from db.mongo_persistence import (
    initialize_admin_provisioning_storage,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and email an administrator provisioning "
            "invitation for Xapity Access."
        )
    )

    parser.add_argument(
        "--email",
        required=True,
        help="Email authorized to register as administrator.",
    )

    args = parser.parse_args()
    email = args.email.strip().lower()

    frontend_base_url = os.getenv(
        "FRONTEND_BASE_URL",
        "http://localhost:5173",
    ).rstrip("/")

    registration_url = (
        f"{frontend_base_url}/admin/register"
    )

    try:
        initialize_admin_provisioning_storage()

        token = create_admin_provisioning_token(email)

        send_admin_provisioning_email(
            to_email=email,
            token=token,
            expires_hours=ADMIN_PROVISIONING_EXPIRE_HOURS,
            registration_url=registration_url,
        )

    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 64)
    print("XAPITY ACCESS — ADMIN INVITATION")
    print("=" * 64)
    print(f"Email      : {email}")
    print(f"Expires in : {ADMIN_PROVISIONING_EXPIRE_HOURS} hours")
    print(f"Register   : {registration_url}")
    print()
    print("Invitation processed successfully.")
    print("Check EMAIL_MODE to confirm delivery method.")
    print("=" * 64)


if __name__ == "__main__":
    main()
