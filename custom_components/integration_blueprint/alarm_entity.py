from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)  # Added SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from custom_components.integration_blueprint.entity import IntegrationBlueprintEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .data import IntegrationBlueprintConfigEntry


class AlarmEntity(IntegrationBlueprintEntity, SensorEntity):
    """AlarmEntity class representing a single alarm as a sensor."""

    _attr_icon = "mdi:alarm"  # Example icon
    _attr_device_class = (
        SensorDeviceClass.TIMESTAMP
    )  # Set device class for proper display

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntegrationBlueprintConfigEntry,
        alarm_number: int,
        alarm_datetime_utc: datetime,
    ) -> None:
        """Initialize the alarm entity."""
        super().__init__()
        self.hass = hass

        # Ensure the provided datetime is UTC.
        # The calling code (in sensor.py) should already ensure this.
        if alarm_datetime_utc.tzinfo is None or alarm_datetime_utc.tzinfo.utcoffset(
            alarm_datetime_utc
        ) != timezone.utc.utcoffset(None):
            LOGGER.warning(
                "AlarmEntity for number %s received datetime '%s' that was not explicitly UTC. Converting. "
                "The calling code should provide UTC datetime objects.",
                alarm_number,
                str(alarm_datetime_utc),
            )
            self._alarm_at = dt_util.as_utc(alarm_datetime_utc)
        else:
            self._alarm_at = alarm_datetime_utc

        self._alarm_number = alarm_number
        self._entry_id = entry.entry_id

        self._attr_name = f"Alarm {self._alarm_number}"
        self._attr_unique_id = f"{self._entry_id}_alarm_{self._alarm_number}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"Integration Blueprint Alarms ({entry.title})",
            manufacturer="Blueprint Industries",
            model="Managed Alarm",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def alarm_number(self) -> int:
        """Return the alarm number for this entity."""
        return self._alarm_number

    @property
    def native_value(self) -> datetime:
        """Return the state of the sensor (the alarm time in ISO format)."""
        return self._alarm_at  # This is already UTC
