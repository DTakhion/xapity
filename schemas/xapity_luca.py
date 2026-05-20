# schemas/xapity_luca.py

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


XapityLucaIntent = Literal[
    "sales_summary",
    "pending_payments",
    "sales_excel",
    "unknown",
]

XapityLucaFormat = Literal[
    "text",
    "excel",
    "pdf",
]


class XapityLucaIntentAnalysis(BaseModel):
    intent: XapityLucaIntent = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    month: int | None = Field(
        default=None,
        description="Mes en formato 1=enero, 2=febrero, ..., 12=diciembre. 0=todos.",
    )

    year: int = 2026
    business_id: int | None = None

    requested_format: XapityLucaFormat = "text"

    original_message: str
    normalized_message: str

    needs_clarification: bool = False
    clarification_reason: str | None = None


class XapityLucaRequest(BaseModel):
    message: str
    business_id: int | None = None
    requested_by: str | None = None


class XapityLucaResponse(BaseModel):
    ok: bool
    intent: XapityLucaIntent
    message: str

    business_id: int | None = None
    month: int | None = None
    year: int | None = None

    data: dict[str, Any] | None = None
    file_path: str | None = None

    needs_clarification: bool = False
    clarification_reason: str | None = None