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
            return {
                "alarm_times": [],
                "alarms_count": 0,
                "enabled_alarms_count": 0,
            }

        enabled_alarms = [
            alarm
            for alarm in alarms_data
            if alarm["enabled"] and alarm["next_run"] is not None
        ]
        sorted_enabled_alarms = sorted(
            enabled_alarms,
            key=lambda alarm: alarm["next_run"],
        )
        next_alarm = sorted_enabled_alarms[0] if sorted_enabled_alarms else None
        next_alarm_entity = None
        if next_alarm:
            next_alarm_entity = (
                f"sensor.wakeup_alarm_alarm_integration_alarm_{next_alarm['number']}"
            )
        return {
            "alarm_times": [
                alarm["next_run"].isoformat() for alarm in sorted_enabled_alarms
            ],
            "alarms_count": len(alarms_data),
            "enabled_alarms_count": len(enabled_alarms),
            "next_alarm_entity": next_alarm_entity,
            "next_alarm_name": next_alarm["name"] if next_alarm else None,
            "next_alarm_type": next_alarm["type"] if next_alarm else None,
            "next_alarm_time": next_alarm.get("time") if next_alarm else None,
            "next_alarm_weekdays": next_alarm.get("weekdays") if next_alarm else None,
        }
