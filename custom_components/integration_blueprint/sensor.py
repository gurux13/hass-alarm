"""Sensor platform for integration_blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_ALARM_DATETIME,
    DOMAIN,
    HASS_DATA_ALARM_MANAGER,
    LOGGER,
    SIGNAL_ADD_ALARM,
    SIGNAL_DELETE_ALARM,
)
from .entity import IntegrationBlueprintEntity

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import IntegrationBlueprintConfigEntry
    from .alarm_manager import AlarmManager


# SensorDescription for the sensor that aggregates all alarm information.
ALL_ALARMS_SUMMARY_SENSOR_DESCRIPTION = SensorEntityDescription(
    key=f"{DOMAIN}_all_alarms_summary",  # Unique key for this sensor type
    name="Alarms Count",  # This will be the entity name
    icon="mdi:alarm-multiple",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    from .alarm_manager import async_setup_entry as am_async_setup_entry

    await am_async_setup_entry(hass, entry, async_add_entities)


class AllAlarmsSensor(IntegrationBlueprintEntity, SensorEntity):
    """Sensor representing the count and list of all alarms for this config entry."""

    _attr_should_poll = False  # State is updated via callbacks

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntegrationBlueprintConfigEntry,
        alarm_manager: AlarmManager,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__()
        self.hass = hass
        self._entry_id = entry.entry_id
        self.entity_description = ALL_ALARMS_SUMMARY_SENSOR_DESCRIPTION
        self._alarm_manager = alarm_manager
        self._attr_unique_id = f"{self._entry_id}_{self.entity_description.key}"

        # Associate this summary sensor with the same device as individual alarms
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"Integration Blueprint Alarms ({entry.title})",
            manufacturer="Blueprint Industries",
            model="Managed Alarm",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        """Return the number of active alarms."""
        return len(self._alarm_manager.get_all_alarms_data())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes, including the list of alarm times."""
        alarms_data = self._alarm_manager.get_all_alarms_data()
        if not alarms_data:
            return {"alarm_times": []}

        # Sort by datetime for display purposes in attributes
        sorted_alarm_times = sorted(alarm["datetime_obj"] for alarm in alarms_data)
        return {"alarm_times": [dt.isoformat() for dt in sorted_alarm_times]}
