"""Pure alarm model helpers for wake_up_alarm."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any

ALARM_TYPE_ONE_TIME = "one_time"
ALARM_TYPE_RECURRING = "recurring"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_TO_INDEX = {weekday: index for index, weekday in enumerate(WEEKDAYS)}


@dataclass
class RecurringAlarmData:
    """Store data used when creating a recurring alarm."""

    alarm_number: int
    time_value: str
    weekdays: list[str]
    name: str | None = None
    enabled: bool = True
    created_at: datetime | None = None
    now: datetime | None = None


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO datetime value into UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _serialize_datetime(value: datetime | None) -> str | None:
    """Serialize a datetime value as an ISO string."""
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> time:
    """Parse a HH:MM[:SS] time string."""
    return time.fromisoformat(value)


def _normalize_weekdays(weekdays: list[str]) -> list[str]:
    """Validate and normalize weekday values."""
    normalized = []
    for weekday in weekdays:
        normalized_weekday = weekday.lower()
        if normalized_weekday not in WEEKDAY_TO_INDEX:
            msg = f"Unsupported weekday: {weekday}"
            raise ValueError(msg)
        if normalized_weekday not in normalized:
            normalized.append(normalized_weekday)
    if not normalized:
        msg = "At least one weekday is required"
        raise ValueError(msg)
    return normalized


def normalize_alarm(raw_alarm: dict[str, Any]) -> dict[str, Any]:
    """Normalize persisted alarm data into the internal alarm shape."""
    alarm_number = raw_alarm["number"]
    alarm_type = raw_alarm.get("type", ALARM_TYPE_ONE_TIME)
    datetime_obj = _parse_datetime(raw_alarm.get("datetime"))
    next_run = _parse_datetime(raw_alarm.get("next_run")) or datetime_obj
    created_at = _parse_datetime(raw_alarm.get("created_at"))

    return {
        "number": alarm_number,
        "name": raw_alarm.get("name") or f"Alarm {alarm_number}",
        "type": alarm_type,
        "enabled": raw_alarm.get("enabled", True),
        "datetime_obj": datetime_obj,
        "time": raw_alarm.get("time"),
        "weekdays": list(raw_alarm.get("weekdays") or []),
        "next_run": next_run,
        "created_at": created_at,
        "skip_next": raw_alarm.get("skip_next", False),
    }


def create_one_time_alarm(
    alarm_number: int,
    alarm_datetime: datetime,
    *,
    name: str | None = None,
    enabled: bool = True,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create normalized one-time alarm data."""
    alarm_datetime_utc = alarm_datetime.astimezone(UTC)
    created_at_utc = created_at.astimezone(UTC) if created_at else None

    return {
        "number": alarm_number,
        "name": name or f"Alarm {alarm_number}",
        "type": ALARM_TYPE_ONE_TIME,
        "enabled": enabled,
        "datetime_obj": alarm_datetime_utc,
        "time": None,
        "weekdays": [],
        "next_run": alarm_datetime_utc,
        "created_at": created_at_utc,
        "skip_next": False,
    }


def calculate_next_recurring_run(
    time_value: str,
    weekdays: list[str],
    *,
    now: datetime,
    skip_current: bool = False,
) -> datetime:
    """Calculate the next recurring run using the timezone from ``now``."""
    alarm_time = _parse_time(time_value)
    selected_weekdays = set(_normalize_weekdays(weekdays))

    skipped_first_match = False
    for days_ahead in range(8):
        candidate_date = now.date() + timedelta(days=days_ahead)
        candidate_weekday = WEEKDAYS[candidate_date.weekday()]
        if candidate_weekday not in selected_weekdays:
            continue

        candidate = datetime.combine(candidate_date, alarm_time, tzinfo=now.tzinfo)
        if candidate <= now:
            continue

        if skip_current and not skipped_first_match:
            skipped_first_match = True
            continue

        return candidate

    msg = "Could not calculate next recurring run"
    raise ValueError(msg)


def create_recurring_alarm(recurring_alarm_data: RecurringAlarmData) -> dict[str, Any]:
    """Create normalized recurring alarm data."""
    normalized_weekdays = _normalize_weekdays(recurring_alarm_data.weekdays)
    created_at_utc = (
        recurring_alarm_data.created_at.astimezone(UTC)
        if recurring_alarm_data.created_at
        else None
    )
    next_run = (
        calculate_next_recurring_run(
            recurring_alarm_data.time_value,
            normalized_weekdays,
            now=recurring_alarm_data.now or datetime.now(UTC),
        )
        if recurring_alarm_data.enabled
        else None
    )

    return {
        "number": recurring_alarm_data.alarm_number,
        "name": recurring_alarm_data.name
        or f"Alarm {recurring_alarm_data.alarm_number}",
        "type": ALARM_TYPE_RECURRING,
        "enabled": recurring_alarm_data.enabled,
        "datetime_obj": None,
        "time": recurring_alarm_data.time_value,
        "weekdays": normalized_weekdays,
        "next_run": next_run,
        "created_at": created_at_utc,
        "skip_next": False,
    }


def serialize_alarm(alarm: dict[str, Any]) -> dict[str, Any]:
    """Serialize normalized alarm data for Home Assistant storage."""
    return {
        "number": alarm["number"],
        "name": alarm["name"],
        "type": alarm["type"],
        "enabled": alarm["enabled"],
        "datetime": _serialize_datetime(alarm.get("datetime_obj")),
        "time": alarm.get("time"),
        "weekdays": list(alarm.get("weekdays") or []),
        "next_run": _serialize_datetime(alarm.get("next_run")),
        "created_at": _serialize_datetime(alarm.get("created_at")),
        "skip_next": alarm.get("skip_next", False),
    }
