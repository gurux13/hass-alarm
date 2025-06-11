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

from .alarm_manager import AlarmManager
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
    if HASS_DATA_ALARM_MANAGER in hass.data:
        LOGGER.error(
            "AlarmManager already initialized for entry %s. Skipping setup.",
            entry.entry_id,
        )
        return
    # Initialize AlarmManager with the full config entry
    alarm_manager = AlarmManager(hass, entry)
    hass.data[HASS_DATA_ALARM_MANAGER] = alarm_manager

    await alarm_manager.async_load_alarms()

    # Note: entry.runtime_data.scheduled_alarm_triggers is now initialized within AlarmManager's __init__
    # Ensure alarm_entities dict exists in runtime_data for storing entity instances
    entry.runtime_data.alarm_entities = {}

    all_alarms_summary_sensor = AllAlarmsSensor(
        hass, entry, ALL_ALARMS_SUMMARY_SENSOR_DESCRIPTION, alarm_manager
    )

    entities_to_add: list[SensorEntity] = [all_alarms_summary_sensor]

    # Create AlarmEntity instances for loaded alarms and schedule their triggers via AlarmManager
    loaded_alarm_entities = (
        alarm_manager.create_entities_for_loaded_alarms_and_schedule()
    )
    for entity in loaded_alarm_entities:
        entry.runtime_data.alarm_entities[entity.alarm_number] = entity
    entities_to_add.extend(loaded_alarm_entities)

    async_add_entities(entities_to_add)

    @callback
    def _async_handle_new_alarm_signal(alarm_details: dict[str, Any]) -> None:
        """Handle the signal to add a new alarm from a service call.

        This creates an individual AlarmEntity sensor, adds the alarm to the
        AlarmManager (which handles persistence), and updates the summary sensor.
        """
        # This datetime is now guaranteed to be UTC from the __init__.py signal dispatch
        alarm_datetime_utc: datetime = alarm_details[ATTR_ALARM_DATETIME]

        # AlarmManager now handles data creation, persistence, entity object instantiation, and scheduling.
        new_alarm_entity = alarm_manager.create_alarm(alarm_datetime_utc)

        if new_alarm_entity is None:
            LOGGER.error(
                "Failed to create alarm entity via AlarmManager for datetime %s",
                alarm_datetime_utc.isoformat(),
            )
            return

        LOGGER.debug(
            ("Sensor platform received new alarm entity: Number=%s, DateTime='%s'"),
            new_alarm_entity.alarm_number,  # Accessing property from AlarmEntity
            new_alarm_entity.native_value.isoformat(),  # Accessing property from AlarmEntity
        )

        # Add the entity to Home Assistant
        async_add_entities([new_alarm_entity])
        entry.runtime_data.alarm_entities[new_alarm_entity.alarm_number] = (
            new_alarm_entity
        )

        # Update the summary sensor's state
        all_alarms_summary_sensor.async_write_ha_state()

    @callback
    async def _async_handle_delete_alarm_signal(alarm_details: dict[str, Any]) -> None:
        """Handle the signal to delete an alarm from a service call."""
        all_alarms_summary_sensor.async_write_ha_state()

    # Listen for signals indicating a new alarm has been added via service.
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_ADD_ALARM}_{entry.entry_id}", _async_handle_new_alarm_signal
        )
    )
    # Listen for signals indicating an alarm should be deleted.
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{SIGNAL_DELETE_ALARM}_{entry.entry_id}",
            _async_handle_delete_alarm_signal,
        )
    )
    # Register AlarmManager's cleanup function for all scheduled triggers on unload
    entry.async_on_unload(alarm_manager.async_cancel_all_scheduled_triggers)


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
