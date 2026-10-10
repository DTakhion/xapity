
# luca/sales_reconciliation_proposal_service.py

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


from luca.sales_reconciliation_service import (
    get_unreconciled_documents_for_proposal,
)


# ---------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------

PROPOSE_PATH = "/conciliacion/xapity/propose"

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_WINDOW_DAYS_BEFORE = 0
DEFAULT_WINDOW_DAYS_AFTER = 45
DEFAULT_MIN_RECURRENT_MATCHES = 2


# ---------------------------------------------------------------------
# Errores del servicio
# ---------------------------------------------------------------------

class ReconciliationProposalError(RuntimeError):
    """Error al solicitar propuestas al backend de Luca."""


class ReconciliationProposalConfigurationError(
    ReconciliationProposalError
):
    """Configuración incompleta del cliente HTTP."""


# ---------------------------------------------------------------------
# Normalización y validación de entrada
# ---------------------------------------------------------------------

def _is_empty_linkage(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 0


def _is_unreconciled(document: Dict[str, Any]) -> bool:
    """
    Un documento está completamente NO CONCILIADO cuando
    ambos arreglos existen y están vacíos.

    Si falta información, no asumimos que está sin conciliar.
    """
    return (
        _is_empty_linkage(document.get("linkage"))
        and _is_empty_linkage(document.get("linkageCredito"))
    )


def _prepare_documents(
    documents: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Prepara los documentos para el endpoint de Luca.

    No inventa identificadores, fechas ni montos.
    No modifica los documentos originales.
    """
    prepared = []
    seen = set()

    for document in documents:
        if not isinstance(document, dict):
            continue

        if not _is_unreconciled(document):
            continue

        document_id = (
            document.get("idPrincipal")
            or document.get("id")
        )

        folio = (
            document.get("folio")
            or document.get("numeroFolio")
        )

        fecha = document.get("fecha")
        rut = document.get("rut")
        monto = document.get("montoTotal")

        if (
            document_id is None
            or not folio
            or not fecha
            or not rut
            or monto is None
        ):
            continue

        # Evita enviar dos veces el mismo documento.
        key = (str(document_id), str(folio))

        if key in seen:
            continue

        seen.add(key)

        prepared.append({
            "idPrincipal": document_id,
            "folio": str(folio),
            "fecha": fecha,
            "fechaVencimiento": document.get(
                "fechaVencimiento"
            ),
            "rut": str(rut),
            "razonSocial": document.get(
                "razonSocial"
            ),
            "montoTotal": monto,
            "code": document.get("code"),
            "nombreFolio": document.get(
                "nombreFolio"
            ),
            "linkage": [],
            "linkageCredito": [],
        })

    return prepared


# ---------------------------------------------------------------------
# Cliente HTTP
# ---------------------------------------------------------------------

def _resolve_configuration(
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> tuple[str, str]:
    """
    Configuración independiente del backend de Xapity.

    Variables de entorno:
      LUCA_RECONCILIATION_API_URL
      LUCA_RECONCILIATION_API_KEY
    """

    resolved_url = (
        base_url
        or os.getenv("LUCA_RECONCILIATION_API_URL")
        or ""
    ).strip().rstrip("/")

    resolved_key = (
        api_key
        if api_key is not None
        else os.getenv("LUCA_RECONCILIATION_API_KEY", "")
    ).strip()

    if not resolved_url:
        raise ReconciliationProposalConfigurationError(
            "Falta LUCA_RECONCILIATION_API_URL."
        )

    if not (
        resolved_url.startswith("https://")
        or resolved_url.startswith("http://localhost:")
        or resolved_url.startswith("http://127.0.0.1:")
    ):
        raise ReconciliationProposalConfigurationError(
            "La URL de Luca debe utilizar HTTPS, "
            "excepto localhost para desarrollo."
        )

    if not resolved_key:
        raise ReconciliationProposalConfigurationError(
            "Falta LUCA_RECONCILIATION_API_KEY."
        )

    return resolved_url, resolved_key


def _post_proposal(
    *,
    payload: Dict[str, Any],
    base_url: str,
    api_key: str,
    timeout_seconds: int,
) -> Dict[str, Any]:

    url = f"{base_url}{PROPOSE_PATH}"

    body = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    request = Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            raw_response = response.read().decode(
                "utf-8"
            )

    except HTTPError as exc:
        # No exponer headers, credenciales ni detalles
        # internos del backend en la respuesta al agente.
        raise ReconciliationProposalError(
            f"Luca respondió HTTP {exc.code} "
            "al solicitar propuestas."
        ) from exc

    except (URLError, TimeoutError, OSError) as exc:
        raise ReconciliationProposalError(
            "No fue posible conectar con el "
            "servicio de conciliación de Luca."
        ) from exc

    try:
        result = json.loads(raw_response)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ReconciliationProposalError(
            "Luca devolvió una respuesta JSON inválida."
        ) from exc

    if not isinstance(result, dict):
        raise ReconciliationProposalError(
            "La respuesta de Luca no tiene "
            "el formato esperado."
        )

    if result.get("ok") is not True:
        raise ReconciliationProposalError(
            "Luca no pudo generar las propuestas."
        )

    if not isinstance(
        result.get("result", {}).get("proposals"),
        list,
    ):
        raise ReconciliationProposalError(
            "La respuesta de Luca no contiene "
            "una lista válida de propuestas."
        )

    return result


# ---------------------------------------------------------------------
# API pública para Xapity
# ---------------------------------------------------------------------

def get_reconciliation_proposals(
    *,
    business_id: int,
    documents: Iterable[Dict[str, Any]],
    account_ids_sql: Optional[List[int]] = None,
    window_days_before: int = DEFAULT_WINDOW_DAYS_BEFORE,
    window_days_after: int = DEFAULT_WINDOW_DAYS_AFTER,
    min_recurrent_matches: int = DEFAULT_MIN_RECURRENT_MATCHES,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Solicita propuestas de conciliación al backend de Luca.

    Responsabilidades:
      1. Recibir documentos desde Xapity.
      2. Conservar solo documentos completamente no conciliados.
      3. Invocar el endpoint PROPOSE de Luca.
      4. Entregar las propuestas y su evidencia.

    No consulta movimientos bancarios directamente.
    No persiste resultados.
    No ejecuta conciliaciones.
    """

    try:
        business_id = int(business_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "business_id debe ser un entero."
        ) from exc

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    if min_recurrent_matches < 2:
        raise ValueError(
            "min_recurrent_matches debe ser >= 2."
        )

    if window_days_before < 0 or window_days_after < 0:
        raise ValueError(
            "Las ventanas temporales no pueden ser negativas."
        )

    prepared_documents = _prepare_documents(
        documents
    )

    # Sin documentos elegibles no es necesario
    # realizar una petición HTTP.
    if not prepared_documents:
        return {
            "ok": True,
            "businessId": business_id,
            "engine": "xapity_propose_v1",
            "operation": "propose",
            "status": "no_eligible_documents",
            "input": {
                "documentsCount": 0,
            },
            "result": {
                "proposalsCount": 0,
                "ambiguousProposalsCount": 0,
                "proposals": [],
            },
            "metadata": {
                "readOnly": True,
                "automaticReconciliation": False,
                "requiresHumanConfirmation": True,
            },
        }

    resolved_url, resolved_key = _resolve_configuration(
        base_url=base_url,
        api_key=api_key,
    )

    payload = {
        "businessId": business_id,
        "documents": prepared_documents,
        "accountIdsSql": account_ids_sql,
        "windowDaysBefore": window_days_before,
        "windowDaysAfter": window_days_after,
        "minRecurrentMatches": min_recurrent_matches,
    }

    result = _post_proposal(
        payload=payload,
        base_url=resolved_url,
        api_key=resolved_key,
        timeout_seconds=timeout_seconds,
    )

    if result.get("businessId") != business_id:
        raise ReconciliationProposalError(
            "El businessId de la respuesta de Luca "
            "no coincide con el solicitado."
        )

    return {
        **result,
        "operation": "propose",
        "status": "proposals_generated",
    }


# ---------------------------------------------------------------------
# Orquestación: Mongo Xapity → PROPOSE Luca
# ---------------------------------------------------------------------

def propose_customer_reconciliation(
    *,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    customer_rut: str | None = None,
    customer_name: str | None = None,
    collection: Any = None,
    account_ids_sql: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Recupera los documentos no conciliados desde Xapity
    y solicita las propuestas al backend de Luca.

    No persiste ni ejecuta conciliaciones.
    """

    documents = get_unreconciled_documents_for_proposal(
        business_id=business_id,
        year=year,
        month=month,
        customer_rut=customer_rut,
        customer_name=customer_name,
        collection=collection,
    )

    return get_reconciliation_proposals(
        business_id=business_id,
        documents=documents,
        account_ids_sql=account_ids_sql,
    )
