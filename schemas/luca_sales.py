# schemas/luca_sales.py
"""
Schemas HTTP para el agente comercial determinista de Luca.

Este módulo define exclusivamente los contratos de entrada y salida
utilizados por FastAPI.

No contiene:

- lógica de negocio;
- consultas a Mongo;
- detección de intenciones;
- construcción de respuestas;
- llamadas a modelos de lenguaje.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ==================================================
# REQUEST
# ==================================================


class LucaSalesChatRequest(BaseModel):
    """
    Solicitud HTTP para el agente comercial de Luca.

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
            "Pregunta comercial escrita por el usuario."
        ),
        examples=[
            "¿Cuánto dinero tengo por cobrar?",
        ],
    )

    business_id: int = Field(
        ...,
        alias="businessId",
        gt=0,
        description=(
            "Identificador de la empresa consultada."
        ),
        examples=[5],
    )

    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description=(
            "Filtro anual explícito. Tiene prioridad sobre "
            "el año detectado dentro de la pregunta."
        ),
        examples=[2026],
    )

    month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description=(
            "Filtro mensual explícito. Tiene prioridad sobre "
            "el mes detectado dentro de la pregunta."
        ),
        examples=[7],
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description=(
            "Cantidad máxima de documentos retornados en "
            "consultas que incluyen detalle."
        ),
        examples=[10],
    )


# ==================================================
# TRACE
# ==================================================


class LucaSalesChatTrace(BaseModel):
    """
    Información técnica y auditable del procesamiento.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    matched_rule: str | None = Field(
        default=None,
        alias="matchedRule",
        description=(
            "Regla determinista que reconoció la intención."
        ),
    )

    query_type: str | None = Field(
        default=None,
        alias="queryType",
        description=(
            "Consulta ejecutada por sales_query_service."
        ),
    )
    
    operation: str | None = Field(
        default=None,
        description=(
            "Operación solicitada sobre la intención comercial: "
            "query o explain."
        ),
    )

    execution_type: str | None = Field(
        default=None,
        alias="executionType",
        description=(
            "Tipo de ejecución realizada por el agente, ya sea "
            "una consulta o un análisis determinista."
        ),
    )

    source: str | None = Field(
        default=None,
        description=(
            "Fuente de datos utilizada por la consulta."
        ),
    )

    generated_at: str | None = Field(
        default=None,
        alias="generatedAt",
        description=(
            "Fecha de generación del resultado de datos."
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
            "Indica que la respuesta fue construida sin LLM."
        ),
    )

    implemented: bool | None = Field(
        default=None,
        description=(
            "Indica si la intención y operación reconocidas "
            "tienen una capacidad implementada."
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


class LucaSalesChatError(BaseModel):
    """
    Información controlada de error devuelta por el agente.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    type: str = Field(
        ...,
        description="Tipo técnico del error.",
    )

    message: str = Field(
        ...,
        description="Descripción controlada del error.",
    )


# ==================================================
# RESPONSE
# ==================================================


class LucaSalesChatResponse(BaseModel):
    """
    Respuesta HTTP del agente comercial determinista.
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
            "Estado del procesamiento: answered, unknown_intent, "
            "not_implemented o error."
        ),
        examples=["answered"],
    )

    answer: str = Field(
        ...,
        description=(
            "Respuesta natural que será mostrada al usuario."
        ),
        examples=[
            (
                "Tienes $12.450.000 por cobrar, "
                "distribuidos en 18 documentos."
            ),
        ],
    )

    intent: str = Field(
        ...,
        description=(
            "Intención comercial detectada."
        ),
        examples=["total_receivable"],
    )

    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description=(
            "Confianza entregada por el router determinista."
        ),
        examples=[1.0],
    )

    entities: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Entidades detectadas o resueltas para la consulta."
        ),
        examples=[
            {
                "year": 2026,
                "month": 7,
            },
        ],
    )

    data: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resultado estructurado proveniente del servicio "
            "de consulta o análisis comercial."
        ),
    )

    trace: LucaSalesChatTrace = Field(
        ...,
        description=(
            "Trazabilidad técnica de la solicitud."
        ),
    )

    error: LucaSalesChatError | None = Field(
        default=None,
        description=(
            "Detalle controlado del error, cuando corresponda."
        ),
    )


# ==================================================
# EJEMPLOS OPENAPI
# ==================================================


LucaSalesChatRequest.model_config["json_schema_extra"] = {
    "examples": [
        {
            "question": "¿Cuánto dinero tengo por cobrar?",
            "businessId": 5,
            "year": None,
            "month": None,
            "limit": 10,
        },
        {
            "question": (
                "Muéstrame las notas de crédito "
                "de enero de 2026"
            ),
            "businessId": 5,
            "limit": 20,
        },
    ],
}


LucaSalesChatResponse.model_config["json_schema_extra"] = {
    "examples": [
        {
            "requestId": (
                "c8f5c3b5-31b4-49ae-89ae-487db3128ab1"
            ),
            "status": "answered",
            "answer": (
                "Tienes $12.450.000 por cobrar, "
                "distribuidos en 18 documentos."
            ),
            "intent": "total_receivable",
            "confidence": 1.0,
            "entities": {
                "year": None,
                "month": None,
            },
            "data": {
                "documentsCount": 18,
                "totalAmount": 12450000,
            },
            "trace": {
                "matchedRule": "total_receivable",
                "queryType": "total_receivable",
                "source": "luca_sales_items",
                "generatedAt": (
                    "2026-07-27T17:00:00+00:00"
                ),
                "responseBuilder": (
                    "build_total_receivable_response"
                ),
                "deterministic": True,
                "elapsedMs": 12.4,
            },
            "error": None,
        },
    ],
}