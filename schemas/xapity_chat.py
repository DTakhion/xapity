# schemas/xapity_chat.py

from __future__ import annotations

from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel, Field


class XapityIntentAnalysis(BaseModel):
    intent: Literal["greeting", "farewell", "list_services", "unknown"] = Field(
        ...,
        description="Intención detectada a partir del mensaje del usuario",
        examples=["greeting", "farewell", "list_services", "unknown"],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nivel de confianza de la intención detectada",
    )
    is_ambiguous: bool = Field(
        default=False,
        description="Indica si el mensaje podría tener más de una interpretación",
    )
    has_noise: bool = Field(
        default=False,
        description="Indica si el mensaje contiene ruido, texto irrelevante o estructura anómala",
    )
    needs_clarification: bool = Field(
        default=False,
        description="Indica si Xapity debería pedir al usuario que reformule su solicitud",
    )


class XapityResponseMetadata(BaseModel):
    classifier_version: Optional[str] = Field(
        default=None,
        description="Versión del clasificador o del flujo de detección de intención",
    )
    detection_source: Optional[str] = Field(
        default=None,
        description="Origen de la detección, por ejemplo mock_rules o ollama",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Nombre del modelo utilizado si aplica",
    )


class XapityChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        description="Mensaje libre enviado por el usuario a Xapity",
    )


class XapityChatResponse(BaseModel):
    request_id: str = Field(
        ...,
        description="Identificador único de la solicitud",
    )
    message: str = Field(
        ...,
        description="Mensaje original recibido por Xapity",
    )
    analysis: XapityIntentAnalysis = Field(
        ...,
        description="Resultado estructurado del análisis de intención",
    )
    reply: str = Field(
        ...,
        description="Respuesta amigable de Xapity al usuario",
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Datos opcionales asociados a la respuesta",
    )
    metadata: Optional[XapityResponseMetadata] = Field(
        default=None,
        description="Metadatos técnicos de la detección y respuesta",
    )