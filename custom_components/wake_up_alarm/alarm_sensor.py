"""Sensor platform for wake_up_alarm."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)

from .const import (
    DOMAIN,
    LOGGER,
)
from .entity import WakeUpAlarmEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .alarm_manager import AlarmManager
    from .data import WakeUpAlarmConfigEntry

# SensorDescription for the sensor that aggregates all alarm information.
IS_ALARM_SENSOR_DESCRIPTION = SensorEntityDescription(
    key=f"{DOMAIN}_is_alarm",
    name="Is Alarming Now",
    icon="mdi:alarm",
)


# Sensor that indicates whether an alarm is currently triggering.
class IsAlarmSensor(WakeUpAlarmEntity, SensorEntity):
    """Sensor representing whether it's alarming now."""

    _attr_should_poll = False  # State is updated via callbacks

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WakeUpAlarmConfigEntry,
        alarm_manager: AlarmManager,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__()
        self.hass = hass
        self._entry_id = entry.entry_id
        self.entity_description = IS_ALARM_SENSOR_DESCRIPTION
        self._alarm_manager = alarm_manager
        self._attr_unique_id = f"{self._entry_id}_{self.entity_description.key}"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["NO", "YES"]
        self.is_alarming = False

    def trigger(self) -> None:
        """Trigger a refresh of the sensor state."""
        LOGGER.debug("Refreshing is alarming sensor")
        self.is_alarming = True
        self.async_write_ha_state()
        self.is_alarming = False
        self.async_write_ha_state()

    def should_poll(self) -> bool:
        """Return whether the sensor should poll."""
        return False

    @property
    def native_value(self) -> str | None:
        """Return the number of active alarms."""
        return "YES" if self.is_alarming else "NO"
