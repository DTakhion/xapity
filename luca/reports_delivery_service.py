# luca/reports_delivery_service.py

"""
Servicio determinista de entrega de reportes.

Responsabilidades actuales:

- recibir una acción previamente confirmada;
- validar que corresponde a un envío soportado;
- recuperar desde Mongo el reporte referenciado;
- comprobar que sigue siendo exactamente el snapshot
  confirmado por el usuario.

Este módulo todavía NO:

- genera archivos XLSX;
- envía correos;
- modifica el estado de la acción.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from db.mongo_persistence_luca import (
    find_luca_report,
)


GENERAL_BALANCE_EMAIL_EXECUTION_TYPE = (
    "general_balance_email"
)


@dataclass(
    frozen=True,
    slots=True,
)
class ConfirmedReportSnapshot:
    """
    Snapshot de reporte validado contra la acción
    previamente confirmada.
    """

    business_id: int
    report_type: str
    query_from: str
    query_to: str
    mongo_id: str
    version: int
    content_hash: str
    report: dict[str, Any]
    summary: dict[str, Any]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "businessId": self.business_id,
            "reportType": self.report_type,
            "queryFrom": self.query_from,
            "queryTo": self.query_to,
            "mongoId": self.mongo_id,
            "version": self.version,
            "contentHash": self.content_hash,
            "report": self.report,
            "summary": self.summary,
        }


def _require_dict(
    *,
    value: Any,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise TypeError(
            f"{field_name} debe ser un diccionario."
        )

    return value


def _require_string(
    *,
    value: Any,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} debe ser un string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} no puede estar vacío."
        )

    return normalized


def _require_positive_int(
    *,
    value: Any,
    field_name: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
    ):
        raise TypeError(
            f"{field_name} debe ser un entero."
        )

    if value <= 0:
        raise ValueError(
            f"{field_name} debe ser mayor que cero."
        )

    return value


def resolve_confirmed_report_snapshot(
    *,
    confirmed_action: dict[str, Any],
) -> ConfirmedReportSnapshot:
    """
    Recupera y valida el reporte exacto asociado
    a una acción previamente confirmada.

    No acepta una acción pendiente ni cancelada.

    La ejecución solamente puede continuar si:

        mongoId
        version
        contentHash

    siguen coincidiendo con la referencia que
    fue confirmada por el usuario.
    """

    action = _require_dict(
        value=confirmed_action,
        field_name="confirmed_action",
    )

    status = _require_string(
        value=action.get(
            "status"
        ),
        field_name="status",
    )

    if status != "confirmed":
        raise ValueError(
            "La acción debe encontrarse en estado "
            "'confirmed' antes de resolver el reporte."
        )

    action_type = _require_string(
        value=action.get(
            "actionType"
        ),
        field_name="actionType",
    )

    if (
        action_type
        != GENERAL_BALANCE_EMAIL_EXECUTION_TYPE
    ):
        raise NotImplementedError(
            "El tipo de acción confirmada todavía "
            "no está soportado por el servicio "
            "de entrega de reportes."
        )

    business_id = (
        _require_positive_int(
            value=action.get(
                "businessId"
            ),
            field_name="businessId",
        )
    )

    payload = _require_dict(
        value=action.get(
            "payload"
        ),
        field_name="payload",
    )

    snapshot_reference = (
        _require_dict(
            value=payload.get(
                "snapshot"
            ),
            field_name="payload.snapshot",
        )
    )

    report_type = _require_string(
        value=snapshot_reference.get(
            "reportType"
        ),
        field_name=(
            "payload.snapshot.reportType"
        ),
    )

    query_from = _require_string(
        value=snapshot_reference.get(
            "queryFrom"
        ),
        field_name=(
            "payload.snapshot.queryFrom"
        ),
    )

    query_to = _require_string(
        value=snapshot_reference.get(
            "queryTo"
        ),
        field_name=(
            "payload.snapshot.queryTo"
        ),
    )

    expected_mongo_id = (
        _require_string(
            value=snapshot_reference.get(
                "mongoId"
            ),
            field_name=(
                "payload.snapshot.mongoId"
            ),
        )
    )

    expected_version = (
        _require_positive_int(
            value=snapshot_reference.get(
                "version"
            ),
            field_name=(
                "payload.snapshot.version"
            ),
        )
    )

    expected_content_hash = (
        _require_string(
            value=snapshot_reference.get(
                "contentHash"
            ),
            field_name=(
                "payload.snapshot.contentHash"
            ),
        )
    )

    report_document = (
        find_luca_report(
            business_id=business_id,
            report_type=report_type,
            query_from=query_from,
            query_to=query_to,
        )
    )

    if report_document is None:
        raise LookupError(
            "El reporte confirmado ya no está "
            "disponible en MongoDB."
        )

    actual_mongo_id = str(
        report_document.get(
            "_id"
        )
    )

    actual_version = (
        report_document.get(
            "version"
        )
    )

    actual_content_hash = (
        report_document.get(
            "contentHash"
        )
    )

    if (
        actual_mongo_id
        != expected_mongo_id
    ):
        raise RuntimeError(
            "El reporte almacenado ya no corresponde "
            "al documento que fue confirmado."
        )

    if (
        actual_version
        != expected_version
    ):
        raise RuntimeError(
            "La versión del reporte cambió después "
            "de la confirmación preparada."
        )

    if (
        actual_content_hash
        != expected_content_hash
    ):
        raise RuntimeError(
            "El contenido del reporte cambió después "
            "de la confirmación preparada."
        )

    report = _require_dict(
        value=report_document.get(
            "report"
        ),
        field_name="report",
    )

    summary = (
        report_document.get(
            "summary"
        )
        or {}
    )

    if not isinstance(
        summary,
        dict,
    ):
        raise TypeError(
            "summary debe ser un diccionario."
        )

    return ConfirmedReportSnapshot(
        business_id=business_id,
        report_type=report_type,
        query_from=query_from,
        query_to=query_to,
        mongo_id=actual_mongo_id,
        version=actual_version,
        content_hash=actual_content_hash,
        report=dict(
            report
        ),
        summary=dict(
            summary
        ),
    )