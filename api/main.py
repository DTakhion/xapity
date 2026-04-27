# api/main.py
from __future__ import annotations

import os
import uuid
from typing import Optional, Any, Dict
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone

# NUEVO:
# Se construyo schemas/service.py central del proyecto en vez de redefinir otro BaseModel local.
from schemas.service import ServiceCreateRequest, ServiceResponse, ServiceUpdateRequest

# Ahora que la tarea de Felipe ya quedó lista, integramos slug y tags al flujo real.
from utils.slug import generate_slug
from utils.tags import generate_tags

# Lógica de persistencia del repo
from services.service_repo import create_service, get_services_list, update_service, delete_service

# Validación de duplicidad antes de insertar en Mongo.
from db.mongo_persistence import service_name_exists, get_service_by_service_id

# NUEVO:
# Se reutilizaron los schemas centrales del proyecto en vez de definir otros locales.
# Esto mantiene consistencia con el POST /services y evita duplicación.
from schemas.service import ServicesListResponse

from schemas.xapity_chat import (
    XapityChatRequest,
    XapityChatResponse,
    XapityIntentAnalysis,
    XapityResponseMetadata,
)

from services.xapity_service import detect_xapity_intent, build_xapity_reply

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"   # xapity/.env
load_dotenv(ENV_PATH)

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

#agregado por felix ortiz 16-03, esto es para permitir la comunicacion con front, evitando asi un error 405
from fastapi.middleware.cors import CORSMiddleware

from services.ollama_client import generate
from services.qicore_client import gate as qicore_gate


app = FastAPI(title="xapity", version="0.1.0")

#agregado por felix ortiz 16-03
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# POST /services

@app.post("/services", response_model=ServiceResponse, status_code=201)
async def create_service_endpoint(service: ServiceCreateRequest):
    """
    Crea un nuevo servicio.

    Flujo:
    1. Valida el body con ServiceCreateRequest
    2. Revisa si ya existe un servicio con el mismo nombre para el business actual
    3. Genera serviceId, slug, tags y timestamps
    4. Persiste el documento en Mongo
    5. Retorna el documento insertado
    """

    # MANTENIDO / AJUSTADO:
    # Se mantiene el businessId fijo "1" porque así se definió temporalmente
    # para esta etapa del proyecto.
    # Más adelante esto debería venir desde auth / tenant context.
    business_id = "1"

    # NUEVO:
    # Se usa la validación central contra Mongo para evitar duplicados por nombre
    # dentro del mismo businessId.
    if service_name_exists(service.name, business_id):
        raise HTTPException(
            status_code=400,
            detail="A service with this name already exists for this business."
        )

    # UUID para serviceId.
    service_id = str(uuid.uuid4())

    # timestamps UTC
    now = datetime.now(timezone.utc)
    
    # Activado   
    slug = generate_slug(service.name)
    tags = generate_tags(service.name, service.description)

    # AJUSTADO:
    # Se construye el documento final alineado con ServiceResponse
    # y con la estructura esperada en Mongo.
    document = {
        "serviceId": service_id,
        "businessId": business_id,
        "name": service.name,
        "slug": slug,
        "description": service.description,
        "category": service.category,
        "tags": tags,
        "isActive": True,
        "isDeleted": False,
        "createdAt": now,
        "updatedAt": now,
        #OPERATIVOS------------------------------
        "durationMinutes": service.durationMinutes,
        "basePrice": service.basePrice,
        "beforeCareInstructions": service.beforeCareInstructions,
        "afterCareInstructions": service.afterCareInstructions,
        "isBookableOnline": service.isBookableOnline,
        #COMERCIALES-----------------------------
        "includes": service.includes,
        "products": service.products,
    }

    # AJUSTADO:
    # Antes se llamaba create_service(document) pero luego se retornaba el document local.
    # Ahora devolvemos lo que realmente quedó insertado en Mongo,
    # incluyendo potencialmente el _id serializado.
    inserted_service = await create_service(document)

    return inserted_service


# GET /services

@app.get("/services", response_model=ServicesListResponse)
async def get_services_endpoint():
    """
    Obtiene el listado de servicios no eliminados, ordenados por fecha de creación descendente.

    Flujo:
    1. Consulta la capa repo
    2. Repo delega en la persistencia central de Mongo
    3. Se retorna items + total
    """

    try:
        # AJUSTADO:
        # Antes Dem, consultabas Mongo directamente con un cliente propio.
        # Ahora reutilizamos la capa repo para mantener la arquitectura del proyecto.
        services_data = await get_services_list()

        # MANTENIDO:
        # Se conserva el formato de respuesta esperado: items + total
        return {
            "items": services_data,
            "total": len(services_data)
        }

    except Exception as exc:
        # AJUSTADO:
        # Se mantiene manejo controlado de errores,
        # pero con mensaje más limpio y consistente.
        raise HTTPException(
            status_code=500,
            detail="Internal error while retrieving services."
        ) from exc

# PATCH /services/{serviceId}

@app.patch("/services/{serviceId}", response_model=ServiceResponse)
async def update_service_endpoint(serviceId: str, service: ServiceUpdateRequest):
    """
    Actualiza parcialmente un servicio existente por serviceId.

    Reglas:
    - Si el servicio no existe, retorna 404
    - Si no se envían campos para actualizar, retorna 400
    - Si cambia el nombre, valida duplicidad dentro del mismo businessId
    - Si cambia name, regenera slug
    - Si cambia name o description, regenera tags
    - Siempre actualiza updatedAt
    """

    existing_service = get_service_by_service_id(serviceId)

    if not existing_service:
        raise HTTPException(
            status_code=404,
            detail="Servicio no encontrado."
        )

    update_data = service.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="Sin campos para actaulizar."
        )

    business_id = existing_service["businessId"]

    # Validar duplicado solo si viene name y realmente cambia
    if "name" in update_data:
        new_name = update_data["name"]

        if new_name != existing_service["name"] and service_name_exists(new_name, business_id):
            raise HTTPException(
                status_code=400,
                detail="Un servicio con este nombre ya existe para este negocio."
            )

        update_data["slug"] = generate_slug(new_name)

    # Regeneramos tags si cambia name o description
    if "name" in update_data or "description" in update_data:
        final_name = update_data.get("name", existing_service["name"])
        final_description = update_data.get("description", existing_service["description"])
        update_data["tags"] = generate_tags(final_name, final_description)

    # Timestamp de actualización
    update_data["updatedAt"] = datetime.now(timezone.utc)

    updated_service = await update_service(serviceId, update_data)

    if not updated_service:
        raise HTTPException(
            status_code=404,
            detail="Servicio no encontrado."
        )

    return updated_service

# DELETE /services/{serviceId}

@app.delete("/services/{serviceId}", response_model=ServiceResponse)
async def delete_service_endpoint(serviceId: str):
    """
    Soft deletes an existing service by serviceId.

    Regla:
    - No elimina físicamente el documento
    - Marca isDeleted=True
    - Actualiza updatedAt
    - Si no existe o ya está eliminado, retorna 404
    """

    deleted_service = await delete_service(serviceId)

    if not deleted_service:
        raise HTTPException(
            status_code=404,
            detail="Service not found."
        )

    return deleted_service

# POST /xapity/chat

@app.post("/xapity/chat", response_model=XapityChatResponse)
async def xapity_chat_endpoint(
    req: XapityChatRequest,
    x_request_id: Optional[str] = Header(default=None),
):
    request_id = x_request_id or str(uuid.uuid4())

    # 1. Detectar intención
    analysis, detection_source = detect_xapity_intent(req.message)

    # 2. Metadata base
    metadata = XapityResponseMetadata(
        classifier_version="v1",
        detection_source=detection_source,
        model_name=None if detection_source != "ollama" else "ollama",
    )

    # 3. Caso: listar servicios
    if analysis.intent == "list_services":
        try:
            services_data = await get_services_list()

            return XapityChatResponse(
                request_id=request_id,
                message=req.message,
                analysis=analysis,
                reply=build_xapity_reply(analysis, total=len(services_data)),
                data={
                    "items": services_data,
                    "total": len(services_data),
                },
                metadata=metadata,
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "xapity_services_fetch_failed",
                    "request_id": request_id,
                },
            ) from exc

    # 4. Caso: resto de intenciones
    return XapityChatResponse(
        request_id=request_id,
        message=req.message,
        analysis=analysis,
        reply=build_xapity_reply(analysis),
        data=None,
        metadata=metadata,
    )