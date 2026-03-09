# services/qicore_client.py
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


QICORE_BASE_URL = (os.getenv("QICORE_BASE_URL", "") or "").strip().rstrip("/")
QICORE_API_KEY = (os.getenv("QICORE_API_KEY", "") or "").strip()
QICORE_TIMEOUT_S = float(os.getenv("QICORE_TIMEOUT_S", "60"))


class QiCoreClientError(RuntimeError):
    pass


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout_s: float) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = "<unable to read body>"
        raise QiCoreClientError(f"HTTP {e.code} from QiCore: {err_body[:800]}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise QiCoreClientError(f"QiCore request failed: {type(e).__name__}: {e}") from e


def gate(
    *,
    prompt: str,
    answer: str,
    provider_engine: str = "ollama",
    provider_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    QiCore expects:
      { "engine": "custom", "payload": { "prompt": "...", "answer": "...", "meta": {...} } }
    """
    if not QICORE_BASE_URL:
        raise QiCoreClientError("QICORE_BASE_URL is not set")
    if not QICORE_API_KEY:
        raise QiCoreClientError("QICORE_API_KEY is not set")

    payload: Dict[str, Any] = {
        "engine": "custom",
        "payload": {
            "prompt": prompt,
            "answer": answer,
            "meta": {
                "provider_engine": provider_engine,
                **(provider_meta or {}),
            },
        },
    }

    headers = {"X-API-Key": QICORE_API_KEY}
    return _post_json(f"{QICORE_BASE_URL}/v1/qicore/gate", payload, headers=headers, timeout_s=QICORE_TIMEOUT_S)