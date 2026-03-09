# api/main.py
from __future__ import annotations

import os
import uuid
from typing import Optional, Any, Dict
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"   # xapity/.env
load_dotenv(ENV_PATH)

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

from services.ollama_client import generate
from services.qicore_client import gate as qicore_gate


app = FastAPI(title="xapity", version="0.1.0")

DEBUG = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes", "y"}
GATE_ENGINE = os.getenv("GATE_ENGINE", "ollama")


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User prompt")
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    model: Optional[str] = Field(None, description="Optional override model name, e.g. llama3.2")


class GateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    model: Optional[str] = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/llm/generate")
def generate_llm(req: PromptRequest, x_request_id: Optional[str] = Header(default=None)):
    request_id = x_request_id or str(uuid.uuid4())

    try:
        out = generate(prompt=req.prompt, model=req.model, temperature=req.temperature)
    except Exception as e:
        # Ideal: log server-side con request_id
        raise HTTPException(
            status_code=502,
            detail={"error": "ollama_request_failed", "type": type(e).__name__, "request_id": request_id},
        )

    # En prod, evitar devolver "raw" si pesa o filtra info
    if not DEBUG and isinstance(out, dict):
        out = dict(out)
        out.pop("raw", None)

    return {"request_id": request_id, "llm": out}


@app.post("/lab/gate")
def lab_gate(req: GateRequest):
    llm_out = generate(prompt=req.prompt, model=req.model, temperature=req.temperature)

    qicore_out = qicore_gate(
        prompt=req.prompt,
        answer=llm_out["response"],
        provider_engine="ollama",
        provider_meta={
            "model": llm_out.get("model"),
            "temperature": req.temperature,
            "time_s": llm_out.get("time_s"),
        },
    )

    decision = (qicore_out.get("qicore") or {}).get("decision") or {}
    blocked = bool(decision.get("blocked", False))

    final_answer = decision.get("safe_message") if blocked else llm_out["response"]

    return {
        "prompt": req.prompt,
        "final_answer": final_answer,
        "blocked": blocked,
        "risk_score": decision.get("risk_score"),
        "reason_codes": decision.get("reason_codes", []),
        "llm": llm_out,
        "qicore": qicore_out,
    }