"""Sensor platform for integration_blueprint."""

from __future__ import annotations
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .alarm_entity import AlarmEntity
from .alarm_manager import AlarmManager
from .const import (
    ATTR_ALARM_DATETIME,
    DOMAIN,
    EVENT_ALARM_TRIGGERED,
    LOGGER,
    SIGNAL_DELETE_ALARM,
    SIGNAL_ADD_ALARM,
    HASS_DATA_ALARM_MANAGER,
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
    if HASS_DATA_ALARM_MANAGER in hass.data:
        LOGGER.error(
            "AlarmManager already initialized for entry %s. Skipping setup.",
            entry.entry_id,
        )
        return
    alarm_manager = AlarmManager(hass, entry.entry_id)
    hass.data[HASS_DATA_ALARM_MANAGER] = alarm_manager

    await alarm_manager.async_load_alarms()

    # Initialize storage for scheduled alarm trigger removers
    entry.runtime_data.scheduled_alarm_triggers = {}

    all_alarms_summary_sensor = AllAlarmsSensor(
        hass, entry, ALL_ALARMS_SUMMARY_SENSOR_DESCRIPTION, alarm_manager
    )

    entities_to_add: list[SensorEntity] = [all_alarms_summary_sensor]

    # Ensure alarm_entities dict exists in runtime_data
    if not hasattr(entry.runtime_data, "alarm_entities"):
        entry.runtime_data.alarm_entities = {}

    @callback
    def _async_schedule_alarm_event(
        hass_ref: HomeAssistant,
        config_entry_ref: IntegrationBlueprintConfigEntry,
        alarm_number: int,
        alarm_datetime_utc: datetime,
    ) -> None:
        """Schedule an event to be fired when the alarm time is reached."""
        # Ensure we don't schedule for past alarms
        if alarm_datetime_utc <= dt_util.utcnow():
            LOGGER.debug(
                "Alarm %s for entry %s is in the past (%s). Not scheduling event.",
                alarm_number,
                config_entry_ref.entry_id,
                alarm_datetime_utc.isoformat(),
            )
            return

        @callback
        async def _fire_alarm_event_callback(time_now: datetime) -> None:
            """Callback executed when alarm time is reached."""
            LOGGER.info(
                "Alarm %s for entry %s triggered at %s (scheduled for %s)",
                alarm_number,
                config_entry_ref.entry_id,
                time_now.isoformat(),
                alarm_datetime_utc.isoformat(),
            )
            hass_ref.bus.async_fire(
                EVENT_ALARM_TRIGGERED,
                {
                    "config_entry_id": config_entry_ref.entry_id,
                    "alarm_number": alarm_number,
                    "alarm_datetime": alarm_datetime_utc.isoformat(),
                },
            )
            # Clean up this specific trigger from the registry as it has fired
            if alarm_number in config_entry_ref.runtime_data.scheduled_alarm_triggers:
                del config_entry_ref.runtime_data.scheduled_alarm_triggers[alarm_number]

        LOGGER.debug(
            "Scheduling event for alarm %s at %s (UTC)",
            alarm_number,
            alarm_datetime_utc.isoformat(),
        )
        # Schedule the event and store the unregister callback
        unregister_listener = async_track_point_in_time(
            hass_ref, _fire_alarm_event_callback, alarm_datetime_utc
        )
        config_entry_ref.runtime_data.scheduled_alarm_triggers[alarm_number] = (
            unregister_listener
        )

    # Create AlarmEntity instances for any loaded alarms
    for alarm_data in alarm_manager.get_all_alarms_data():
        alarm_entity = AlarmEntity(
            hass,
            entry,
            alarm_data["number"],
            alarm_data["datetime_obj"],  # This is now guaranteed UTC by AlarmManager
        )
        entities_to_add.append(alarm_entity)
        entry.runtime_data.alarm_entities[alarm_data["number"]] = alarm_entity
        # Schedule event trigger for existing alarms
        _async_schedule_alarm_event(
            hass, entry, alarm_data["number"], alarm_data["datetime_obj"]
        )

    async_add_entities(entities_to_add)

    @callback
    def _async_cancel_alarm_event(alarm_number: int) -> None:
        """Cancel a scheduled alarm event trigger."""
        if alarm_number in entry.runtime_data.scheduled_alarm_triggers:
            LOGGER.debug("Cancelling scheduled event for alarm %s", alarm_number)
            entry.runtime_data.scheduled_alarm_triggers.pop(
                alarm_number
            )()  # Call the unregister callback
        else:
            LOGGER.debug(
                "No scheduled event found for alarm %s to cancel.", alarm_number
            )

    @callback
    def _async_handle_new_alarm_signal(alarm_details: dict[str, Any]) -> None:
        """Handle the signal to add a new alarm from a service call.

        This creates an individual AlarmEntity sensor, adds the alarm to the
        AlarmManager (which handles persistence), and updates the summary sensor.
        """
        # This datetime is now guaranteed to be UTC from the __init__.py signal dispatch
        alarm_datetime_utc: datetime = alarm_details[ATTR_ALARM_DATETIME]

        # Determine the next alarm number using the alarm manager
        alarm_number = alarm_manager.get_next_alarm_number()

        LOGGER.debug(
            (
                "Sensor platform processing signal for new alarm: Number=%s, DateTime='%s'"
            ),
            alarm_number,
            alarm_datetime_utc.isoformat(),
        )

        # Create the individual sensor entity for this specific alarm
        new_alarm = AlarmEntity(hass, entry, alarm_number, alarm_datetime_utc)
        async_add_entities([new_alarm])
        entry.runtime_data.alarm_entities[alarm_number] = new_alarm

        # Add alarm to the manager, which handles persistence
        alarm_manager.add_alarm(alarm_number, alarm_datetime_utc)

        # Update the summary sensor's state
        all_alarms_summary_sensor.async_write_ha_state()

        # Schedule the event trigger for the new alarm
        _async_schedule_alarm_event(hass, entry, alarm_number, alarm_datetime_utc)

    @callback
    async def _async_handle_delete_alarm_signal(alarm_details: dict[str, Any]) -> None:
        """Handle the signal to delete an alarm from a service call."""
        alarm_number_to_delete = alarm_details["alarm_number"]
        LOGGER.debug(
            "Sensor platform processing signal to delete alarm: Number=%s",
            alarm_number_to_delete,
        )

        if alarm_manager.delete_alarm(alarm_number_to_delete):
            # Cancel any scheduled event for this alarm
            _async_cancel_alarm_event(alarm_number_to_delete)

            entity_to_remove = entry.runtime_data.alarm_entities.pop(
                alarm_number_to_delete, None
            )
            if entity_to_remove:
                LOGGER.debug("Removing alarm entity: %s", entity_to_remove.entity_id)
                await entity_to_remove.async_remove()
            else:
                LOGGER.warning(
                    "Alarm entity for number %s not found in runtime data for removal.",
                    alarm_number_to_delete,
                )
            all_alarms_summary_sensor.async_write_ha_state()
        else:
            LOGGER.warning(
                "Failed to delete alarm %s via alarm manager.", alarm_number_to_delete
            )

    # Setup cleanup for all scheduled triggers when the config entry is unloaded
    @callback
    def _async_cancel_all_scheduled_alarm_triggers() -> None:
        LOGGER.debug(
            "Cancelling all scheduled alarm triggers for entry %s", entry.entry_id
        )
        for alarm_num in list(entry.runtime_data.scheduled_alarm_triggers.keys()):
            _async_cancel_alarm_event(alarm_num)

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
    # Register the cleanup function for when the entry is unloaded
    entry.async_on_unload(_async_cancel_all_scheduled_alarm_triggers)


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
