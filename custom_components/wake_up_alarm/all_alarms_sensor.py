"""Sensor platform for wake_up_alarm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)

from .const import (
    DOMAIN,
)
from .entity import WakeUpAlarmEntity

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from .alarm_manager import AlarmManager
    from .data import WakeUpAlarmConfigEntry

# SensorDescription for the sensor that aggregates all alarm information.
ALL_ALARMS_SUMMARY_SENSOR_DESCRIPTION = SensorEntityDescription(
    key=f"{DOMAIN}_all_alarms_summary",
    name="Next alarm",
    icon="mdi:alarm-multiple",
)


class AllAlarmsSensor(WakeUpAlarmEntity, SensorEntity):
    """Sensor representing the next alarm and list of all alarms."""

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
        self.entity_description = ALL_ALARMS_SUMMARY_SENSOR_DESCRIPTION
        self._alarm_manager = alarm_manager
        self._attr_unique_id = f"{self._entry_id}_{self.entity_description.key}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the number of active alarms."""
        return self._alarm_manager.get_next_alarm_time()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes, including the list of alarm times."""
        alarms_data = self._alarm_manager.get_all_alarms_data()
        if not alarms_data:
            return {"alarm_times": [], "alarms_count": 0}

        # Sort by datetime for display purposes in attributes
        sorted_alarm_times = sorted(alarm["datetime_obj"] for alarm in alarms_data)
        return {
            "alarm_times": [dt.isoformat() for dt in sorted_alarm_times],
            "alarms_count": len(sorted_alarm_times),
        }
