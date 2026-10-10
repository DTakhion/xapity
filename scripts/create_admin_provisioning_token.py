
# scripts/create_admin_provisioning_token.py
# ============================================================
# XAPITY ACCESS — ADMIN PROVISIONING TOKEN GENERATOR
# ============================================================

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow execution from the project root or scripts directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from services.auth_service import (
    create_admin_provisioning_token,
    ADMIN_PROVISIONING_EXPIRE_HOURS,
)

from db.mongo_persistence import (
    initialize_admin_provisioning_storage,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a controlled administrator provisioning "
            "token for Xapity Access."
        )
    )

    parser.add_argument(
        "--email",
        required=True,
        help="Email address authorized to register as administrator.",
    )

    args = parser.parse_args()

    email = args.email.strip().lower()

    try:
        initialize_admin_provisioning_storage()

        token = create_admin_provisioning_token(email)

    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 64)
    print("XAPITY ACCESS — ADMIN PROVISIONING")
    print("=" * 64)
    print(f"Email       : {email}")
    print(f"Expires in  : {ADMIN_PROVISIONING_EXPIRE_HOURS} hours")
    print()
    print("ADMIN PROVISIONING TOKEN:")
    print(token)
    print()
    print("IMPORTANT:")
    print("- Share this token only with the authorized administrator.")
    print("- The token is bound to the email above.")
    print("- The token can be used only once.")
    print("- The token is stored as a SHA-256 hash in MongoDB.")
    print("=" * 64)
    print()


if __name__ == "__main__":
    main()
