# # services/ollama_client.py

# import os
# import json
# import time
# import urllib.request

# BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")


# def _post_json(url: str, payload: dict) -> dict:
#     data = json.dumps(payload).encode("utf-8")
#     req = urllib.request.Request(
#         url,
#         data=data,
#         headers={"Content-Type": "application/json"},
#         method="POST",
#     )
#     with urllib.request.urlopen(req, timeout=120) as resp:
#         return json.loads(resp.read().decode("utf-8"))


# def generate(prompt: str, temperature: float = 0.2) -> dict:
#     payload = {
#         "model": MODEL,
#         "prompt": prompt,
#         "stream": False,
#         "options": {
#             "temperature": temperature,
#         },
#     }

#     t0 = time.time()
#     out = _post_json(f"{BASE_URL}/api/generate", payload)
#     dt = time.time() - t0

#     return {
#         "model": MODEL,
#         "response": out.get("response", "").strip(),
#         "time_s": round(dt, 3),
#         "raw": out,
#     }

# services/ollama_client.py
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "120"))


def _post_json(url: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    Calls Ollama /api/generate (non-streaming).
    Returns a normalized dict for your API.
    """
    use_model = model or OLLAMA_MODEL

    payload: Dict[str, Any] = {
        "model": use_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": float(temperature),
        },
    }

    t0 = time.time()
    out = _post_json(f"{OLLAMA_BASE_URL}/api/generate", payload, timeout_s=OLLAMA_TIMEOUT_S)
    dt = time.time() - t0

    return {
        "engine": "ollama",
        "model": out.get("model", use_model),
        "response": (out.get("response") or "").strip(),
        "time_s": round(dt, 3),
        "raw": out,  # útil para debugging (context, eval_count, etc.)
    }