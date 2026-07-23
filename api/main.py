# api/main.py
from __future__ import annotations

import os
import uuid
import re
from typing import Optional, Any, Dict
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone, date, timedelta

# Esta es la importanción correcta para los endpoints de Staff
from schemas.staff import StaffCreateRequest, StaffUpdateRequest, StaffResponse

from schemas.subscription import OrganizationUsageResponse

#from services.staff_repo import create_staff, get_staff_list
from services.staff_repo import (
    create_staff,
    get_staff_list,
    get_staff_by_id,
    update_staff,
    delete_staff,
)

# @app.post("/staff", response_model=StaffResponse)
# def create_staff_endpoint(staff: StaffCreate):
#     return create_staff(staff.dict())
# Comentarios:
# Este endpoint fue movido porque estaba definido antes de app = FastAPI(...).
# Además se ajustó para seguir la arquitectura del proyecto:
# endpoint -> staff_repo.py -> mongo_persistence.py -> MongoDB.
# También se reemplazó StaffCreate por StaffCreateRequest para mantener
# consistencia con ServiceCreateRequest.

# NUEVO:
# Se construyo schemas/service.py central del proyecto en vez de redefinir otro BaseModel local.
from schemas.service import ServiceCreateRequest, ServiceResponse, ServiceUpdateRequest

# Ahora que la tarea de Felipe ya quedó lista, integramos slug y tags al flujo real.
from utils.slug import generate_slug
from utils.tags import generate_tags

# Lógica de persistencia del repo
from services.service_repo import create_service, get_services_list, get_service, update_service, delete_service

# Validación de duplicidad antes de insertar en Mongo.
from db.mongo_persistence import service_name_exists, get_service_by_service_id

# NUEVO:
# Se reutilizaron los schemas centrales del proyecto en vez de definir otros locales.
# Esto mantiene consistencia con el POST /services y evita duplicación.
from schemas.service import ServicesListResponse

from schemas.availability import AvailabilityRequest, AvailabilityResponse
from schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentUpdateRequest,
    AppointmentResponse,
    AppointmentsListResponse,
)

from services.availability_service import get_availability_slots
from services.appointment_repo import (
    create_appointment,
    get_appointments_list,
    get_appointment,
    update_appointment,
    delete_appointment,
)

from services.subscription_service import (
    initialize_subscription_storage,
    get_organization_usage,
    reserve_question_credit,
    complete_question_credit,
    release_question_credit,
    SubscriptionNotFoundError,
    SubscriptionInactiveError,
    QuotaExceededError,
    UsageRequestConflictError,
    UsageEventNotFoundError,
    InvalidUsageEventStateError,
)

from schemas.xapity_chat import (
    XapityChatRequest,
    XapityChatResponse,
    XapityIntentAnalysis,
    XapityResponseMetadata,
)

from schemas.auth import (
    AuthRegisterRequest,
    AuthRegisterStartResponse,
    AuthRegisterVerifyRequest,
    AuthRegisterVerifyResponse,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthMeResponse,
    AuthUserResponse,
    AuthForgotPasswordRequest,
    AuthForgotPasswordResponse,
    AuthResetPasswordRequest,
    AuthResetPasswordResponse,
    AuthInviteUserRequest,
    AuthInviteUserResponse,
    AuthAcceptInvitationRequest,
    AuthAcceptInvitationResponse,
)

from services.auth_service import (
    register_user,
    start_user_registration,
    verify_user_registration,
    login_user,
    get_user_by_id,
    start_password_reset,
    reset_user_password,
    invite_user,
    accept_invitation,
    SECRET_KEY,
    ALGORITHM,
)

from schemas.rag import RagAnswerRequest, RagAnswerResponse
from rag.hybrid_service import answer_hybrid_question
from db.mongo_persistence import insert_maf_rag_query_log

from jose import JWTError, jwt

#from services.xapity_service import detect_xapity_intent, build_xapity_reply
from services.xapity_service import detect_xapity_intent, build_xapity_reply, normalize_message

from services.sales_service import get_sales_total_for_period
from schemas.xapity_luca import XapityLucaRequest, XapityLucaResponse
from xapity_luca.service import handle_xapity_luca_request

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"   # xapity/.env
load_dotenv(ENV_PATH)

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

#agregado por felix ortiz 16-03, esto es para permitir la comunicacion con front, evitando asi un error 405
from fastapi.middleware.cors import CORSMiddleware

from services.ollama_client import generate
from services.qicore_client import gate as qicore_gate


app = FastAPI(title="xapity", version="0.1.0")

# Migrate startup event to FastAPI lifespan API.
# Current implementation is intentionally kept for compatibility.
@app.on_event("startup")
def startup_subscription_storage() -> None:
    """
    Ensures subscription and usage-event indexes exist in MongoDB.
    """
    initialize_subscription_storage()

#agregado por felix ortiz 16-03
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer()

DEBUG = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes", "y"}
GATE_ENGINE = os.getenv("GATE_ENGINE", "ollama")

MAF_BUSINESS_ID = os.getenv("MAF_BUSINESS_ID", "maf")

MAF_ALLOWED_EMAIL_DOMAINS = [
    domain.strip().lower()
    for domain in os.getenv(
        "MAF_ALLOWED_EMAIL_DOMAINS",
        "mafchile.com",
    ).split(",")
    if domain.strip()
]


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

# ============================================================
# AUTH
# ============================================================

def extract_bearer_token(authorization: Optional[str]) -> str:
    """
    Extrae el token desde el header:
    Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header.",
        )

    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format.",
        )

    return parts[1]


async def get_current_auth_user(authorization: Optional[str]) -> Dict[str, Any]:
    """
    Valida JWT y retorna usuario actual desde Mongo.
    """
    token = extract_bearer_token(authorization)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub") or payload.get("userId")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload.",
            )

    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
        ) from exc

    user = await get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive.",
        )

    return user

def get_email_domain(email: str) -> str:
    return email.strip().lower().split("@")[-1]


def is_maf_email(email: str) -> bool:
    return get_email_domain(email) in MAF_ALLOWED_EMAIL_DOMAINS


def assert_maf_user(user: Dict[str, Any]) -> None:
    user_business_id = str(user.get("businessId", ""))

    if user_business_id != str(MAF_BUSINESS_ID):
        raise HTTPException(
            status_code=403,
            detail="Usuario no autorizado para acceder a Xapity MAF.",
        )

def assert_admin_user(user: Dict[str, Any]) -> None:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Solo usuarios admin pueden invitar nuevos usuarios.",
        )

# @app.post("/auth/register", response_model=AuthUserResponse, status_code=201)
# async def auth_register_endpoint(payload: AuthRegisterRequest):
#     """
#     Registra un usuario local en MongoDB.

#     MVP:
#     - No verifica email todavía.
#     - Crea businessId automáticamente.
#     - Guarda passwordHash, nunca password plano.
#     """
#     try:
#         if is_maf_email(payload.email):
#             payload.businessId = MAF_BUSINESS_ID

#         user = await register_user(payload)
#         return user
    
#     # try:
#     #     user = await register_user(payload)
#     #     return user

#     except ValueError as exc:
#         raise HTTPException(
#             status_code=400,
#             detail=str(exc),
#         ) from exc

#     except Exception as exc:
#         raise HTTPException(
#             status_code=500,
#             detail="Internal error while registering user.",
#         ) from exc

@app.post("/auth/register/start", response_model=AuthRegisterStartResponse)
async def auth_register_start_endpoint(payload: AuthRegisterRequest):
    """
    Starts email-verified registration.

    This endpoint does NOT create the final user.
    It creates a pending registration and sends a 6-digit code by email.
    """
    try:
        business_id = MAF_BUSINESS_ID if is_maf_email(payload.email) else None

        return await start_user_registration(
            payload=payload,
            business_id=business_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while starting registration.",
        ) from exc


@app.post(
    "/auth/register/verify",
    response_model=AuthRegisterVerifyResponse,
    status_code=201,
)
async def auth_register_verify_endpoint(payload: AuthRegisterVerifyRequest):
    """
    Verifies the email code and creates the final user.
    """
    try:
        user = await verify_user_registration(
            email=payload.email,
            code=payload.code,
        )

        return {
            "user": user,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while verifying registration.",
        ) from exc

# @app.post("/auth/register", response_model=AuthUserResponse, status_code=201)
# async def auth_register_endpoint(payload: AuthRegisterRequest):
#     try:
#         business_id = MAF_BUSINESS_ID if is_maf_email(payload.email) else None
        
#         user = await register_user(
#             payload=payload,
#             business_id=business_id,
#         )
        
#         # business_id = MAF_BUSINESS_ID if is_maf_email(payload.email) else "1"

#         # user = await register_user(
#         #     payload=payload,
#         #     business_id=business_id,
#         # )

#         return user

#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc)) from exc

#     except Exception as exc:
#         raise HTTPException(
#             status_code=500,
#             detail="Internal error while registering user.",
#         ) from exc


@app.post("/auth/login", response_model=AuthLoginResponse)
async def auth_login_endpoint(payload: AuthLoginRequest):
    """
    Login local con email + password.

    Retorna:
    - accessToken
    - tokenType
    - user
    """
    try:
        return await login_user(payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while logging in.",
        ) from exc

@app.post("/auth/forgot-password", response_model=AuthForgotPasswordResponse)
async def auth_forgot_password_endpoint(payload: AuthForgotPasswordRequest):
    """
    Starts password reset flow.

    Security:
    Always returns a generic response to avoid revealing whether
    the email is registered or not.
    """
    try:
        return await start_password_reset(payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while starting password reset.",
        ) from exc


@app.post("/auth/reset-password", response_model=AuthResetPasswordResponse)
async def auth_reset_password_endpoint(payload: AuthResetPasswordRequest):
    """
    Resets password using a valid recovery code.
    """
    try:
        return await reset_user_password(payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while resetting password.",
        ) from exc

@app.get("/auth/me", response_model=AuthMeResponse)
async def auth_me_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    authorization = f"{credentials.scheme} {credentials.credentials}"
    user = await get_current_auth_user(authorization)

    return {
        "user": user,
    }

@app.get(
    "/subscriptions/usage",
    response_model=OrganizationUsageResponse,
)
async def get_subscription_usage_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Returns the authenticated organization's subscription and quota.

    The businessId is always obtained from the authenticated user.
    It is never accepted from the frontend.
    """
    authorization = f"{credentials.scheme} {credentials.credentials}"
    user = await get_current_auth_user(authorization)

    business_id = str(user.get("businessId") or "").strip()

    if not business_id:
        raise HTTPException(
            status_code=400,
            detail="Authenticated user does not have a businessId.",
        )

    try:
        return get_organization_usage(
            business_id=business_id,
        )

    except SubscriptionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while retrieving subscription usage.",
        ) from exc

@app.post("/auth/invitations", response_model=AuthInviteUserResponse, status_code=201)
async def auth_invite_user_endpoint(
    payload: AuthInviteUserRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    authorization = f"{credentials.scheme} {credentials.credentials}"
    inviter_user = await get_current_auth_user(authorization)

    assert_admin_user(inviter_user)

    if str(inviter_user.get("businessId")) == str(MAF_BUSINESS_ID):
        if not is_maf_email(payload.email):
            raise HTTPException(
                status_code=400,
                detail="Solo se pueden invitar correos institucionales autorizados para MAF.",
            )

    try:
        return await invite_user(
            payload=payload,
            inviter_user=inviter_user,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while creating invitation.",
        ) from exc

@app.post(
    "/auth/invitations/accept",
    response_model=AuthAcceptInvitationResponse,
    status_code=201,
)
async def auth_accept_invitation_endpoint(payload: AuthAcceptInvitationRequest):
    """
    Accepts a pending invitation and creates the final user.
    """
    try:
        user = await accept_invitation(payload)

        return {
            "user": user,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while accepting invitation.",
        ) from exc

# @app.post("/xapity-maf/chat", response_model=RagAnswerResponse)
# async def xapity_maf_chat_endpoint(
#     req: RagAnswerRequest,
#     credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
#     x_request_id: Optional[str] = Header(default=None),
# ):
#     request_id = x_request_id or str(uuid.uuid4())

#     authorization = f"{credentials.scheme} {credentials.credentials}"
#     user = await get_current_auth_user(authorization)

#     assert_maf_user(user)

#     result = answer_hybrid_question(
#         query=req.query,
#     )

#     now = datetime.now(timezone.utc)

#     log_document = {
#         "requestId": request_id,
#         "businessId": MAF_BUSINESS_ID,
#         "userId": user.get("userId"),
#         "userEmail": user.get("email"),
#         "query": req.query,
#         "answer": result.get("answer"),
#         "status": result.get("status"),
#         "confidence": result.get("confidence"),
#         "matchesCount": result.get("matches_count"),
#         "sources": result.get("sources", []),
#         "createdAt": now,
#         "metadata": {
#             "endpoint": "/xapity-maf/chat",
#             "ragVersion": "hybrid-v1",
#             "mode": result.get("mode"),
#         },
#     }

#     try:
#         insert_maf_rag_query_log(log_document)
#         #await insert_maf_rag_query_log(log_document)
#     except Exception:
#         pass

#     return result

@app.post("/xapity-maf/chat", response_model=RagAnswerResponse)
async def xapity_maf_chat_endpoint(
    req: RagAnswerRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    x_request_id: Optional[str] = Header(default=None),
):
    """
    Executes the Xapity MAF hybrid chat with organization-level
    subscription quota control.

    Flow:
        authenticate user
        -> validate MAF tenant
        -> reserve credit
        -> execute hybrid engine
        -> complete credit

    On a technical execution failure:
        -> release reserved credit
    """
    request_id = (
        str(x_request_id).strip()
        if x_request_id
        else str(uuid.uuid4())
    )

    authorization = f"{credentials.scheme} {credentials.credentials}"
    user = await get_current_auth_user(authorization)

    assert_maf_user(user)

    business_id = str(user.get("businessId") or "").strip()
    user_id = str(user.get("userId") or "").strip()

    if not business_id or not user_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_authenticated_user",
                "message": "Authenticated user does not have tenant information.",
                "request_id": request_id,
            },
        )

    # ========================================================
    # 1. RESERVE SUBSCRIPTION CREDIT
    # ========================================================

    try:
        reserve_question_credit(
            business_id=business_id,
            user_id=user_id,
            endpoint="/xapity-maf/chat",
            request_id=request_id,
            credits=1,
        )

    except SubscriptionNotFoundError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "subscription_not_found",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    except SubscriptionInactiveError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "subscription_inactive",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "subscription_quota_exceeded",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    except UsageRequestConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "request_id_conflict",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "subscription_reservation_failed",
                "message": "No fue posible reservar el crédito de consulta.",
                "request_id": request_id,
            },
        ) from exc

    # ========================================================
    # 2. EXECUTE HYBRID ENGINE
    # ========================================================

    try:
        result = answer_hybrid_question(
            query=req.query,
        )

    except Exception as execution_exc:
        try:
            release_question_credit(
                business_id=business_id,
                request_id=request_id,
                failure_type="technical_error",
            )
        except Exception:
            # The original execution failure remains the primary error.
            # This secondary failure should be logged server-side later.
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "error": "xapity_maf_execution_failed",
                "message": "No fue posible procesar la consulta.",
                "request_id": request_id,
            },
        ) from execution_exc

    # ========================================================
    # 3. COMPLETE SUBSCRIPTION CREDIT
    # ========================================================

    try:
        complete_question_credit(
            business_id=business_id,
            request_id=request_id,
            engine_mode=result.get("mode"),
        )

    except (
        UsageEventNotFoundError,
        InvalidUsageEventStateError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "subscription_completion_invalid_state",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "subscription_completion_failed",
                "message": (
                    "La respuesta fue generada, pero no fue posible "
                    "confirmar el consumo del crédito."
                ),
                "request_id": request_id,
            },
        ) from exc

    # ========================================================
    # 4. RAG AUDIT LOG
    # ========================================================

    now = datetime.now(timezone.utc)

    log_document = {
        "requestId": request_id,
        "businessId": business_id,
        "userId": user_id,
        "userEmail": user.get("email"),
        "query": req.query,
        "answer": result.get("answer"),
        "status": result.get("status"),
        "confidence": result.get("confidence"),
        "matchesCount": result.get("matches_count"),
        "sources": result.get("sources", []),
        "createdAt": now,
        "metadata": {
            "endpoint": "/xapity-maf/chat",
            "ragVersion": "hybrid-v1",
            "mode": result.get("mode"),
        },
    }

    try:
        insert_maf_rag_query_log(log_document)
    except Exception:
        # The audit log must not invalidate an already successful answer.
        pass

    return result

# ============================================================
# XAPITY LUCA
# ============================================================

@app.post("/xapity-luca/chat", response_model=XapityLucaResponse)
async def xapity_luca_chat_endpoint(
    req: XapityLucaRequest,
    x_request_id: Optional[str] = Header(default=None),
):
    """
    Chat financiero Xapity-Luca.

    MVP:
    - Sin restricción de usuario.
    - business_id puede venir en el body.
    - Si no viene, usa LUCA_BUSINESS_ID desde .env.
    - requested_by puede venir en el body para auditoría.
    """

    request_id = x_request_id or str(uuid.uuid4())

    try:
        response = handle_xapity_luca_request(req)
        return response

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "xapity_luca_data_not_found",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "xapity_luca_invalid_request",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "xapity_luca_internal_error",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

@app.post("/auth/logout")
async def auth_logout_endpoint():
    """
    Logout stateless.

    MVP:
    - El backend no invalida tokens todavía.
    - El frontend debe borrar accessToken del localStorage.
    """
    return {
        "ok": True,
        "message": "Logout handled client-side.",
    }

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
    
# GET /services/{serviceId}

@app.get("/services/{serviceId}", response_model=ServiceResponse)
async def get_service_endpoint(serviceId: str):
    """
    Obtiene un servicio específico por serviceId.

    Reglas:
    - Busca por serviceId
    - Solo retorna servicios no eliminados
    - Si no existe o está eliminado, retorna 404
    """

    try:
        service = await get_service(serviceId)

        if not service:
            raise HTTPException(
                status_code=404,
                detail="Service not found.",
            )

        return service

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while retrieving service.",
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
            detail="Sin campos para actualizar."
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

def get_previous_month_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()

    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)

    return first_day_previous_month, last_day_previous_month


def format_clp(value: float) -> str:
    return f"${int(round(value)):,.0f}".replace(",", ".")

def get_next_weekday(target_weekday: int, today: date | None = None) -> date:
    """
    Retorna la próxima fecha para un día de la semana.
    Monday=0 ... Sunday=6.
    """
    today = today or date.today()
    days_ahead = target_weekday - today.weekday()

    if days_ahead < 0:
        days_ahead += 7

    return today + timedelta(days=days_ahead)


# def extract_requested_date_from_message(message: str) -> date | None:
#     normalized = normalize_message(message)

#     weekday_map = {
#         "lunes": 0,
#         "martes": 1,
#         "miercoles": 2,
#         "jueves": 3,
#         "viernes": 4,
#         "sabado": 5,
#         "domingo": 6,
#     }

#     if "hoy" in normalized:
#         return date.today()

#     if "manana" in normalized:
#         return date.today() + timedelta(days=1)

#     for word, weekday in weekday_map.items():
#         if word in normalized:
#             return get_next_weekday(weekday)

#     return None

def extract_requested_date_from_message(message: str) -> date | None:
    """
    Extrae una fecha desde el mensaje del usuario.

    Soporta:
    - hoy
    - mañana
    - lunes, martes, miércoles...
    - lunes 11 de mayo
    - 11 de mayo
    - 11/05
    - 11-05

    MVP:
    - Si no viene año, usa el año actual.
    """

    normalized = normalize_message(message)

    today = date.today()
    current_year = today.year

    month_map = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    weekday_map = {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "domingo": 6,
    }

    if "hoy" in normalized:
        return today

    if "manana" in normalized:
        return today + timedelta(days=1)

    # Caso: "lunes 11 de mayo", "11 de mayo", "lunes 11 mayo"
    month_names = "|".join(month_map.keys())

    match = re.search(
        rf"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)?\s*"
        rf"\b(\d{{1,2}})\s*(?:de\s*)?({month_names})\b",
        normalized,
    )

    if match:
        day = int(match.group(1))
        month = month_map[match.group(2)]

        try:
            return date(current_year, month, day)
        except ValueError:
            return None

    # Caso: "11/05" o "11-05"
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", normalized)

    if match:
        day = int(match.group(1))
        month = int(match.group(2))

        try:
            return date(current_year, month, day)
        except ValueError:
            return None

    # Caso: "lunes", "martes", etc.
    for word, weekday in weekday_map.items():
        if word in normalized:
            return get_next_weekday(weekday, today=today)

    return None


def extract_requested_time_from_message(message: str) -> str | None:
    normalized = normalize_message(message)

    # Casos: 10:00, 09:30, 15:45
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", normalized)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        return f"{hour:02d}:{minute:02d}"

    # Casos: 10am, 10 am, 3pm, 3 pm
    match = re.search(r"\b(\d{1,2})\s*(am|pm)\b", normalized)
    if match:
        hour = int(match.group(1))
        meridian = match.group(2)

        if meridian == "pm" and hour < 12:
            hour += 12

        if meridian == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:00"

    # Caso simple MVP: "a las 10"
    match = re.search(r"\ba las (\d{1,2})\b", normalized)
    if match:
        hour = int(match.group(1))

        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    return None


async def find_service_from_message(message: str) -> Dict[str, Any] | None:
    normalized = normalize_message(message)
    services_data = await get_services_list()

    for service in services_data:
        service_name = normalize_message(service.get("name", ""))

        if service_name and service_name in normalized:
            return service

    return None

def extract_service_query_from_staff_message(message: str) -> str:
    """
    Extrae una aproximación del nombre del servicio desde frases como:
    - qué staff tienes para biopsia clínica
    - quién atiende mantenimiento de robots
    """
    normalized = normalize_message(message)

    patterns = [
        r"staff tienes para (.+)",
        r"staff para (.+)",
        r"profesionales tienes para (.+)",
        r"profesionales para (.+)",
        r"especialistas para (.+)",
        r"quien atiende (.+)",
        r"quienes atienden (.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(1).strip()

    return normalized


async def find_staff_by_service_id(service_id: str) -> list[Dict[str, Any]]:
    """
    Busca staff activo/no eliminado asociado a un serviceId.
    """
    staff_data = await get_staff_list()

    return [
        staff_member
        for staff_member in staff_data
        if service_id in (staff_member.get("serviceIds") or [])
    ]

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
    
    # 4. Caso: consultar staff por servicio
    if analysis.intent == "staff_by_service":
        try:
            business_id = "1"

            service = await find_service_from_message(req.message)

            if not service:
                service_query = extract_service_query_from_staff_message(req.message)

                return XapityChatResponse(
                    request_id=request_id,
                    message=req.message,
                    analysis=analysis,
                    reply=(
                        f"No encontré un servicio llamado '{service_query}'. "
                        "Puedes revisar los servicios disponibles o escribir el nombre del servicio con más detalle."
                    ),
                    data={
                        "serviceFound": False,
                        "serviceQuery": service_query,
                    },
                    metadata=metadata,
                )

            # =====================================================
            # NUEVO:
            # Si el usuario además entrega día y hora, no respondemos
            # solo staff asociado al servicio.
            # Respondemos staff realmente disponible en ese horario.
            #
            # Ejemplos:
            # - qué staff tienes para mantenimiento de robots el lunes a las 10
            # - qué profesionales tienes para biopsia clínica mañana a las 15:00
            # =====================================================
            requested_date = extract_requested_date_from_message(req.message)
            requested_start = extract_requested_time_from_message(req.message)

            if requested_date and requested_start:
                availability = await get_availability_slots(
                    service_id=service["serviceId"],
                    target_date=requested_date,
                    start_date=None,
                    end_date=None,
                    staff_id=None,
                    business_id=business_id,
                )

                matching_slots = [
                    slot
                    for slot in availability.get("availableSlots", [])
                    if slot.get("start") == requested_start
                ]

                if not matching_slots:
                    return XapityChatResponse(
                        request_id=request_id,
                        message=req.message,
                        analysis=analysis,
                        reply=(
                            f"Para {service['name']} no encontré staff disponible "
                            f"el {requested_date.isoformat()} a las {requested_start}. "
                            "Puedes intentar con otro horario."
                        ),
                        data={
                            "serviceFound": True,
                            "service": service,
                            "requestedDate": requested_date.isoformat(),
                            "requestedStart": requested_start,
                            "availableStaff": [],
                            "availableSlots": availability.get("availableSlots", []),
                            "total": 0,
                        },
                        metadata=metadata,
                    )

                staff_names = ", ".join(
                    slot.get("staffName", "Staff sin nombre")
                    for slot in matching_slots
                )

                return XapityChatResponse(
                    request_id=request_id,
                    message=req.message,
                    analysis=analysis,
                    reply=(
                        f"Para {service['name']} el {requested_date.isoformat()} "
                        f"a las {requested_start} tengo disponible a: {staff_names}."
                    ),
                    data={
                        "serviceFound": True,
                        "service": service,
                        "requestedDate": requested_date.isoformat(),
                        "requestedStart": requested_start,
                        "availableStaff": matching_slots,
                        "total": len(matching_slots),
                    },
                    metadata=metadata,
                )

            # =====================================================
            # FLUJO ACTUAL:
            # Si no viene día/hora, respondemos staff asociado al servicio.
            # Esto mantiene el comportamiento que ya probaste con éxito.
            # =====================================================
            staff_matches = await find_staff_by_service_id(service["serviceId"])

            if not staff_matches:
                return XapityChatResponse(
                    request_id=request_id,
                    message=req.message,
                    analysis=analysis,
                    reply=(
                        f"Encontré el servicio {service['name']}, pero todavía no hay staff asociado "
                        "a ese servicio."
                    ),
                    data={
                        "serviceFound": True,
                        "service": service,
                        "staff": [],
                        "total": 0,
                    },
                    metadata=metadata,
                )

            staff_names = ", ".join(
                staff_member.get("name", "Staff sin nombre")
                for staff_member in staff_matches
            )

            return XapityChatResponse(
                request_id=request_id,
                message=req.message,
                analysis=analysis,
                reply=(
                    f"Para {service['name']} tengo disponible el siguiente staff: "
                    f"{staff_names}."
                ),
                data={
                    "serviceFound": True,
                    "service": service,
                    "staff": staff_matches,
                    "total": len(staff_matches),
                },
                metadata=metadata,
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "xapity_staff_by_service_failed",
                    "request_id": request_id,
                },
            ) from exc
    
    # # 4. Caso: consultar staff por servicio
    # if analysis.intent == "staff_by_service":
    #     try:
    #         service = await find_service_from_message(req.message)

    #         if not service:
    #             service_query = extract_service_query_from_staff_message(req.message)

    #             return XapityChatResponse(
    #                 request_id=request_id,
    #                 message=req.message,
    #                 analysis=analysis,
    #                 reply=(
    #                     f"No encontré un servicio llamado '{service_query}'. "
    #                     "Puedes revisar los servicios disponibles o escribir el nombre del servicio con más detalle."
    #                 ),
    #                 data={
    #                     "serviceFound": False,
    #                     "serviceQuery": service_query,
    #                 },
    #                 metadata=metadata,
    #             )

    #         staff_matches = await find_staff_by_service_id(service["serviceId"])

    #         if not staff_matches:
    #             return XapityChatResponse(
    #                 request_id=request_id,
    #                 message=req.message,
    #                 analysis=analysis,
    #                 reply=(
    #                     f"Encontré el servicio {service['name']}, pero todavía no hay staff asociado "
    #                     "a ese servicio."
    #                 ),
    #                 data={
    #                     "serviceFound": True,
    #                     "service": service,
    #                     "staff": [],
    #                     "total": 0,
    #                 },
    #                 metadata=metadata,
    #             )

    #         staff_names = ", ".join(
    #             staff_member.get("name", "Staff sin nombre")
    #             for staff_member in staff_matches
    #         )

    #         return XapityChatResponse(
    #             request_id=request_id,
    #             message=req.message,
    #             analysis=analysis,
    #             reply=(
    #                 f"Para {service['name']} tengo disponible el siguiente staff: "
    #                 f"{staff_names}."
    #             ),
    #             data={
    #                 "serviceFound": True,
    #                 "service": service,
    #                 "staff": staff_matches,
    #                 "total": len(staff_matches),
    #             },
    #             metadata=metadata,
    #         )

    #     except Exception as exc:
    #         raise HTTPException(
    #             status_code=500,
    #             detail={
    #                 "error": "xapity_staff_by_service_failed",
    #                 "request_id": request_id,
    #             },
    #         ) from exc
    
    # 5. Caso: crear agenda / appointment
    if analysis.intent == "create_appointment":
        try:
            business_id = "1"

            service = await find_service_from_message(req.message)
            requested_date = extract_requested_date_from_message(req.message)
            requested_start = extract_requested_time_from_message(req.message)

            if not service or not requested_date or not requested_start:
                return XapityChatResponse(
                    request_id=request_id,
                    message=req.message,
                    analysis=analysis,
                    reply=(
                        "Puedo ayudarte a agendar, pero necesito identificar claramente "
                        "el servicio, el día y la hora. Por ejemplo: "
                        "'Necesito agendar corte de pelo para el lunes a las 10am'."
                    ),
                    data={
                        "missing": {
                            "service": service is None,
                            "date": requested_date is None,
                            "time": requested_start is None,
                        }
                    },
                    metadata=metadata,
                )

            availability = await get_availability_slots(
                service_id=service["serviceId"],
                target_date=requested_date,
                start_date=None,
                end_date=None,
                staff_id=None,
                business_id=business_id,
            )

            matching_slot = None

            for slot in availability.get("availableSlots", []):
                if slot.get("start") == requested_start:
                    matching_slot = slot
                    break

            if not matching_slot:
                return XapityChatResponse(
                    request_id=request_id,
                    message=req.message,
                    analysis=analysis,
                    reply=(
                        f"No encontré disponibilidad para {service['name']} "
                        f"el {requested_date.isoformat()} a las {requested_start}. "
                        "Puedes intentar con otro horario."
                    ),
                    data={
                        "service": service,
                        "requestedDate": requested_date.isoformat(),
                        "requestedStart": requested_start,
                        "availableSlots": availability.get("availableSlots", []),
                        "totalAvailableSlots": availability.get("total", 0),
                    },
                    metadata=metadata,
                )

            now = datetime.now(timezone.utc)
            appointment_id = str(uuid.uuid4())

            document = {
                "appointmentId": appointment_id,
                "businessId": business_id,
                "serviceId": matching_slot["serviceId"],
                "serviceName": matching_slot["serviceName"],
                "staffId": matching_slot["staffId"],
                "staffName": matching_slot["staffName"],
                "customerName": "Cliente Xapity",
                "customerPhone": None,
                "customerEmail": None,
                #"date": matching_slot["date"],
                "date": matching_slot["date"].isoformat()
                if hasattr(matching_slot["date"], "isoformat")
                else matching_slot["date"],
                "start": matching_slot["start"],
                "end": matching_slot["end"],
                "status": "scheduled",
                "notes": f"Reserva creada desde conversación: {req.message}",
                "isDeleted": False,
                "createdAt": now,
                "updatedAt": now,
            }

            inserted_appointment = await create_appointment(document)

            return XapityChatResponse(
                request_id=request_id,
                message=req.message,
                analysis=analysis,
                reply=(
                    f"Listo, agendé {matching_slot['serviceName']} "
                    f"con {matching_slot['staffName']} para el "
                    f"{requested_date.isoformat()} de "
                    f"{matching_slot['start']} a {matching_slot['end']}."
                ),
                data=inserted_appointment,
                metadata=metadata,
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "xapity_create_appointment_failed",
                    "request_id": request_id,
                },
            ) from exc
    
    # 6. Caso: total de ventas / ingresos por venta
    if analysis.intent == "sales_total":
        try:
            # MVP:
            # businessId fijo para Luca.
            # Más adelante debe venir desde auth / tenant context.
            business_id = 5

            # MVP:
            # por ahora resolvemos "mes pasado".
            start_date, end_date = get_previous_month_range()

            result = get_sales_total_for_period(
                business_id=business_id,
                start_date=start_date,
                end_date=end_date,
                include_documents=[33, 34],
            )

            total = float(result.get("totalIngresosVenta") or 0)
            total_documentos = int(result.get("totalDocumentos") or 0)

            reply = (
                f"El monto total de ingresos por ventas para el periodo "
                f"{start_date.isoformat()} al {end_date.isoformat()} "
                f"es de {format_clp(total)}, considerando {total_documentos} documentos."
            )

            return XapityChatResponse(
                request_id=request_id,
                message=req.message,
                analysis=analysis,
                reply=reply,
                data={
                    "businessId": business_id,
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "totalIngresosVenta": total,
                    "totalIngresosVentaFormatted": format_clp(total),
                    "totalDocumentos": total_documentos,
                    "byDocumentType": result.get("byDocumentType", []),
                },
                metadata=metadata,
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "xapity_sales_total_failed",
                    "request_id": request_id,
                },
            ) from exc

    # 7. Caso: resto de intenciones
    return XapityChatResponse(
        request_id=request_id,
        message=req.message,
        analysis=analysis,
        reply=build_xapity_reply(analysis),
        data=None,
        metadata=metadata,
    )

# POST /staff

@app.post("/staff", response_model=StaffResponse, status_code=201)
async def create_staff_endpoint(staff: StaffCreateRequest):
    """
    Crea un nuevo miembro del staff.

    Flujo:
    1. Valida el body con StaffCreateRequest
    2. Genera staffId, businessId y timestamps
    3. Persiste el documento en Mongo
    4. Retorna el documento insertado
    """

    business_id = "1"
    staff_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    document = {
        "staffId": staff_id,
        "businessId": business_id,
        "name": staff.name,
        "role": staff.role,
        "email": staff.email,
        "phone": staff.phone,
        "specialties": staff.specialties,
        "serviceIds": staff.serviceIds,
        "notes": staff.notes,
        "workingHours": staff.workingHours.model_dump() if staff.workingHours else None,
        "isActive": True,
        "isDeleted": False,
        "createdAt": now,
        "updatedAt": now,
    }

    inserted_staff = await create_staff(document)

    return inserted_staff

# GET /staff

@app.get("/staff")
async def get_staff_endpoint():
    """
    Obtiene el listado de staff no eliminado.
    """

    try:
        staff_data = await get_staff_list()

        return {
            "items": staff_data,
            "total": len(staff_data)
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while retrieving staff."
        ) from exc

# GET /staff/{staffId}

@app.get("/staff/{staffId}", response_model=StaffResponse)
async def get_staff_by_id_endpoint(staffId: str):
    """
    Obtiene un miembro específico del staff por staffId.

    Reglas:
    - Busca por staffId
    - Solo retorna staff no eliminado
    - Si no existe o está eliminado, retorna 404
    """

    try:
        staff = await get_staff_by_id(staffId)

        if not staff:
            raise HTTPException(
                status_code=404,
                detail="Staff not found.",
            )

        return staff

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while retrieving staff member.",
        ) from exc

# PATCH /staff/{staffId}

@app.patch("/staff/{staffId}", response_model=StaffResponse)
async def update_staff_endpoint(staffId: str, staff: StaffUpdateRequest):
    """
    Actualiza parcialmente un miembro del staff.

    Reglas:
    - Busca por staffId
    - Solo actualiza staff activo y no eliminado
    - Si no existe, está inactivo o eliminado, retorna 404
    - Si no se envían campos para actualizar, retorna 400
    - Siempre actualiza updatedAt
    """

    update_data = staff.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update.",
        )
    
    update_data = staff.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update.",
        )
    
    update_data["updatedAt"] = datetime.now(timezone.utc)
    
    updated_staff = await update_staff(staffId, update_data)

    # if "workingHours" in update_data and update_data["workingHours"] is not None:
    #     update_data["workingHours"] = update_data["workingHours"].model_dump()

    update_data["updatedAt"] = datetime.now(timezone.utc)

    updated_staff = await update_staff(staffId, update_data)

    if not updated_staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found, inactive, or deleted.",
        )

    return updated_staff

# DELETE /staff/{staffId}

@app.delete("/staff/{staffId}", response_model=StaffResponse)
async def delete_staff_endpoint(staffId: str):
    """
    Soft delete de un miembro del staff.

    Regla:
    - No elimina físicamente el documento
    - Marca isDeleted=True
    - Marca isActive=False
    - Actualiza updatedAt
    - Si no existe o ya está eliminado, retorna 404
    """

    deleted_staff = await delete_staff(staffId)

    if not deleted_staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found.",
        )

    return deleted_staff

# POST /availability

@app.post("/availability", response_model=AvailabilityResponse)
async def get_availability_endpoint(req: AvailabilityRequest):
    """
    Calcula disponibilidad para un servicio.

    No guarda datos en Mongo.
    Solo calcula slots disponibles según:
    - servicio
    - staff asociado
    - workingHours
    - appointments existentes
    """

    try:
        availability = await get_availability_slots(
            service_id=req.serviceId,
            target_date=req.targetDate,
            start_date=req.startDate,
            end_date=req.endDate,
            staff_id=req.staffId,
            business_id="1",
        )

        return availability

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while calculating availability.",
        ) from exc


# POST /appointments

@app.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment_endpoint(appointment: AppointmentCreateRequest):
    """
    Crea una reserva real en Mongo.

    Reglas:
    - El frontend envía date + start.
    - El backend calcula end usando durationMinutes del servicio.
    """

    business_id = "1"
    appointment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    service = get_service_by_service_id(appointment.serviceId)

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Service not found.",
        )

    duration_minutes = service.get("durationMinutes")

    if not duration_minutes:
        raise HTTPException(
            status_code=400,
            detail="Service does not have durationMinutes configured.",
        )

    try:
        start_time = datetime.strptime(appointment.start, "%H:%M")
        end_time = start_time + timedelta(minutes=int(duration_minutes))
        calculated_end = end_time.strftime("%H:%M")

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Start time must use HH:MM format, for example '09:00'.",
        ) from exc

    document = {
        "appointmentId": appointment_id,
        "businessId": business_id,
        "serviceId": appointment.serviceId,
        "serviceName": service.get("name"),
        "staffId": appointment.staffId,
        "staffName": None,
        "customerName": appointment.customerName,
        "customerPhone": appointment.customerPhone,
        "customerEmail": appointment.customerEmail,
        #"date": appointment.date,
        "date": appointment.date.isoformat(),
        "start": appointment.start,
        "end": calculated_end,
        "status": "scheduled",
        "notes": appointment.notes,
        "isDeleted": False,
        "createdAt": now,
        "updatedAt": now,
    }

    inserted_appointment = await create_appointment(document)

    return inserted_appointment


# GET /appointments

@app.get("/appointments", response_model=AppointmentsListResponse)
async def get_appointments_endpoint():
    """
    Lista reservas no eliminadas.
    """

    try:
        appointments_data = await get_appointments_list()

        return {
            "items": appointments_data,
            "total": len(appointments_data),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal error while retrieving appointments.",
        ) from exc


# GET /appointments/{appointmentId}

@app.get("/appointments/{appointmentId}", response_model=AppointmentResponse)
async def get_appointment_endpoint(appointmentId: str):
    """
    Obtiene una reserva por appointmentId.
    """

    appointment = await get_appointment(appointmentId)

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found.",
        )

    return appointment


# PATCH /appointments/{appointmentId}

@app.patch("/appointments/{appointmentId}", response_model=AppointmentResponse)
async def update_appointment_endpoint(
    appointmentId: str,
    appointment: AppointmentUpdateRequest,
):
    """
    Actualiza parcialmente una reserva.
    """

    update_data = appointment.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update.",
        )

    update_data["updatedAt"] = datetime.now(timezone.utc)

    updated_appointment = await update_appointment(appointmentId, update_data)

    if not updated_appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found.",
        )

    return updated_appointment


# DELETE /appointments/{appointmentId}

@app.delete("/appointments/{appointmentId}", response_model=AppointmentResponse)
async def delete_appointment_endpoint(appointmentId: str):
    """
    Soft delete de una reserva.
    """

    deleted_appointment = await delete_appointment(appointmentId)

    if not deleted_appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found.",
        )

    return deleted_appointment