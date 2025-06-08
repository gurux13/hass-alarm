"""Sensor platform for integration_blueprint."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alarm_entity import AlarmEntity
from .alarm_manager import AlarmManager
from .const import (
    ATTR_ALARM_DATETIME,
    DOMAIN,
    LOGGER,
    SIGNAL_ADD_ALARM,
)
from .entity import IntegrationBlueprintEntity

if TYPE_CHECKING:
    from .data import IntegrationBlueprintConfigEntry


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
    """Set up the sensor platform."""
    alarm_manager = AlarmManager(hass, entry.entry_id)
    await alarm_manager.async_load_alarms()

    all_alarms_summary_sensor = AllAlarmsSensor(
        hass, entry, ALL_ALARMS_SUMMARY_SENSOR_DESCRIPTION, alarm_manager
    )

    entities_to_add: list[SensorEntity] = [all_alarms_summary_sensor]

    # Create AlarmEntity instances for any loaded alarms
    for loaded_alarm_data in alarm_manager.get_all_alarms_data():
        entities_to_add.append(
            AlarmEntity(
                hass,
                entry,
                loaded_alarm_data["number"],
                loaded_alarm_data["datetime_obj"],
            )
        )
    async_add_entities(entities_to_add)

    @callback
    def _async_handle_new_alarm_signal(alarm_details: dict[str, Any]) -> None:
        """Handle the signal to add a new alarm from a service call.

        This creates an individual AlarmEntity sensor, adds the alarm to the
        AlarmManager (which handles persistence), and updates the summary sensor.
        """
        alarm_datetime_obj: datetime = alarm_details[ATTR_ALARM_DATETIME]

        # Determine the next alarm number using the alarm manager
        alarm_number = alarm_manager.get_next_alarm_number()

        LOGGER.debug(
            (
                "Sensor platform processing signal for new alarm: Number=%s, DateTime='%s'"
            ),
            alarm_number,
            alarm_datetime_obj.isoformat(),
        )

        # Create the individual sensor entity for this specific alarm
        new_alarm = AlarmEntity(hass, entry, alarm_number, alarm_datetime_obj)
        async_add_entities([new_alarm])

        # Add alarm to the manager, which handles persistence
        alarm_manager.add_alarm(alarm_number, alarm_datetime_obj)

        # Update the summary sensor's state
        all_alarms_summary_sensor.async_write_ha_state()

    # Listen for signals indicating a new alarm has been added via service.
    entry_specific_signal = f"{SIGNAL_ADD_ALARM}_{entry.entry_id}"
    unregister_dispatcher = async_dispatcher_connect(
        hass, entry_specific_signal, _async_handle_new_alarm_signal
    )
    entry.async_on_unload(unregister_dispatcher)


class AllAlarmsSensor(IntegrationBlueprintEntity, SensorEntity):
    """Sensor representing the count and list of all alarms for this config entry."""

    _attr_should_poll = False  # State is updated via callbacks

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntegrationBlueprintConfigEntry,
        entity_description: SensorEntityDescription,
        alarm_manager: AlarmManager,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__()
        self.hass = hass
        self._entry_id = entry.entry_id
        self.entity_description = entity_description
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
