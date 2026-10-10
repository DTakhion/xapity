# luca/sales_dynamic_planner.py

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests
from pymongo.collection import Collection

from luca.sales_query_service import (
    get_sales_overview,
    get_total_documents,
    get_total_sales_amount,
)


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_LLM_MODEL",
    "llama3.2:3b",
)


# ==================================================
# TIPOS
# ==================================================


DynamicToolHandler = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class DynamicTool:
    """
    Herramienta determinista disponible para el planner.
    """

    name: str
    description: str
    result_semantics: str
    handler: DynamicToolHandler


@dataclass(frozen=True, slots=True)
class DynamicPlanResult:
    """
    Resultado de una consulta comercial dinámica.
    """

    answer: str
    tool_name: str
    tool_result: dict[str, Any]
    plan: dict[str, Any]


# ==================================================
# CATÁLOGO DE HERRAMIENTAS
# ==================================================


DYNAMIC_TOOLS: dict[str, DynamicTool] = {
    "sales_overview": DynamicTool(
        name="sales_overview",
        description=(
            "Obtiene un resumen comercial de ventas. "
            "Incluye cantidad total de documentos, monto total, "
            "documentos y monto por cobrar, cantidad de clientes "
            "únicos, notas de crédito, documentos anulados y "
            "documentos vinculados."
        ),
        result_semantics=(
            "result.uniqueCustomers representa la cantidad de "
            "clientes únicos identificados en los documentos "
            "comerciales del período consultado."
        ),
        handler=get_sales_overview,
    ),
    "total_documents": DynamicTool(
        name="total_documents",
        description=(
            "Obtiene la cantidad de documentos de venta y su "
            "monto total para un período."
        ),
        result_semantics=(
            "result.documentsCount representa la cantidad de "
            "documentos encontrados y result.totalAmount "
            "representa su monto total."
        ),
        handler=get_total_documents,
    ),
    "total_sales_amount": DynamicTool(
        name="total_sales_amount",
        description=(
            "Obtiene el monto total de ventas documentadas para "
            "un período. Considera facturas menos notas de crédito "
            "y excluye documentos anulados."
        ),
        result_semantics=(
            "result.totalAmount representa el monto total de "
            "ventas documentadas del período según las reglas "
            "comerciales de Luca."
        ),
        handler=get_total_sales_amount,
    ),
}


# ==================================================
# HELPERS OLLAMA
# ==================================================


def _call_ollama_json(
    prompt: str,
) -> dict[str, Any]:
    """
    Ejecuta Ollama esperando exclusivamente JSON.
    """

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
            },
        },
        timeout=45,
    )

    response.raise_for_status()

    payload = response.json()
    raw_answer = payload.get("response")

    if not isinstance(raw_answer, str):
        raise ValueError(
            "Ollama no devolvió una respuesta válida."
        )

    result = json.loads(raw_answer)

    if not isinstance(result, dict):
        raise ValueError(
            "Ollama no devolvió un objeto JSON."
        )

    return result


def _call_ollama_text(
    prompt: str,
) -> str:
    """
    Ejecuta Ollama esperando una respuesta textual.
    """

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        },
        timeout=45,
    )

    response.raise_for_status()

    payload = response.json()
    raw_answer = payload.get("response")

    if not isinstance(raw_answer, str):
        raise ValueError(
            "Ollama no devolvió una respuesta válida."
        )

    answer = raw_answer.strip()

    if not answer:
        raise ValueError(
            "Ollama devolvió una respuesta vacía."
        )

    return answer


# ==================================================
# DESCRIPCIÓN DE TOOLS
# ==================================================


def _build_tools_description() -> str:
    """
    Construye el catálogo que el LLM puede inspeccionar.
    """

    lines: list[str] = []

    for tool in DYNAMIC_TOOLS.values():
        lines.append(
            f"- {tool.name}: {tool.description}"
        )

    return "\n".join(lines)


# ==================================================
# PLANIFICACIÓN
# ==================================================


def _build_plan(
    *,
    question: str,
    year: int | None,
    month: int | None,
) -> dict[str, Any]:
    """
    Pide al LLM seleccionar una herramienta disponible.

    El LLM decide qué capacidad necesita, pero no
    ejecuta consultas ni calcula datos comerciales.
    """

    tools_description = _build_tools_description()

    prompt = f"""
Eres el planificador comercial de Xapity-Luca.

Debes decidir qué herramienta disponible permite
obtener la información necesaria para responder
la pregunta del usuario.

No inventes herramientas.
No inventes datos.
No respondas todavía la pregunta.
No hagas cálculos comerciales.
Selecciona solamente una herramienta.

HERRAMIENTAS DISPONIBLES:

{tools_description}

CONTEXTO TEMPORAL YA RESUELTO:

year: {year}
month: {month}

PREGUNTA:

{question}

Responde exclusivamente con JSON:

{{
  "tool": "nombre_de_herramienta",
  "reason": "explicación breve"
}}

Si ninguna herramienta disponible permite obtener
la información necesaria, responde:

{{
  "tool": null,
  "reason": "explicación breve"
}}
""".strip()

    plan = _call_ollama_json(prompt)

    tool_name = plan.get("tool")

    if tool_name is not None:
        if (
            not isinstance(tool_name, str)
            or tool_name not in DYNAMIC_TOOLS
        ):
            raise ValueError(
                "El planner seleccionó una herramienta "
                "no autorizada."
            )

    return plan


# ==================================================
# EJECUCIÓN DE TOOL
# ==================================================


def _execute_tool(
    *,
    tool_name: str,
    business_id: int,
    year: int | None,
    month: int | None,
    collection: Collection | None,
) -> dict[str, Any]:
    """
    Ejecuta únicamente una herramienta registrada.
    """

    tool = DYNAMIC_TOOLS.get(tool_name)

    if tool is None:
        raise ValueError(
            f"Herramienta dinámica no soportada: {tool_name}"
        )

    kwargs: dict[str, Any] = {
        "business_id": business_id,
        "year": year,
        "month": month,
    }

    if collection is not None:
        kwargs["collection"] = collection

    result = tool.handler(**kwargs)

    if not isinstance(result, dict):
        raise TypeError(
            "La herramienta dinámica debe retornar un dict."
        )

    return result


# ==================================================
# SÍNTESIS DE RESPUESTA
# ==================================================


def _build_dynamic_answer(
    *,
    question: str,
    tool_name: str,
    tool_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta final utilizando exclusivamente
    datos obtenidos desde la herramienta determinista.
    """

    tool = DYNAMIC_TOOLS[tool_name]

    serialized_result = json.dumps(
        tool_result,
        ensure_ascii=False,
        default=str,
    )

    prompt = f"""
Eres el asistente comercial de Xapity-Luca.

Responde la pregunta del usuario utilizando
exclusivamente la información entregada por
la herramienta.

SEMÁNTICA DEL RESULTADO:

{tool.result_semantics}

Examina los datos y utiliza esta semántica para
interpretar correctamente sus campos.

No inventes cifras.
No inventes clientes.
No inventes documentos.
No agregues información que no pueda deducirse
del resultado entregado.

Si el resultado realmente no contiene información
suficiente para responder la pregunta, indícalo
claramente.

Sé breve, claro y directo.

PREGUNTA:

{question}

HERRAMIENTA UTILIZADA:

{tool_name}

RESULTADO DE LA HERRAMIENTA:

{serialized_result}
""".strip()

    return _call_ollama_text(prompt)


# ==================================================
# PLANNER PÚBLICO
# ==================================================


def execute_dynamic_sales_query(
    *,
    question: str,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> DynamicPlanResult | None:
    """
    Intenta resolver una consulta comercial no cubierta
    por una intención determinista.

    Flujo:

        pregunta
            ↓
        LLM selecciona tool
            ↓
        ejecución determinista
            ↓
        LLM sintetiza respuesta

    Retorna None cuando ninguna herramienta disponible
    puede resolver la consulta.
    """

    if not isinstance(question, str):
        raise TypeError(
            "question debe ser un string."
        )

    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError(
            "question no puede estar vacía."
        )

    if not isinstance(business_id, int):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    plan = _build_plan(
        question=normalized_question,
        year=year,
        month=month,
    )

    tool_name = plan.get("tool")

    if tool_name is None:
        return None

    tool_result = _execute_tool(
        tool_name=tool_name,
        business_id=business_id,
        year=year,
        month=month,
        collection=collection,
    )

    answer = _build_dynamic_answer(
        question=normalized_question,
        tool_name=tool_name,
        tool_result=tool_result,
    )

    return DynamicPlanResult(
        answer=answer,
        tool_name=tool_name,
        tool_result=tool_result,
        plan=plan,
    )