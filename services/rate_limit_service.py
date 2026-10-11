# services/rate_limit_service.py
# ============================================================
# XAPITY ACCESS — RATE LIMIT SERVICE
# ============================================================
#
# Shared rate limiting using MongoDB.
#
# Architecture:
#   FastAPI dependency
#       -> rate_limit_service.py
#       -> db/mongo_persistence.py
#       -> MongoDB
#
# Fixed-window counters with atomic increments.
#
# ============================================================

from __future__ import annotations

import hashlib
import math
import time

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from db.mongo_persistence import get_rate_limits_collection


# ============================================================
# EXCEPTIONS
# ============================================================

class RateLimitExceeded(Exception):
    """
    Raised when a rate-limit threshold is exceeded.
    """

    def __init__(
        self,
        *,
        retry_after: int,
        limit: int,
        window_seconds: int,
    ):
        self.retry_after = retry_after
        self.limit = limit
        self.window_seconds = window_seconds

        super().__init__(
            "Rate limit exceeded. Please try again later."
        )


class RateLimitStorageError(Exception):
    """
    Raised when MongoDB cannot evaluate a rate limit.
    """


# ============================================================
# RESULT
# ============================================================

@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_at: datetime


# ============================================================
# HELPERS
# ============================================================

def normalize_identifier(identifier: str) -> str:
    """
    Normalizes the identifier used to build a counter key.

    Email normalization and IP validation should be handled
    by the calling layer.
    """
    value = str(identifier).strip().lower()

    if not value:
        raise ValueError(
            "Rate limit identifier cannot be empty."
        )

    return value


def build_rate_limit_key(
    *,
    scope: str,
    identifier: str,
    window_start: int,
) -> str:
    """
    Creates a deterministic SHA-256 counter identifier.

    No raw email or IP is stored in the MongoDB _id.
    """
    normalized_scope = scope.strip().lower()

    if not normalized_scope:
        raise ValueError(
            "Rate limit scope cannot be empty."
        )

    normalized_identifier = normalize_identifier(
        identifier
    )

    raw_key = (
        f"{normalized_scope}:"
        f"{normalized_identifier}:"
        f"{window_start}"
    )

    digest = hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()

    return f"rl:{digest}"


# ============================================================
# CORE RATE LIMIT
# ============================================================

def check_rate_limit(
    *,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    now: Optional[datetime] = None,
) -> RateLimitResult:
    """
    Checks and consumes one request from a fixed-window
    rate-limit counter.

    Args:
        scope:
            Logical operation, e.g. auth_login_ip.

        identifier:
            Normalized email, userId, IP, etc.

        limit:
            Maximum requests permitted per window.

        window_seconds:
            Window duration in seconds.

        now:
            Optional UTC datetime, useful for tests.

    Returns:
        RateLimitResult.

    Raises:
        RateLimitExceeded:
            When the counter exceeds the threshold.

        RateLimitStorageError:
            When MongoDB cannot evaluate the counter.

    Notes:
        - Counters are shared between Cloud Run instances.
        - MongoDB increments are atomic.
        - TTL cleanup is asynchronous.
        - Expiration is determined by the window,
          not by TTL deletion.
    """

    if limit < 1:
        raise ValueError(
            "Rate limit must be greater than zero."
        )

    if window_seconds < 1:
        raise ValueError(
            "Rate limit window must be greater than zero."
        )

    if now is None:
        now = datetime.now(timezone.utc)

    elif now.tzinfo is None:
        raise ValueError(
            "Rate limit datetime must be timezone-aware."
        )

    now = now.astimezone(timezone.utc)

    timestamp = now.timestamp()

    window_start = (
        math.floor(timestamp / window_seconds)
        * window_seconds
    )

    window_end = window_start + window_seconds

    reset_at = datetime.fromtimestamp(
        window_end,
        tz=timezone.utc,
    )

    # TTL cleanup occurs after the logical window ends.
    # This retention period is independent of enforcement.
    expires_at = reset_at + timedelta(hours=1)

    key = build_rate_limit_key(
        scope=scope,
        identifier=identifier,
        window_start=window_start,
    )

    collection = get_rate_limits_collection()

    try:
        document = collection.find_one_and_update(
            {"_id": key},
            {
                "$inc": {
                    "count": 1,
                },
                "$setOnInsert": {
                    "createdAt": now,
                    "resetAt": reset_at,
                    "expiresAt": expires_at,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    except DuplicateKeyError:
        # A concurrent request may have inserted the
        # same counter first. Retry as an update only.
        try:
            document = collection.find_one_and_update(
                {"_id": key},
                {
                    "$inc": {
                        "count": 1,
                    },
                },
                return_document=ReturnDocument.AFTER,
            )

        except PyMongoError as exc:
            raise RateLimitStorageError(
                "Could not update rate-limit counter."
            ) from exc

    except PyMongoError as exc:
        raise RateLimitStorageError(
            "Could not evaluate rate limit."
        ) from exc

    if document is None:
        raise RateLimitStorageError(
            "Rate-limit counter was not returned."
        )

    count = int(document["count"])

    remaining = max(0, limit - count)

    retry_after = max(
        1,
        math.ceil(window_end - timestamp),
    )

    allowed = count <= limit

    if not allowed:
        raise RateLimitExceeded(
            retry_after=retry_after,
            limit=limit,
            window_seconds=window_seconds,
        )

    return RateLimitResult(
        allowed=True,
        limit=limit,
        remaining=remaining,
        retry_after=0,
        reset_at=reset_at,
    )
