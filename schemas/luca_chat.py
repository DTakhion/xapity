# schemas/luca_chat.py
"""
Schemas HTTP para el agente global de Xapity.

Este módulo define exclusivamente los contratos de entrada y salida
utilizados por el endpoint principal de conversación de Xapity.

No contiene:

- lógica de negocio;
- consultas a fuentes de datos;
- detección de intenciones;
- routing entre agentes;
- construcción de respuestas;
- llamadas a modelos de lenguaje.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ==================================================
# REQUEST
# ==================================================


class LucaChatRequest(BaseModel):
    """
    Solicitud HTTP para el agente global de Xapity.

    El businessId se recibe temporalmente desde el body para facilitar
    las pruebas del MVP.

    En una etapa posterior debería resolverse desde el usuario
    autenticado y su contexto de organización.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description=(
            "Pregunta o interacción escrita por el usuario."
        ),
        examples=[
            "Hola",
            "¿Qué puedes hacer?",
            "¿Cuánto dinero tengo por cobrar?",
        ],
    )

    business_id: int = Field(
        ...,
        alias="businessId",
        gt=0,
        description=(
            "Identificador de la empresa asociada "
            "a la conversación."
        ),
        examples=[70],
    )

    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description=(
            "Filtro anual explícito utilizado por capacidades "
            "que requieran contexto temporal."
        ),
        examples=[2026],
    )

    month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description=(
            "Filtro mensual explícito utilizado por capacidades "
            "que requieran contexto temporal."
        ),
        examples=[7],
    )
    
    query_from: str | None = Field(
        default=None,
        alias="queryFrom",
        description=(
            "Fecha inicial explícita para consultas de reportes "
            "en formato YYYY-MM-DD."
        ),
        examples=[
            "2026-01-01",
        ],
    )

    query_to: str | None = Field(
        default=None,
        alias="queryTo",
        description=(
            "Fecha final explícita para consultas de reportes "
            "en formato YYYY-MM-DD."
        ),
        examples=[
            "2026-09-04",
        ],
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description=(
            "Cantidad máxima de elementos retornados por "
            "capacidades que incluyan detalle."
        ),
        examples=[10],
    )


# ==================================================
# TRACE
# ==================================================


class LucaChatTrace(BaseModel):
    """
    Información técnica y auditable del procesamiento global.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    agent: str | None = Field(
        default=None,
        description=(
            "Agente que resolvió finalmente la interacción."
        ),
    )

    attempted_agents: list[str] = Field(
        default_factory=list,
        alias="attemptedAgents",
        description=(
            "Agentes evaluados por el orquestador global."
        ),
    )

    matched_rule: str | None = Field(
        default=None,
        alias="matchedRule",
        description=(
            "Regla determinista que reconoció la intención."
        ),
    )

    operation: str | None = Field(
        default=None,
        description=(
            "Operación específica ejecutada por un agente "
            "especializado, cuando corresponda."
        ),
    )

    execution_type: str | None = Field(
        default=None,
        alias="executionType",
        description=(
            "Tipo de ejecución realizada por un agente "
            "especializado."
        ),
    )

    source: str | None = Field(
        default=None,
        description=(
            "Fuente de datos utilizada, cuando corresponda."
        ),
    )

    generated_at: str | None = Field(
        default=None,
        alias="generatedAt",
        description=(
            "Fecha de generación del resultado de datos."
        ),
    )
    
    query_from: str | None = Field(
        default=None,
        alias="queryFrom",
        description=(
            "Fecha inicial efectiva utilizada por una consulta "
            "de reportes."
        ),
    )

    query_to: str | None = Field(
        default=None,
        alias="queryTo",
        description=(
            "Fecha final efectiva utilizada por una consulta "
            "de reportes."
        ),
    )

    mongo_id: str | None = Field(
        default=None,
        alias="mongoId",
        description=(
            "Identificador MongoDB del snapshot utilizado."
        ),
    )

    version: int | None = Field(
        default=None,
        description=(
            "Versión del snapshot persistido utilizado "
            "para responder."
        ),
    )

    content_hash: str | None = Field(
        default=None,
        alias="contentHash",
        description=(
            "Hash del contenido del snapshot utilizado."
        ),
    )

    loaded_at: str | None = Field(
        default=None,
        alias="loadedAt",
        description=(
            "Fecha en que el snapshot fue sincronizado "
            "desde su fuente."
        ),
    )

    response_builder: str | None = Field(
        default=None,
        alias="responseBuilder",
        description=(
            "Constructor determinista utilizado para redactar "
            "la respuesta."
        ),
    )

    deterministic: bool = Field(
        default=True,
        description=(
            "Indica si la resolución fue determinista."
        ),
    )

    handled: bool | None = Field(
        default=None,
        description=(
            "Indica si la interacción fue resuelta por alguna "
            "capacidad disponible."
        ),
    )

    implemented: bool | None = Field(
        default=None,
        description=(
            "Indica si la capacidad reconocida se encuentra "
            "implementada."
        ),
    )

    elapsed_ms: float | None = Field(
        default=None,
        alias="elapsedMs",
        ge=0,
        description=(
            "Tiempo total de procesamiento en milisegundos."
        ),
    )


# ==================================================
# ERROR
# ==================================================


class LucaChatError(BaseModel):
    """
    Información controlada de error devuelta por Xapity.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    type: str = Field(
        ...,
        description=(
            "Tipo técnico del error."
        ),
    )

    message: str = Field(
        ...,
        description=(
            "Descripción controlada del error."
        ),
    )


# ==================================================
# RESPONSE
# ==================================================


class LucaChatResponse(BaseModel):
    """
    Respuesta HTTP del agente global de Xapity.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    request_id: str = Field(
        ...,
        alias="requestId",
        description=(
            "Identificador único de la solicitud HTTP."
        ),
    )

    status: str = Field(
        ...,
        description=(
            "Estado final del procesamiento."
        ),
        examples=[
            "answered",
            "not_handled",
        ],
    )

    answer: str = Field(
        ...,
        description=(
            "Respuesta natural que será mostrada al usuario."
        ),
        examples=[
            "¡Hola! Soy Xapity, tu agente comercial.",
        ],
    )

    intent: str = Field(
        ...,
        description=(
            "Intención detectada por el agente que procesó "
            "la interacción."
        ),
        examples=[
            "greeting",
            "total_receivable",
        ],
    )

    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description=(
            "Confianza entregada por el router que reconoció "
            "la intención."
        ),
        examples=[1.0],
    )

    entities: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Entidades detectadas o resueltas durante "
            "el procesamiento."
        ),
    )

    data: Any = Field(
        default=None,
        description=(
            "Resultado estructurado producido por el agente "
            "especializado, cuando corresponda."
        ),
    )

    trace: LucaChatTrace = Field(
        ...,
        description=(
            "Trazabilidad técnica del routing y procesamiento."
        ),
    )

    error: LucaChatError | None = Field(
        default=None,
        description=(
            "Detalle controlado del error, cuando corresponda."
        ),
    )


# ==================================================
# EJEMPLOS OPENAPI
# ==================================================


LucaChatRequest.model_config["json_schema_extra"] = {
    "examples": [
        {
            "question": "Hola",
            "businessId": 70,
            "year": None,
            "month": None,
            "limit": 10,
        },
        {
            "question": (
                "¿Cuánto dinero tengo por cobrar?"
            ),
            "businessId": 70,
            "limit": 10,
        },
    ],
}


LucaChatResponse.model_config["json_schema_extra"] = {
    "examples": [
        {
            "requestId": (
                "c8f5c3b5-31b4-49ae-89ae-487db3128ab1"
            ),
            "status": "answered",
            "answer": (
                "¡Hola! Soy Xapity, tu agente comercial. "
                "¿En qué te puedo ayudar?"
            ),
            "intent": "greeting",
            "confidence": 1.0,
            "entities": {},
            "data": None,
            "trace": {
                "agent": "conversation",
                "attemptedAgents": [
                    "conversation",
                ],
                "matchedRule": "greeting",
                "responseBuilder": (
                    "build_greeting_response"
                ),
                "deterministic": True,
                "handled": True,
                "elapsedMs": 0.4,
            },
            "error": None,
        },
    ],
}

LucaChatRequest.model_config["json_schema_extra"] = {
    "examples": [
        {
            "question": "Hola",
            "businessId": 70,
            "year": None,
            "month": None,
            "queryFrom": None,
            "queryTo": None,
            "limit": 10,
        },
        {
            "question": (
                "¿Cuánto dinero tengo por cobrar?"
            ),
            "businessId": 70,
            "limit": 10,
        },
        {
            "question": (
                "Entrégame el balance general de la "
                "empresa al día de hoy"
            ),
            "businessId": 70,
            "limit": 10,
        },
        {
            "question": (
                "Muéstrame el balance general"
            ),
            "businessId": 70,
            "queryFrom": "2026-01-01",
            "queryTo": "2026-09-04",
            "limit": 10,
        },
    ],
}