# schemas/rag.py
from pydantic import BaseModel, Field
from typing import Literal


class RagAnswerRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Pregunta del usuario para consultar la base de conocimiento RAG.",
        examples=["¿Qué permiso tiene un padre por nacimiento de un hijo?"],
    )

    top_k: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Cantidad máxima de fragmentos de contexto a recuperar.",
    )

    min_score: float = Field(
        default=0.68,
        ge=0.0,
        le=1.0,
        description="Score mínimo de similitud para aceptar contexto recuperado.",
    )


class RagSource(BaseModel):
    chunk_id: str | None = None
    score: float | None = None
    source: str | None = None
    page: int | None = None


class RagAnswerResponse(BaseModel):
    status: Literal["answered", "no_context", "error"]
    answer: str
    query: str
    matches_count: int
    confidence: Literal["high", "medium", "low", "none"]
    mode: str | None = None
    sources: list[RagSource] = Field(default_factory=list)
    error_detail: str | None = None