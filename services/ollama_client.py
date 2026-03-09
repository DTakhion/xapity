# services/ollama_client.py
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "120"))


class OllamaClientError(RuntimeError):
    pass


def _post_json(url: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            try:
                return json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as e:
                raise OllamaClientError(f"Ollama returned non-JSON response: {body[:200]!r}") from e

    except urllib.error.HTTPError as e:
        # e.read() can be consumed only once; best effort
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = "<unable to read body>"
        raise OllamaClientError(f"HTTP {e.code} from Ollama: {err_body[:500]}") from e

    except (urllib.error.URLError, TimeoutError) as e:
        raise OllamaClientError(f"Could not reach Ollama at {url}: {e}") from e


def generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    options: Optional[Dict[str, Any]] = None,
    include_raw: bool = True,
) -> Dict[str, Any]:
    """
    Calls Ollama /api/generate (non-streaming).
    Returns a normalized dict for API.
    """
    use_model = model or OLLAMA_MODEL

    payload: Dict[str, Any] = {
        "model": use_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": float(temperature),
            **(options or {}),
        },
    }

    t0 = time.time()
    out = _post_json(f"{OLLAMA_BASE_URL}/api/generate", payload, timeout_s=OLLAMA_TIMEOUT_S)
    dt = time.time() - t0

    response = (out.get("response") or "").strip()

    normalized: Dict[str, Any] = {
        "engine": "ollama",
        "model": out.get("model", use_model),
        "response": response,
        "time_s": round(dt, 3),
        "usage": {
            "prompt_chars": len(prompt),
            "response_chars": len(response),
            "eval_count": out.get("eval_count"),
            "prompt_eval_count": out.get("prompt_eval_count"),
        },
    }

    if include_raw:
        # Evita inflar/filtrar context gigante
        raw = dict(out)
        raw.pop("context", None)
        normalized["raw"] = raw

    return normalized