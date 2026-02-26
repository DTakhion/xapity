# api/main.py
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.ollama_client import generate
from services.qicore_client import gate as qicore_gate


app = FastAPI(title="xapity", version="0.1.0")


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User prompt")
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    model: Optional[str] = Field(None, description="Optional override model name, e.g. llama3.2")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/llm/generate")
def generate_llm(req: PromptRequest):
    try:
        return generate(
            prompt=req.prompt,
            model=req.model,
            temperature=req.temperature,
        )
    except Exception as e:
        # No exponemos detalles sensibles; pero sí retornamos algo útil
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {type(e).__name__}")
    
class GateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    model: Optional[str] = None


@app.post("/lab/gate")
def lab_gate(req: GateRequest):
    # 1) generar con Ollama (raw)
    llm_out = generate(
        prompt=req.prompt,
        model=req.model,
        temperature=req.temperature,
    )

    # 2) gatear con QiCore
    qicore_out = qicore_gate(
        prompt=req.prompt,
        answer=llm_out["response"],
        engine="ollama",
        extra={
            "model": llm_out.get("model"),
            "time_s": llm_out.get("time_s"),
        },
    )

    return {
        "prompt": req.prompt,
        "llm": llm_out,
        "qicore": qicore_out,
    }