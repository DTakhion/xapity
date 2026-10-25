# db/mongo_mcp_oauth_requests.py
# ============================================================
# XAPITY — MCP OAUTH PENDING AUTHORIZATION REQUESTS
# ============================================================

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from db.mongo_persistence import get_database


COLLECTION = "mcp_oauth_pending_requests"
REQUEST_TTL_SECONDS = 300


def _hash_secret(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def initialize_mcp_oauth_requests_storage() -> None:
    collection = get_database()[COLLECTION]

    collection.create_index(
        "requestHash",
        unique=True,
        name="ux_mcp_oauth_request_hash",
    )

    collection.create_index(
        "expiresAt",
        expireAfterSeconds=0,
        name="ttl_mcp_oauth_request_expiry",
    )


def create_mcp_oauth_request(
    *,
    client_id: str,
    redirect_uri: str,
    redirect_uri_provided_explicitly: bool,
    code_challenge: str,
    state: str | None,
    scopes: list[str],
    resource: str,
) -> str:
    if not client_id or not redirect_uri or not code_challenge:
        raise ValueError("Invalid OAuth authorization request.")

    if not resource:
        raise ValueError("OAuth resource is required.")

    if not scopes:
        raise ValueError("OAuth scopes are required.")

    request_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    get_database()[COLLECTION].insert_one({
        "requestHash": _hash_secret(request_id),
        "clientId": client_id,
        "redirectUri": redirect_uri,
        "redirectUriProvidedExplicitly": (
            redirect_uri_provided_explicitly
        ),
        "codeChallenge": code_challenge,
        "state": state,
        "scopes": list(scopes),
        "resource": resource,
        "createdAt": now,
        "expiresAt": now + timedelta(
            seconds=REQUEST_TTL_SECONDS
        ),
        "consumedAt": None,
    })

    return request_id


def get_mcp_oauth_request(request_id: str) -> dict | None:
    if not request_id:
        return None

    return get_database()[COLLECTION].find_one({
        "requestHash": _hash_secret(request_id),
        "consumedAt": None,
        "expiresAt": {
            "$gt": datetime.now(timezone.utc)
        },
    })


def consume_mcp_oauth_request(request_id: str) -> dict | None:
    if not request_id:
        return None

    now = datetime.now(timezone.utc)

    return get_database()[COLLECTION].find_one_and_update(
        {
            "requestHash": _hash_secret(request_id),
            "consumedAt": None,
            "expiresAt": {"$gt": now},
        },
        {
            "$set": {"consumedAt": now},
        },
        return_document=ReturnDocument.AFTER,
    )
