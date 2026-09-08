# luca/reports_execute_service.py

"""
Servicio determinista de ejecución para reportes de Luca.

Este módulo contiene exclusivamente lógica asociada a acciones
ejecutables sobre reportes.

Responsabilidades actuales:

- preparar el envío por correo de un Balance General;
- resolver el snapshot exacto que será utilizado;
- validar el formato solicitado;
- construir una acción pendiente de confirmación;
- conservar trazabilidad suficiente del snapshot elegido.

No contiene:

- clasificación de intenciones;
- routing entre agentes;
- generación de respuestas naturales;
- consultas directas a Luca API;
- resolución del usuario autenticado;
- envío real de correos;
- persistencia de confirmaciones.

El envío real será incorporado posteriormente, una vez resueltos:

1. correo del usuario autenticado;
2. generación del archivo;
3. mecanismo de confirmación;
4. servicio de correo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


from luca.reports_query_service import (
    ReportsQueryResult,
    query_general_balance,
)
from luca.luca_user_service import (
    get_luca_current_user,
)


# ==================================================
# CONSTANTES
# ==================================================


GENERAL_BALANCE_EMAIL_EXECUTION_TYPE = (
    "general_balance_email"
)

DEFAULT_REPORT_EMAIL_SENDER = (
    "no-reply@xapity.app"
)

DEFAULT_GENERAL_BALANCE_FORMAT = (
    "xlsx"
)

SUPPORTED_GENERAL_BALANCE_EMAIL_FORMATS = {
    "xlsx",
}


# ==================================================
# TIPOS
# ==================================================


@dataclass(
    frozen=True,
    slots=True,
)
class ReportsExecuteResult:
    """
    Resultado estructurado de una acción asociada
    a un reporte.

    En esta primera versión representa una ejecución
    preparada que aún requiere confirmación explícita
    antes de realizar una acción externa.
    """

    execution_type: str
    business_id: int
    status: str
    data: dict[str, Any]
    source: str
    trace: dict[str, Any]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convierte el resultado a un diccionario
        serializable.
        """

        return {
            "executionType": (
                self.execution_type
            ),
            "businessId": (
                self.business_id
            ),
            "status": (
                self.status
            ),
            "data": dict(
                self.data
            ),
            "source": (
                self.source
            ),
            "trace": dict(
                self.trace
            ),
        }


# ==================================================
# VALIDACIONES
# ==================================================


def _validate_business_id(
    business_id: int,
) -> None:
    if isinstance(
        business_id,
        bool,
    ) or not isinstance(
        business_id,
        int,
    ):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )


def _validate_optional_date(
    *,
    value: str | None,
    field_name: str,
) -> None:
    if (
        value is not None
        and not isinstance(
            value,
            str,
        )
    ):
        raise TypeError(
            f"{field_name} debe ser string o None."
        )


def _validate_query_dates(
    *,
    query_from: str | None,
    query_to: str | None,
) -> None:
    _validate_optional_date(
        value=query_from,
        field_name="query_from",
    )

    _validate_optional_date(
        value=query_to,
        field_name="query_to",
    )

    if (
        query_from is None
        and query_to is not None
    ):
        raise ValueError(
            "query_from y query_to deben "
            "informarse juntos."
        )

    if (
        query_from is not None
        and query_to is None
    ):
        raise ValueError(
            "query_from y query_to deben "
            "informarse juntos."
        )


def _validate_email(
    *,
    email: str,
    field_name: str,
) -> str:
    """
    Validación mínima defensiva.

    La identidad real del destinatario será resuelta
    posteriormente desde Luca y no desde texto libre
    entregado por el usuario.
    """

    if not isinstance(
        email,
        str,
    ):
        raise TypeError(
            f"{field_name} debe ser string."
        )

    normalized = email.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} no puede estar vacío."
        )

    if (
        "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
        raise ValueError(
            f"{field_name} no contiene un "
            "correo válido."
        )

    return normalized


def _normalize_format(
    report_format: str | None,
) -> str:
    """
    Normaliza y valida el formato solicitado.

    Por ahora solamente XLSX está implementado
    para esta capacidad.
    """

    if report_format is None:
        return (
            DEFAULT_GENERAL_BALANCE_FORMAT
        )

    if not isinstance(
        report_format,
        str,
    ):
        raise TypeError(
            "report_format debe ser string o None."
        )

    normalized = (
        report_format
        .strip()
        .lower()
    )

    if normalized == "excel":
        normalized = "xlsx"

    if normalized not in (
        SUPPORTED_GENERAL_BALANCE_EMAIL_FORMATS
    ):
        raise NotImplementedError(
            "El formato solicitado todavía no está "
            "implementado para el envío del "
            "Balance General. "
            "Actualmente se admite XLSX."
        )

    return normalized


# ==================================================
# HELPERS
# ==================================================


def _build_snapshot_reference(
    query_result: ReportsQueryResult,
) -> dict[str, Any]:
    """
    Construye una referencia auditable al snapshot
    exacto seleccionado para la futura ejecución.

    Esto permite que una confirmación posterior pueda
    referirse al mismo reporte y no a otro snapshot
    sincronizado posteriormente.
    """

    return {
        "reportType": (
            query_result.report_type
        ),
        "queryFrom": (
            query_result.query_from
        ),
        "queryTo": (
            query_result.query_to
        ),
        "mongoId": (
            query_result.trace.get(
                "mongoId"
            )
        ),
        "version": (
            query_result.trace.get(
                "version"
            )
        ),
        "contentHash": (
            query_result.trace.get(
                "contentHash"
            )
        ),
        "loadedAt": (
            query_result.trace.get(
                "loadedAt"
            )
        ),
    }


# ==================================================
# GENERAL BALANCE — EMAIL
# ==================================================


def prepare_general_balance_email(
    *,
    business_id: int,
    query_from: str | None = None,
    query_to: str | None = None,
    report_format: str | None = None,
    sender_email: str = (
        DEFAULT_REPORT_EMAIL_SENDER
    ),
) -> ReportsExecuteResult:
    """
    Prepara el envío por correo de un Balance General.

    IMPORTANTE:
    esta función NO envía el correo.

    Su responsabilidad es resolver exactamente qué
    snapshot se enviaría y construir una acción
    pendiente de confirmación.

    Parameters
    ----------
    business_id:
        Empresa propietaria del reporte.

    recipient_email:
        Correo obtenido desde la identidad autenticada
        del usuario.

        No debe provenir de una dirección arbitraria
        indicada por lenguaje natural.

    query_from:
        Fecha inicial explícita del reporte.

        Si no se informa junto con query_to,
        se utilizará el snapshot más reciente
        disponible en MongoDB.

    query_to:
        Fecha final explícita del reporte.

    report_format:
        Formato del archivo.

        Actualmente:
            xlsx

        Si no se informa se utiliza xlsx.

    sender_email:
        Remitente que posteriormente será utilizado
        para el envío.

        Por defecto:
            no-reply@xapity.app
    """

    _validate_business_id(
        business_id
    )

    _validate_query_dates(
        query_from=query_from,
        query_to=query_to,
    )

    current_user = (
        get_luca_current_user()
    )

    resolved_recipient_email = (
        _validate_email(
            email=current_user.email,
            field_name=(
                "recipient_email"
            ),
        )
    )

    resolved_sender_email = (
        _validate_email(
            email=sender_email,
            field_name=(
                "sender_email"
            ),
        )
    )

    resolved_format = (
        _normalize_format(
            report_format
        )
    )

    # --------------------------------------------------
    # Resolver el reporte desde la fuente controlada
    # --------------------------------------------------
    #
    # No se consulta Luca API.
    #
    # Se reutiliza exactamente la misma fuente de verdad
    # utilizada por GENERAL_BALANCE + QUERY:
    #
    #     MongoDB
    #
    # Si no se entrega un período explícito,
    # query_general_balance seleccionará el snapshot
    # más reciente disponible.
    # --------------------------------------------------

    query_result = (
        query_general_balance(
            business_id=business_id,
            query_from=query_from,
            query_to=query_to,
            top_limit=10,
        )
    )

    snapshot_reference = (
        _build_snapshot_reference(
            query_result
        )
    )

    return ReportsExecuteResult(
        execution_type=(
            GENERAL_BALANCE_EMAIL_EXECUTION_TYPE
        ),
        business_id=business_id,
        status="pending_confirmation",
        data={
            "deliveryChannel": "email",
            "format": (
                resolved_format
            ),
            "recipientEmail": (
                resolved_recipient_email
            ),
            "recipientUser": {
                "userId": (
                    current_user.user_id
                ),
                "fullName": (
                    current_user.full_name
                ),
                "organizationId": (
                    current_user.organization_id
                ),
                "organizationName": (
                    current_user.organization_name
                ),
            },
            "senderEmail": (
                resolved_sender_email
            ),
            "requiresConfirmation": True,
            "snapshot": (
                snapshot_reference
            ),
        },
        source="mongodb",
        trace={
            "executionType": (
                GENERAL_BALANCE_EMAIL_EXECUTION_TYPE
            ),
            "recipientUserId": (
                current_user.user_id
            ),
            "reportType": (
                query_result.report_type
            ),
            "queryFrom": (
                query_result.query_from
            ),
            "queryTo": (
                query_result.query_to
            ),
            "mongoId": (
                query_result.trace.get(
                    "mongoId"
                )
            ),
            "version": (
                query_result.trace.get(
                    "version"
                )
            ),
            "contentHash": (
                query_result.trace.get(
                    "contentHash"
                )
            ),
            "loadedAt": (
                query_result.trace.get(
                    "loadedAt"
                )
            ),
            "deliveryChannel": "email",
            "format": (
                resolved_format
            ),
            "requiresConfirmation": True,
            "executed": False,
            "deterministic": True,
        },
    )