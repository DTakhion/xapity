# services/availability_service.py

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from db.mongo_persistence import (
    get_service_by_service_id,
    get_staff,
    get_appointments,
)


WEEKDAY_MAP = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}


def _parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _combine_day_and_time(day: date, value: str) -> datetime:
    return datetime.combine(day, _parse_hhmm(value))


def _format_hhmm(value: datetime) -> str:
    return value.strftime("%H:%M")


def _normalize_date(value: Any) -> date:
    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, str):
        return date.fromisoformat(value[:10])

    raise ValueError("Invalid date value.")


def _dates_between(start_date: date, end_date: date) -> List[date]:
    days: List[date] = []
    current = start_date

    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)

    return days


def _appointment_overlaps(
    *,
    slot_start: datetime,
    slot_end: datetime,
    appointment: Dict[str, Any],
) -> bool:
    appointment_date = _normalize_date(appointment["date"])

    appointment_start = _combine_day_and_time(
        appointment_date,
        appointment["start"],
    )
    appointment_end = _combine_day_and_time(
        appointment_date,
        appointment["end"],
    )

    return slot_start < appointment_end and slot_end > appointment_start


def _get_working_day(
    *,
    staff_member: Dict[str, Any],
    target_day: date,
) -> Optional[Dict[str, Any]]:
    working_hours = staff_member.get("workingHours")

    if not working_hours:
        return None

    weekday_key = WEEKDAY_MAP[target_day.weekday()]
    working_day = working_hours.get(weekday_key)

    if not working_day:
        return None

    if not working_day.get("isWorking", True):
        return None

    return working_day


async def get_availability_slots(
    *,
    service_id: str,
    target_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    staff_id: Optional[str] = None,
    business_id: str = "1",
) -> Dict[str, Any]:
    """
    Calculates available slots for a service.

    This service does not persist data.
    It only reads:
    - service
    - staff
    - existing appointments

    Then returns available slots.
    """

    service = get_service_by_service_id(service_id)

    if not service:
        raise ValueError("Service not found.")

    if not service.get("isActive", True):
        raise ValueError("Service is not active.")

    if service.get("isDeleted", False):
        raise ValueError("Service is deleted.")

    if not service.get("isBookableOnline", True):
        raise ValueError("Service is not bookable online.")

    duration_minutes = int(service.get("durationMinutes", 60))

    if target_date:
        query_start_date = target_date
        query_end_date = target_date
    else:
        if not start_date or not end_date:
            raise ValueError("You must provide target_date or start_date/end_date.")

        query_start_date = start_date
        query_end_date = end_date

    staff_members = get_staff(
        include_deleted=False,
        only_active=True,
    )

    eligible_staff = []

    for staff_member in staff_members:
        if staff_member.get("businessId") != business_id:
            continue

        if staff_id and staff_member.get("staffId") != staff_id:
            continue

        service_ids = staff_member.get("serviceIds", [])

        if service_id not in service_ids:
            continue

        eligible_staff.append(staff_member)

    appointments = get_appointments(
        include_deleted=False,
        business_id=business_id,
        service_id=service_id,
    )

    active_appointments = [
        appointment
        for appointment in appointments
        if appointment.get("status", "scheduled") not in ["cancelled"]
    ]

    available_slots: List[Dict[str, Any]] = []

    for current_date in _dates_between(query_start_date, query_end_date):
        for staff_member in eligible_staff:
            working_day = _get_working_day(
                staff_member=staff_member,
                target_day=current_date,
            )

            if not working_day:
                continue

            blocks = working_day.get("blocks", [])

            staff_appointments = [
                appointment
                for appointment in active_appointments
                if appointment.get("staffId") == staff_member.get("staffId")
                and _normalize_date(appointment.get("date")) == current_date
            ]

            for block in blocks:
                block_start = _combine_day_and_time(current_date, block["start"])
                block_end = _combine_day_and_time(current_date, block["end"])

                slot_start = block_start

                while slot_start + timedelta(minutes=duration_minutes) <= block_end:
                    slot_end = slot_start + timedelta(minutes=duration_minutes)

                    has_conflict = any(
                        _appointment_overlaps(
                            slot_start=slot_start,
                            slot_end=slot_end,
                            appointment=appointment,
                        )
                        for appointment in staff_appointments
                    )

                    if not has_conflict:
                        available_slots.append(
                            {
                                "serviceId": service["serviceId"],
                                "serviceName": service["name"],
                                "durationMinutes": duration_minutes,
                                "staffId": staff_member["staffId"],
                                "staffName": staff_member["name"],
                                "date": current_date,
                                "start": _format_hhmm(slot_start),
                                "end": _format_hhmm(slot_end),
                            }
                        )

                    slot_start = slot_end

    return {
        "serviceId": service["serviceId"],
        "serviceName": service["name"],
        "durationMinutes": duration_minutes,
        "staffId": staff_id,
        "staffName": None,
        "targetDate": target_date,
        "startDate": query_start_date,
        "endDate": query_end_date,
        "availableSlots": available_slots,
        "total": len(available_slots),
    }