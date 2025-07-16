"""Alarm Manager for wake_up_alarm."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers import entity_registry
from homeassistant.util import dt as dt_util

from .alarm_entity import AlarmEntity  # Added
from .const import (
    ATTR_ALARM_DATETIME,
    EVENT_ALARM_TRIGGERED,
    HASS_DATA_ALARM_MANAGER,
    LOGGER,
    SIGNAL_ADD_ALARM,
    SIGNAL_DELETE_ALARM,
    STORAGE_KEY_ALARMS_FORMAT,
    STORAGE_VERSION,
)
from .data import WakeUpAlarmConfigEntry  # Added
from .sensor import AllAlarmsSensor

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import WakeUpAlarmConfigEntry


async def async_remove_entry(hass, entry) -> None:
    if HASS_DATA_ALARM_MANAGER in hass.data:
        del hass.data[HASS_DATA_ALARM_MANAGER]
        LOGGER.debug(
            "Removed alarm manager for %s.",
            entry.entry_id,
        )
        return


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
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

    all_alarms_summary_sensor = AllAlarmsSensor(hass, entry, alarm_manager)

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


class AlarmManager:
    """Manages loading, saving, and accessing alarm data."""

    @classmethod
    def get_instance(cls, hass: HomeAssistant) -> AlarmManager | None:
        """Get the AlarmManager instance for the given Home Assistant instance."""
        return hass.data.get(HASS_DATA_ALARM_MANAGER)

    @classmethod
    def execute_on_instance(
        cls, hass: HomeAssistant, func: Callable
    ) -> tuple[bool, Any]:
        """
        Execute a function on the AlarmManager instance if it exists.

        Returns a tuple (success: bool, result: Any).
        """
        instance = cls.get_instance(hass)
        if instance is None:
            return False, None
        result = func(instance)
        return True, result

    @classmethod
    async def execute_on_instance_async(
        cls, hass: HomeAssistant, func: Callable[[AlarmManager], Any]
    ) -> tuple[bool, Any]:
        """
        Execute an async function on the AlarmManager instance if it exists.

        Returns a tuple (success: bool, result: Any).
        """
        instance = cls.get_instance(hass)
        if instance is None:
            return False, None
        result = await func(instance)
        return True, result

    def save_instance(self, hass: HomeAssistant) -> None:
        """Save the AlarmManager instance to the Home Assistant data."""
        hass.data[HASS_DATA_ALARM_MANAGER] = self

    def __init__(self, hass: HomeAssistant, entry: WakeUpAlarmConfigEntry) -> None:
        """Initialize the Alarm Manager."""
        if HASS_DATA_ALARM_MANAGER in hass.data:
            msg = (
                f"AlarmManager already initialized for entry {entry.entry_id}. "
                "Only one instance can be created per config entry."
            )
            raise RuntimeError(msg)
        self.save_instance(hass)
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        # _alarms stores {"number": int, "datetime_obj": datetime}
        self._alarms: list[dict[str, Any]] = []
        self._free_alarm_numbers: set[int] = set()

        storage_key = STORAGE_KEY_ALARMS_FORMAT.format(entry_id=self._entry_id)
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, storage_key
        )
        self._entry.runtime_data.scheduled_alarm_triggers = {}

    def recalculate_free_alarm_numbers(self) -> None:
        """Recalculate the set of free alarm numbers based on current alarms."""
        if not self._alarms:
            self._free_alarm_numbers = set()
        else:
            used_numbers = {alarm["number"] for alarm in self._alarms}
            self._free_alarm_numbers = {
                num
                for num in range(1, max(used_numbers) + 1)
                if num not in used_numbers
            }

    def get_next_alarm_time(self) -> datetime | None:
        """Get the next alarm time, or None if no alarms are set."""
        if not self._alarms:
            return None
        # Return the earliest alarm datetime
        return min(alarm["datetime_obj"] for alarm in self._alarms)

    async def async_load_alarms(self) -> None:
        """Load alarms from the store."""
        if not (stored_alarms_raw := await self._store.async_load()):
            LOGGER.debug("No persisted alarms found for %s", self._entry_id)
            return

        loaded_alarms: list[dict[str, Any]] = []
        for alarm_raw in stored_alarms_raw:
            try:
                if not all(k in alarm_raw for k in ("number", "datetime")):
                    LOGGER.warning("Skipping malformed alarm data: %s", alarm_raw)
                    continue
                if not isinstance(alarm_raw["number"], int) or not isinstance(
                    alarm_raw["datetime"], str
                ):
                    LOGGER.warning(
                        "Skipping alarm data with incorrect types: %s", alarm_raw
                    )
                    continue

                # Ensure the loaded datetime is UTC
                # dt_util.parse_datetime will return a tz-aware datetime if the string has tz info
                # or naive if it doesn't. We assume naive datetimes from storage were UTC.
                parsed_datetime_raw = dt_util.parse_datetime(alarm_raw["datetime"])
                if parsed_datetime_raw is None:
                    LOGGER.warning(
                        "Could not parse datetime string for alarm: %s", alarm_raw
                    )
                    continue

                if parsed_datetime_raw.tzinfo is None:
                    LOGGER.warning(
                        "Loaded alarm datetime '%s' for number %s is tz-unknown, assuming it was stored as UTC.",
                        alarm_raw["datetime"],
                        alarm_raw["number"],
                    )
                    parsed_datetime = parsed_datetime_raw.replace(tzinfo=dt_util.UTC)
                else:
                    parsed_datetime = dt_util.as_utc(parsed_datetime_raw)

                loaded_alarms.append(
                    {"number": alarm_raw["number"], "datetime_obj": parsed_datetime}
                )
            except (TypeError, ValueError) as ex:
                LOGGER.warning("Could not parse stored alarm %s: %s", alarm_raw, ex)

        self._alarms = sorted(loaded_alarms, key=lambda x: x["number"])
        self.recalculate_free_alarm_numbers()
        LOGGER.debug(
            "Loaded %s alarms for %s from store", len(self._alarms), self._entry_id
        )

    def get_all_alarms_data(self) -> list[dict[str, Any]]:
        """Return a copy of all current alarm data (number, datetime_obj)."""
        return list(self._alarms)  # Return a copy

    def get_next_alarm_number(self) -> int:
        """Determine the next available alarm number."""
        if not self._free_alarm_numbers:
            # If no free numbers, return the next number after the highest existing one
            return self._get_next_alarm_number_after_highest()
        return min(self._free_alarm_numbers)

    def _get_next_alarm_number_after_highest(self) -> int:
        """Determine the next available alarm number after the highest existing one."""
        if not self._alarms:
            return 1
        return max(alarm["number"] for alarm in self._alarms) + 1

    def get_alarm(self, alarm_number: int) -> dict[str, Any] | None:
        """Get an alarm by its number."""
        for alarm in self._alarms:
            if alarm["number"] == alarm_number:
                return alarm
        return None

    @callback
    def _create_alarm_data_and_persist(
        self, alarm_datetime: datetime
    ) -> dict[str, Any] | None:
        """
        Create data for a new alarm, assign a number, add it to internal list, and schedule save.

        Returns the details (number, datetime_obj) of the created alarm data, or None if creation failed.
        """
        alarm_number = self.get_next_alarm_number()

        if self.add_alarm_data(alarm_number, alarm_datetime):
            LOGGER.debug(
                "Alarm %s created in manager with datetime %s.",
                alarm_number,
                alarm_datetime.isoformat(),  # Log the input datetime for clarity
            )
            return {
                "number": alarm_number,
                "datetime_obj": alarm_datetime,
            }
        return None

    @callback
    def create_alarm(self, alarm_datetime_utc: datetime) -> AlarmEntity | None:
        """
        Create alarm e2e
        """
        created_alarm_data = self._create_alarm_data_and_persist(alarm_datetime_utc)

        if created_alarm_data:
            alarm_number = created_alarm_data["number"]
            actual_alarm_datetime_utc = created_alarm_data["datetime_obj"]
            alarm_entity = AlarmEntity(
                self.hass, self._entry, alarm_number, actual_alarm_datetime_utc
            )
            self._async_schedule_alarm_event_trigger(
                alarm_number, actual_alarm_datetime_utc
            )
            return alarm_entity
        return None

    def create_entities_for_loaded_alarms_and_schedule(self) -> list[AlarmEntity]:
        """
        Creates AlarmEntity instances for all loaded alarms and schedules their triggers.
        Returns a list of created AlarmEntity instances.
        """
        created_entities: list[AlarmEntity] = []
        for alarm_data in self.get_all_alarms_data():
            alarm_entity = AlarmEntity(
                self.hass,
                self._entry,
                alarm_data["number"],
                alarm_data["datetime_obj"],
            )
            created_entities.append(alarm_entity)
            self._async_schedule_alarm_event_trigger(
                alarm_data["number"], alarm_data["datetime_obj"]
            )
        return created_entities

    @callback
    def _async_schedule_alarm_event_trigger(
        self, alarm_number: int, alarm_datetime_utc: datetime
    ) -> None:
        """Schedule an event to be fired when the alarm time is reached."""

        @callback
        async def _fire_alarm_event_callback(_now: datetime) -> None:
            """Callback executed when alarm time is reached."""
            LOGGER.info(
                "Alarm %s for entry %s triggered (scheduled for %s)",
                alarm_number,
                self._entry_id,
                alarm_datetime_utc.isoformat(),
            )
            self.hass.bus.async_fire(
                EVENT_ALARM_TRIGGERED,
                {
                    "config_entry_id": self._entry_id,
                    "alarm_number": alarm_number,
                    "alarm_datetime": alarm_datetime_utc.isoformat(),
                },
            )
            await self.delete_alarm(alarm_number)  # Remove alarm after firing
            if alarm_number in self._entry.runtime_data.scheduled_alarm_triggers:
                del self._entry.runtime_data.scheduled_alarm_triggers[alarm_number]

        if alarm_datetime_utc <= dt_util.utcnow():
            LOGGER.debug(
                "Alarm %s for entry %s is in the past (%s). Firing NOW.",
                alarm_number,
                self._entry_id,
                alarm_datetime_utc.isoformat(),
            )
            # If the alarm time is in the past, fire immediately
            self.hass.async_create_task(_fire_alarm_event_callback(dt_util.utcnow()))
            return

        LOGGER.debug(
            "Scheduling event for alarm %s at %s (UTC)",
            alarm_number,
            alarm_datetime_utc.isoformat(),
        )
        unregister_listener = async_track_point_in_time(
            self.hass, _fire_alarm_event_callback, alarm_datetime_utc
        )
        self._entry.runtime_data.scheduled_alarm_triggers[alarm_number] = (
            unregister_listener
        )

    @callback
    def add_alarm_data(self, alarm_number: int, alarm_datetime: datetime) -> bool:
        """Add an alarm, update internal list, and schedule save. Returns True if successful."""
        alarm_datetime_utc = alarm_datetime.astimezone(UTC)

        if any(alarm["number"] == alarm_number for alarm in self._alarms):
            LOGGER.warning(
                "Attempted to add alarm with duplicate number %s. Skipping.",
                alarm_number,
            )
            return False

        self._alarms.append(
            {"number": alarm_number, "datetime_obj": alarm_datetime_utc}
        )
        if alarm_number in self._free_alarm_numbers:
            self._free_alarm_numbers.remove(alarm_number)
        LOGGER.debug(
            "Alarm %s (datetime: %s) added to manager. Total alarms: %s. Scheduling save.",
            alarm_number,
            alarm_datetime_utc.isoformat(),
            len(self._alarms),
        )
        self.hass.async_create_task(self._async_save_alarms_to_store())
        return True

    @callback
    def _async_cancel_scheduled_alarm_trigger(self, alarm_number: int) -> None:
        """Cancel a scheduled alarm event trigger."""
        if alarm_number in self._entry.runtime_data.scheduled_alarm_triggers:
            LOGGER.debug(
                "Cancelling scheduled event for alarm %s for entry %s",
                alarm_number,
                self._entry_id,
            )
            # Call the unregister callback and remove from dict
            self._entry.runtime_data.scheduled_alarm_triggers.pop(alarm_number)()
        else:
            LOGGER.debug(
                "No scheduled event found for alarm %s (entry %s) to cancel.",
                alarm_number,
                self._entry_id,
            )

    @callback
    async def delete_all_alarms(self) -> int:
        """Delete all alarms, update internal list, and schedule save."""
        deleted_count = 0
        # Iterate over a copy of the list because delete_alarm modifies self._alarms
        # and removes items from self._entry.runtime_data.alarm_entities
        for alarm_data in list(self._alarms):
            if await self.delete_alarm(alarm_data["number"]):
                deleted_count += 1

        LOGGER.debug("Deleted %s alarms.", deleted_count)
        # The individual delete_alarm calls handle saving and entity removal.
        return deleted_count

    @callback
    async def delete_alarm(self, alarm_number: int) -> bool:
        """Delete an alarm by its number, update internal list, and schedule save."""
        initial_alarm_count = len(self._alarms)
        self._alarms = [
            alarm for alarm in self._alarms if alarm["number"] != alarm_number
        ]

        if len(self._alarms) < initial_alarm_count:
            LOGGER.debug(
                "Alarm %s removed from manager. Total alarms: %s. Scheduling save.",
                alarm_number,
                len(self._alarms),
            )
            self._free_alarm_numbers.add(alarm_number)
            self._async_cancel_scheduled_alarm_trigger(
                alarm_number
            )  # Cancel scheduled event
            self.hass.async_create_task(self._async_save_alarms_to_store())
            entity_to_remove = self._entry.runtime_data.alarm_entities.pop(
                alarm_number, None
            )
            if entity_to_remove:
                LOGGER.debug("Removing alarm entity: %s", entity_to_remove.entity_id)
                await entity_to_remove.async_remove()
                er = entity_registry.async_get(self.hass)
                er.async_remove(entity_to_remove.entity_id)
            else:
                LOGGER.warning(
                    "Alarm entity for number %s not found in runtime data for removal.",
                    alarm_number,
                )
            return True
        LOGGER.warning(
            "Attempted to delete non-existent alarm number %s.", alarm_number
        )

        return False

    @callback
    def async_cancel_all_scheduled_triggers(self) -> None:
        """Cancel all scheduled alarm triggers for this manager's entry."""
        LOGGER.debug(
            "Cancelling all scheduled alarm triggers for entry %s", self._entry_id
        )
        # Iterate over a copy of keys as _async_cancel_scheduled_alarm_trigger modifies the dict
        for alarm_num in list(self._entry.runtime_data.scheduled_alarm_triggers.keys()):
            self._async_cancel_scheduled_alarm_trigger(alarm_num)

    async def _async_save_alarms_to_store(self) -> None:
        """Save the current list of alarms to the store."""
        LOGGER.debug(
            "Saving %s alarms to store for %s", len(self._alarms), self._entry_id
        )
        data_to_save = [
            {"number": alarm["number"], "datetime": alarm["datetime_obj"].isoformat()}
            for alarm in self._alarms
        ]
        await self._store.async_save(data_to_save)
