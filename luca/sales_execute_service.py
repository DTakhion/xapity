# luca/sales_execute_service.py

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path

from pymongo.collection import Collection

from luca.sales_proposal_service import (
    propose_receivable_documents,
)


# ==================================================
# CONFIGURACIÓN
# ==================================================


DEFAULT_LUCA_API_BASE_URL = (
    "https://luca-api-dev-bvxil9xk.ue.gateway.dev"
)


# ==================================================
# HELPERS
# ==================================================


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_string(
    value: Any,
    default: str | None = None,
) -> str | None:
    if value is None:
        return default

    normalized = str(value).strip()

    return normalized or default


def _get_luca_api_base_url() -> str:
    return (
        os.getenv("LUCA_API_BASE_URL")
        or DEFAULT_LUCA_API_BASE_URL
    ).rstrip("/")


def _get_json(
    *,
    url: str,
    access_token: str,
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    """
    Ejecuta un GET autenticado contra Luca.

    El access token se utiliza solamente durante la llamada
    y nunca se incorpora en el resultado retornado.
    """

    if not access_token.strip():
        raise ValueError(
            "access_token no puede estar vacío."
        )

    request = Request(
        url,
        method="GET",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            payload = response.read().decode(
                "utf-8"
            )

    except HTTPError as exc:
        raise RuntimeError(
            "Luca respondió con error HTTP "
            f"{exc.code} al resolver contexto "
            "de ejecución."
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            "No fue posible conectar con Luca "
            "para resolver contexto de ejecución."
        ) from exc

    try:
        data = json.loads(payload)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Luca retornó una respuesta JSON inválida."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "Luca retornó una estructura inesperada."
        )

    return data

def _load_luca_access_token() -> str:
    token_path = Path(
        "results/luca_token.json"
    )

    if not token_path.exists():
        raise RuntimeError(
            "No existe results/luca_token.json."
        )

    with token_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    if payload.get("token_expired"):
        raise RuntimeError(
            "El token de Luca está expirado."
        )

    access_token = (
        payload.get("access_token")
        or payload.get("accessToken")
        or payload.get("token")
    )

    if not access_token:
        raise RuntimeError(
            "No encontré access_token en "
            "results/luca_token.json."
        )

    return str(access_token).strip()

# ==================================================
# RESOLUCIÓN DE REMITENTE
# ==================================================


def resolve_sender_identity(
    *,
    access_token: str,
) -> dict[str, Any]:
    """
    Resuelve el usuario autenticado de Luca mediante:

        GET /v1/users/me

    Esta identidad representa al usuario comercial que
    está solicitando la ejecución.
    """

    url = (
        f"{_get_luca_api_base_url()}"
        "/v1/users/me"
    )

    user = _get_json(
        url=url,
        access_token=access_token,
    )

    first_name = _safe_string(
        user.get("firstname")
    )

    last_name = _safe_string(
        user.get("lastname")
    )

    display_name = " ".join(
        value
        for value in (
            first_name,
            last_name,
        )
        if value
    ).strip()

    email = (
        _safe_string(
            user.get("emailNormalized")
        )
        or _safe_string(
            user.get("email")
        )
    )

    organization = user.get(
        "currentOrganization",
        {},
    )

    if not isinstance(
        organization,
        dict,
    ):
        organization = {}

    return {
        "userId": user.get("id"),
        "displayName": (
            display_name
            or email
            or "Usuario Luca"
        ),
        "email": email,
        "active": bool(
            user.get("active")
        ),
        "subscriptionExpired": bool(
            user.get(
                "subscriptionExpired",
                False,
            )
        ),
        "organizationId": (
            user.get(
                "currentOrganizationId"
            )
        ),
        "organizationName": (
            organization.get("name")
        ),
    }


# ==================================================
# RESOLUCIÓN DE CONTACTO DEL CLIENTE
# ==================================================


def resolve_company_contact(
    *,
    business_id: int,
    company_id: int,
    access_token: str,
) -> dict[str, Any]:
    """
    Resuelve los datos maestros del cliente deudor mediante:

        GET /v1/business/{businessId}/empresa/{idEmpresa}?type=venta
    """

    query = urlencode(
        {
            "type": "venta",
        }
    )

    url = (
        f"{_get_luca_api_base_url()}"
        f"/v1/business/{business_id}"
        f"/empresa/{company_id}"
        f"?{query}"
    )

    company = _get_json(
        url=url,
        access_token=access_token,
    )

    return {
        "companyId": company.get("id"),
        "rut": (
            company.get("rutEmpresa")
        ),
        "companyName": (
            company.get("razonSocial")
        ),
        "contactName": (
            company.get("contact")
        ),
        "email": (
            company.get("mail")
        ),
        "phone": (
            company.get("phone")
        ),
        "paymentTermDays": (
            company.get(
                "diasVencimiento"
            )
        ),
    }


# ==================================================
# EXTRACCIÓN DE EMPRESA DESDE LA PROPUESTA
# ==================================================


def _resolve_priority_customer(
    proposal_result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Resuelve el cliente prioritario para una acción
    de cobranza.

    Prioridad:

    1. Target explícito de la propuesta principal.
    2. Cliente principal identificado por la capa
       de análisis de cuentas por cobrar.
    """

    proposal = proposal_result.get(
        "proposal",
        {},
    )

    # --------------------------------------------------
    # 1. Target explícito de la propuesta
    # --------------------------------------------------

    if isinstance(
        proposal,
        dict,
    ):
        primary = proposal.get(
            "primaryProposal"
        )

        if isinstance(
            primary,
            dict,
        ):
            target = primary.get(
                "target",
                {},
            )

            if isinstance(
                target,
                dict,
            ):
                customer_rut = _safe_string(
                    target.get(
                        "customerRut"
                    )
                )

                customer_name = _safe_string(
                    target.get(
                        "customerName"
                    )
                )

                if (
                    customer_rut
                    or customer_name
                ):
                    return {
                        "customerRut": customer_rut,
                        "customerName": customer_name,
                    }

    # --------------------------------------------------
    # 2. Fallback:
    # Cliente principal determinado por EXPLAIN
    # --------------------------------------------------

    facts = proposal_result.get(
        "facts",
        {},
    )

    if not isinstance(
        facts,
        dict,
    ):
        return None

    explanation = facts.get(
        "explanation",
        {},
    )

    if not isinstance(
        explanation,
        dict,
    ):
        return None

    analysis = explanation.get(
        "analysis",
        {},
    )

    if not isinstance(
        analysis,
        dict,
    ):
        return None

    primary_customer = analysis.get(
        "primaryCustomer"
    )

    if not isinstance(
        primary_customer,
        dict,
    ):
        return None

    customer_rut = _safe_string(
        primary_customer.get(
            "customerRut"
        )
    )

    customer_name = _safe_string(
        primary_customer.get(
            "customerName"
        )
    )

    if not (
        customer_rut
        or customer_name
    ):
        return None

    return {
        "customerRut": customer_rut,
        "customerName": customer_name,
    }


def _resolve_company_id_from_explanation(
    *,
    proposal_result: dict[str, Any],
    customer_rut: str | None,
    customer_name: str | None,
) -> int | None:
    """
    Busca el idEmpresa dentro de los documentos factualizados.

    La búsqueda prioriza RUT y utiliza razón social
    solamente como fallback.
    """

    facts = proposal_result.get(
        "facts",
        {},
    )

    if not isinstance(
        facts,
        dict,
    ):
        return None

    explanation = facts.get(
        "explanation",
        {},
    )

    if not isinstance(
        explanation,
        dict,
    ):
        return None

    explanation_facts = explanation.get(
        "facts",
        {},
    )

    if not isinstance(
        explanation_facts,
        dict,
    ):
        return None

    receivables = explanation_facts.get(
        "receivables",
        {},
    )

    if not isinstance(
        receivables,
        dict,
    ):
        return None

    result = receivables.get(
        "result",
        {},
    )

    if not isinstance(
        result,
        dict,
    ):
        return None

    documents = result.get(
        "documents",
        [],
    )

    if not isinstance(
        documents,
        list,
    ):
        return None

    normalized_rut = (
        customer_rut.upper()
        if customer_rut
        else None
    )

    normalized_name = (
        customer_name.upper()
        if customer_name
        else None
    )

    for document in documents:
        if not isinstance(
            document,
            dict,
        ):
            continue

        document_rut = _safe_string(
            document.get(
                "customerRut"
            )
        )

        document_name = _safe_string(
            document.get(
                "customerName"
            )
        )

        rut_matches = (
            normalized_rut is not None
            and document_rut is not None
            and document_rut.upper()
            == normalized_rut
        )

        name_matches = (
            normalized_rut is None
            and normalized_name is not None
            and document_name is not None
            and document_name.upper()
            == normalized_name
        )

        if not (
            rut_matches
            or name_matches
        ):
            continue

        company_id = _safe_int(
            document.get(
                "companyId"
            ),
            default=0,
        )

        if company_id > 0:
            return company_id

    return None


# ==================================================
# DOCUMENTOS DEL CLIENTE
# ==================================================


def _resolve_customer_receivables(
    *,
    proposal_result: dict[str, Any],
    customer_rut: str | None,
    customer_name: str | None,
) -> list[dict[str, Any]]:
    """
    Obtiene solamente los documentos pendientes
    correspondientes al cliente priorizado.
    """

    try:
        documents = (
            proposal_result[
                "facts"
            ][
                "explanation"
            ][
                "facts"
            ][
                "receivables"
            ][
                "result"
            ][
                "documents"
            ]
        )

    except (
        KeyError,
        TypeError,
    ):
        return []

    if not isinstance(
        documents,
        list,
    ):
        return []

    normalized_rut = (
        customer_rut.upper()
        if customer_rut
        else None
    )

    normalized_name = (
        customer_name.upper()
        if customer_name
        else None
    )

    matched: list[
        dict[str, Any]
    ] = []

    for document in documents:
        if not isinstance(
            document,
            dict,
        ):
            continue

        document_rut = _safe_string(
            document.get(
                "customerRut"
            )
        )

        document_name = _safe_string(
            document.get(
                "customerName"
            )
        )

        if (
            normalized_rut
            and document_rut
            and document_rut.upper()
            == normalized_rut
        ):
            matched.append(
                document
            )
            continue

        if (
            normalized_rut is None
            and normalized_name
            and document_name
            and document_name.upper()
            == normalized_name
        ):
            matched.append(
                document
            )

    return matched


# ==================================================
# CONSTRUCCIÓN DEL MENSAJE
# ==================================================


def _build_collection_email_draft(
    *,
    sender: dict[str, Any],
    recipient: dict[str, Any],
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Construye una plantilla determinista de cobranza.

    El mensaje se prepara para revisión del usuario.
    No se envía desde esta función.
    """

    customer_name = (
        recipient.get("companyName")
        or "cliente"
    )

    contact_name = (
        recipient.get("contactName")
    )

    sender_name = (
        sender.get("displayName")
        or "Equipo comercial"
    )

    organization_name = (
        sender.get(
            "organizationName"
        )
    )

    total_amount = sum(
        _safe_float(
            document.get("amount")
        )
        for document in documents
    )

    documents_count = len(
        documents
    )

    salutation = (
        f"Hola {contact_name},"
        if contact_name
        else "Hola,"
    )

    subject = (
        "Documentos pendientes de pago"
    )

    body_lines = [
        salutation,
        "",
        (
            f"Te escribo en relación con "
            f"{documents_count} documento"
            f"{'' if documents_count == 1 else 's'} "
            f"pendiente"
            f"{'' if documents_count == 1 else 's'} "
            f"de pago de {customer_name}, "
            f"por un monto total de "
            f"${round(total_amount):,}"
            f"."
        ).replace(",", "."),
        "",
        (
            "Agradeceríamos que pudieran revisar "
            "el estado de estos documentos y "
            "confirmarnos su fecha estimada de pago."
        ),
        "",
        "Muchas gracias.",
        "",
        sender_name,
    ]

    if organization_name:
        body_lines.append(
            str(organization_name)
        )

    return {
        "channel": "email",
        "from": {
            "name": sender.get(
                "displayName"
            ),
            "email": sender.get(
                "email"
            ),
        },
        "to": {
            "name": (
                recipient.get(
                    "contactName"
                )
                or recipient.get(
                    "companyName"
                )
            ),
            "email": recipient.get(
                "email"
            ),
        },
        "subject": subject,
        "body": "\n".join(
            body_lines
        ),
        "documentsCount": (
            documents_count
        ),
        "totalAmount": (
            total_amount
        ),
    }


# ==================================================
# EXECUTE: COBRANZA DE DOCUMENTOS
# ==================================================


def execute_receivable_documents(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> dict[str, Any]:
    """
    Prepara la ejecución de una acción de cobranza.

    IMPORTANTE
    ----------
    Esta primera versión NO envía el correo.

    Realiza:

    1. determina la propuesta comercial;
    2. identifica al cliente prioritario;
    3. resuelve el usuario autenticado;
    4. resuelve el contacto del cliente;
    5. construye un borrador;
    6. retorna prepared o blocked.

    El envío real requerirá aprobación explícita del usuario.
    """
    access_token = _load_luca_access_token()

    proposal_result = (
        propose_receivable_documents(
            business_id=business_id,
            year=year,
            month=month,
            collection=collection,
        )
    )

    # --------------------------------------------------
    # Propuesta / cliente prioritario
    # --------------------------------------------------

    priority_customer = (
        _resolve_priority_customer(
            proposal_result
        )
    )

    if priority_customer is None:
        return {
            "executionType": (
                "receivable_collection_email"
            ),
            "businessId": business_id,
            "status": "blocked",
            "blockReason": (
                "missing_priority_customer"
            ),
            "requiredAction": (
                "review_receivable_proposal"
            ),
            "executed": False,
            "facts": {
                "proposal": proposal_result,
            },
            "execution": None,
            "metadata": {
                "deterministic": True,
            },
        }

    customer_rut = (
        priority_customer.get(
            "customerRut"
        )
    )

    customer_name = (
        priority_customer.get(
            "customerName"
        )
    )

    # --------------------------------------------------
    # Remitente
    # --------------------------------------------------

    sender = resolve_sender_identity(
        access_token=access_token,
    )

    if not sender.get("active"):
        return {
            "executionType": (
                "receivable_collection_email"
            ),
            "businessId": business_id,
            "status": "blocked",
            "blockReason": (
                "inactive_sender"
            ),
            "requiredAction": (
                "validate_sender_account"
            ),
            "executed": False,
            "facts": {
                "proposal": proposal_result,
                "sender": sender,
            },
            "execution": None,
            "metadata": {
                "deterministic": True,
            },
        }

    if sender.get(
        "subscriptionExpired"
    ):
        return {
            "executionType": (
                "receivable_collection_email"
            ),
            "businessId": business_id,
            "status": "blocked",
            "blockReason": (
                "subscription_expired"
            ),
            "requiredAction": (
                "validate_luca_subscription"
            ),
            "executed": False,
            "facts": {
                "proposal": proposal_result,
                "sender": sender,
            },
            "execution": None,
            "metadata": {
                "deterministic": True,
            },
        }

    if not sender.get("email"):
        return {
            "executionType": (
                "receivable_collection_email"
            ),
            "businessId": business_id,
            "status": "blocked",
            "blockReason": (
                "missing_sender_email"
            ),
            "requiredAction": (
                "complete_sender_email"
            ),
            "executed": False,
            "facts": {
                "proposal": proposal_result,
                "sender": sender,
            },
            "execution": None,
            "metadata": {
                "deterministic": True,
            },
        }

    # --------------------------------------------------
    # Empresa / destinatario
    # --------------------------------------------------

    company_id = (
        _resolve_company_id_from_explanation(
            proposal_result=proposal_result,
            customer_rut=customer_rut,
            customer_name=customer_name,
        )
    )

    if company_id is None:
        return {
            "executionType": (
                "receivable_collection_email"
            ),
            "businessId": business_id,
            "status": "blocked",
            "blockReason": (
                "missing_company_id"
            ),
            "requiredAction": (
                "resolve_customer_company"
            ),
            "executed": False,
            "facts": {
                "proposal": proposal_result,
                "sender": sender,
                "priorityCustomer": (
                    priority_customer
                ),
            },
            "execution": None,
            "metadata": {
                "deterministic": True,
            },
        }

    recipient = resolve_company_contact(
        business_id=business_id,
        company_id=company_id,
        access_token=access_token,
    )

    if not recipient.get("email"):
        return {
            "executionType": (
                "receivable_collection_email"
            ),
            "businessId": business_id,
            "status": "blocked",
            "blockReason": (
                "missing_recipient_email"
            ),
            "requiredAction": (
                "complete_company_contact"
            ),
            "executed": False,
            "facts": {
                "proposal": proposal_result,
                "sender": sender,
                "recipient": recipient,
                "priorityCustomer": (
                    priority_customer
                ),
            },
            "execution": None,
            "metadata": {
                "deterministic": True,
            },
        }

    # --------------------------------------------------
    # Documentos a cobrar
    # --------------------------------------------------

    receivable_documents = (
        _resolve_customer_receivables(
            proposal_result=proposal_result,
            customer_rut=customer_rut,
            customer_name=customer_name,
        )
    )

    if not receivable_documents:
        return {
            "executionType": (
                "receivable_collection_email"
            ),
            "businessId": business_id,
            "status": "blocked",
            "blockReason": (
                "missing_receivable_documents"
            ),
            "requiredAction": (
                "review_receivable_documents"
            ),
            "executed": False,
            "facts": {
                "proposal": proposal_result,
                "sender": sender,
                "recipient": recipient,
            },
            "execution": None,
            "metadata": {
                "deterministic": True,
            },
        }

    # --------------------------------------------------
    # Borrador / aprobación requerida
    # --------------------------------------------------

    draft = _build_collection_email_draft(
        sender=sender,
        recipient=recipient,
        documents=receivable_documents,
    )

    return {
        "executionType": (
            "receivable_collection_email"
        ),
        "businessId": business_id,
        "status": "prepared",
        "blockReason": None,
        "requiredAction": (
            "approve_email_send"
        ),
        "executed": False,
        "facts": {
            "proposal": proposal_result,
            "sender": sender,
            "recipient": recipient,
            "priorityCustomer": (
                priority_customer
            ),
            "receivableDocuments": (
                receivable_documents
            ),
        },
        "execution": {
            "action": (
                "send_collection_email"
            ),
            "approvalRequired": True,
            "approved": False,
            "draft": draft,
        },
        "metadata": {
            "deterministic": True,
        },
    }