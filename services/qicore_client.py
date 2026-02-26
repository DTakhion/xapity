# services/qicore_client.py
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, Optional


QICORE_BASE_URL = os.getenv("QICORE_BASE_URL", "").rstrip("/")
QICORE_API_KEY = os.getenv("QICORE_API_KEY", "")
QICORE_TIMEOUT_S = float(os.getenv("QICORE_TIMEOUT_S", "60"))


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout_s: float) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gate(
    prompt: str,
    answer: str,
    engine: str = "ollama",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calls QiCore gate endpoint:
    POST {QICORE_BASE_URL}/v1/qicore/gate
    Headers: X-API-Key
    """
    if not QICORE_BASE_URL:
        raise RuntimeError("QICORE_BASE_URL is not set")
    if not QICORE_API_KEY:
        raise RuntimeError("QICORE_API_KEY is not set")

    payload: Dict[str, Any] = {
        "engine": engine,
        "payload": {
            "prompt": prompt,
            "answer": answer,
        },
    }
    if extra:
        payload["payload"].update(extra)

    headers = {"X-API-Key": QICORE_API_KEY}

    return _post_json(f"{QICORE_BASE_URL}/v1/qicore/gate", payload, headers=headers, timeout_s=QICORE_TIMEOUT_S)