from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType

from .const import DOMAIN
from custom_components.integration_blueprint.entity import IntegrationBlueprintEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .data import IntegrationBlueprintConfigEntry


class AlarmEntity(IntegrationBlueprintEntity, SensorEntity):
    """AlarmEntity class representing a single alarm as a sensor."""

    _attr_icon = "mdi:alarm"  # Example icon

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntegrationBlueprintConfigEntry,
        alarm_number: int,
        alarm_datetime: datetime,
    ) -> None:
        """Initialize the alarm entity."""
        super().__init__()
        self.hass = hass
        self._alarm_number = alarm_number
        self._alarm_at = alarm_datetime
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
    def native_value(self) -> str:
        """Return the state of the sensor (the alarm time in ISO format)."""
        return self._alarm_at.isoformat()
