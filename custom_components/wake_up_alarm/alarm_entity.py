"""Alarm entity for wake_up_alarm integration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.util import dt as dt_util

from custom_components.wake_up_alarm.entity import WakeUpAlarmEntity

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import WakeUpAlarmConfigEntry


class AlarmEntity(WakeUpAlarmEntity, SensorEntity):
    """AlarmEntity class representing a single alarm as a sensor."""

    _attr_icon = "mdi:alarm"  # Example icon

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WakeUpAlarmConfigEntry,
        alarm_number: int,
        alarm_datetime_utc: datetime,
        alarm_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the alarm entity."""
        super().__init__()
        self.hass = hass

        # Ensure the provided datetime is UTC.
        # The calling code (in sensor.py) should already ensure this.
        if alarm_datetime_utc.tzinfo is None or alarm_datetime_utc.tzinfo.utcoffset(
            alarm_datetime_utc
        ) != UTC.utcoffset(None):
            LOGGER.warning(
                "AlarmEntity for number %s received datetime '%s' that was not  UTC."
                "The calling code should provide UTC datetime objects, converting.",
                alarm_number,
                str(alarm_datetime_utc),
            )
            self._alarm_at = dt_util.as_utc(alarm_datetime_utc)
        else:
            self._alarm_at = alarm_datetime_utc

        self._alarm_number = alarm_number
        self._alarm_data = alarm_data
        self._entry_id = entry.entry_id

        self._attr_name = (
            self._alarm_data["name"] if self._alarm_data else f"Alarm {alarm_number}"
        )
        self._attr_unique_id = f"{self._entry_id}_alarm_{self._alarm_number}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"WakeUp Alarm ({entry.title})",
            manufacturer="Ephemeral",
            model="Managed Alarm",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def alarm_number(self) -> int:
        """Return the alarm number for this entity."""
        return self._alarm_number

    @property
    def native_value(self) -> datetime | str | None:
        """Return the state of the sensor (the alarm time in ISO format)."""
        if self._alarm_data:
            if not self._alarm_data["enabled"]:
                return "disabled"
            return self._alarm_data["next_run"]
        return self._alarm_at  # This is already UTC

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return alarm details as entity attributes."""
        if not self._alarm_data:
            return {
                "alarm_number": self._alarm_number,
                "datetime": self._alarm_at.isoformat(),
                "next_run": self._alarm_at.isoformat(),
            }

        datetime_obj = self._alarm_data.get("datetime_obj")
        next_run = self._alarm_data.get("next_run")
        created_at = self._alarm_data.get("created_at")

        return {
            "alarm_number": self._alarm_number,
            "name": self._alarm_data["name"],
            "type": self._alarm_data["type"],
            "enabled": self._alarm_data["enabled"],
            "datetime": datetime_obj.isoformat() if datetime_obj else None,
            "time": self._alarm_data.get("time"),
            "weekdays": list(self._alarm_data.get("weekdays") or []),
            "next_run": next_run.isoformat() if next_run else None,
            "created_at": created_at.isoformat() if created_at else None,
            "skip_next": self._alarm_data.get("skip_next", False),
        }
