"""Alarm Manager for wake_up_alarm."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .alarm_entity import AlarmEntity
from .alarm_model import (
    ALARM_TYPE_ONE_TIME,
    ALARM_TYPE_RECURRING,
    calculate_next_recurring_run,
    create_one_time_alarm,
    normalize_alarm,
    serialize_alarm,
)
from .alarm_model import (
    create_recurring_alarm as create_recurring_alarm_data,
)
from .alarm_sensor import IsAlarmSensor
from .all_alarms_sensor import AllAlarmsSensor
from .const import (
    ATTR_ALARM_DATETIME,
    ATTR_ALARM_TYPE,
    ATTR_ENABLED,
    ATTR_NAME,
    ATTR_TIME,
    ATTR_WEEKDAYS,
    EVENT_ALARM_FIRED,
    EVENT_ALARM_TRIGGERED,
    HASS_DATA_ALARM_MANAGER,
    LOGGER,
    SIGNAL_ADD_ALARM,
    SIGNAL_DELETE_ALARM,
    STORAGE_KEY_ALARMS_FORMAT,
    STORAGE_VERSION,
)
from .data import WakeUpAlarmConfigEntry

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.components.sensor import SensorEntity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import WakeUpAlarmConfigEntry


async def async_remove_entry(
    hass: HomeAssistant, entry: WakeUpAlarmConfigEntry
) -> None:
    """Handle removal of the entry."""
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

    entry.runtime_data.alarm_entities = {}

    all_alarms_summary_sensor = AllAlarmsSensor(hass, entry, alarm_manager)

    is_alarming_sensor = IsAlarmSensor(hass, entry, alarm_manager)

    entities_to_add: list[SensorEntity] = [
        all_alarms_summary_sensor,
        is_alarming_sensor,
    ]

    loaded_alarm_entities = (
        alarm_manager.create_entities_for_loaded_alarms_and_schedule()
    )
    for entity in loaded_alarm_entities:
        entry.runtime_data.alarm_entities[entity.alarm_number] = entity
    entities_to_add.extend(loaded_alarm_entities)

    async_add_entities(entities_to_add)

    @callback
    def _async_handle_new_alarm_signal(alarm_details: dict[str, Any]) -> None:
        """
        Handle the signal to add a new alarm from a service call.

        This creates an individual AlarmEntity sensor, adds the alarm to the
        AlarmManager (which handles persistence), and updates the summary sensor.
        """
        if alarm_details.get(ATTR_ALARM_TYPE) == ALARM_TYPE_RECURRING:
            new_alarm_entity = alarm_manager.create_recurring_alarm(
                alarm_details[ATTR_TIME],
                alarm_details[ATTR_WEEKDAYS],
                name=alarm_details.get(ATTR_NAME),
                enabled=alarm_details.get(ATTR_ENABLED, True),
            )
        else:
            alarm_datetime_utc: datetime = alarm_details[ATTR_ALARM_DATETIME]
            new_alarm_entity = alarm_manager.create_alarm(
                alarm_datetime_utc,
                name=alarm_details.get(ATTR_NAME),
                enabled=alarm_details.get(ATTR_ENABLED, True),
            )

        if new_alarm_entity is None:
            LOGGER.error(
                "Failed to create alarm entity via AlarmManager for %s",
                alarm_details,
            )
            return

        LOGGER.debug(
            "Sensor platform received new alarm entity: Number=%s, Value='%s'",
            new_alarm_entity.alarm_number,
            new_alarm_entity.native_value,
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
        await alarm_manager.delete_alarm(alarm_details["alarm_number"])

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
        # _alarms stores normalized alarm dictionaries. See alarm_model.py.
        self._alarms: list[dict[str, Any]] = []
        self._free_alarm_numbers: set[int] = set()

        storage_key = STORAGE_KEY_ALARMS_FORMAT.format(entry_id=self._entry_id)
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, storage_key
        )
        self._entry.runtime_data.scheduled_alarm_triggers = {}

    def refresh_sensor(self) -> None:
        """Refresh the next alarm sensor."""
        component = self.hass.data.get("sensor")
        sensor = component.get_entity("sensor.next_alarm") if component else None
        if sensor:
            LOGGER.debug("Refreshing next alarm sensor")
            sensor.async_write_ha_state()
        else:
            LOGGER.warning("Next alarm sensor not found in entity registry.")

    def trigger_is_alarming_sensor(self) -> None:
        """Trigger update of the is_alarming_now sensor."""
        component = self.hass.data.get("sensor")
        sensor = component.get_entity("sensor.is_alarming_now") if component else None
        if sensor:
            LOGGER.debug("Refreshing next alarm sensor")
            sensor.trigger()
        else:
            LOGGER.warning("Next alarm sensor not found in entity registry.")

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
        enabled_alarm_times = [
            alarm["next_run"]
            for alarm in self._alarms
            if alarm["enabled"] and alarm["next_run"] is not None
        ]
        if not enabled_alarm_times:
            return None
        return min(enabled_alarm_times)

    async def async_load_alarms(self) -> None:
        """Load alarms from the store."""
        if not (stored_alarms_raw := await self._store.async_load()):
            LOGGER.debug("No persisted alarms found for %s", self._entry_id)
            return

        loaded_alarms: list[dict[str, Any]] = []
        for alarm_raw in stored_alarms_raw:
            try:
                if "number" not in alarm_raw:
                    LOGGER.warning("Skipping malformed alarm data: %s", alarm_raw)
                    continue
                if not isinstance(alarm_raw["number"], int):
                    LOGGER.warning(
                        "Skipping alarm data with incorrect types: %s", alarm_raw
                    )
                    continue

                loaded_alarms.append(normalize_alarm(alarm_raw))
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
        self,
        alarm_datetime: datetime,
        *,
        name: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any] | None:
        """
        Create data for a new alarm, add it to internal list, and schedule a save.

        Returns the details (number, datetime_obj) of the created alarm data, or None
        if creation failed.
        """
        alarm_number = self.get_next_alarm_number()

        if self.add_alarm_data(
            alarm_number,
            alarm_datetime,
            name=name,
            enabled=enabled,
        ):
            LOGGER.debug(
                "Alarm %s created in manager with datetime %s.",
                alarm_number,
                alarm_datetime.isoformat(),  # Log the input datetime for clarity
            )
            return self.get_alarm(alarm_number)
        return None

    @callback
    def create_alarm(
        self,
        alarm_datetime_utc: datetime,
        *,
        name: str | None = None,
        enabled: bool = True,
    ) -> AlarmEntity | None:
        """Create alarm e2e."""
        created_alarm_data = self._create_alarm_data_and_persist(
            alarm_datetime_utc,
            name=name,
            enabled=enabled,
        )

        if created_alarm_data:
            alarm_number = created_alarm_data["number"]
            actual_alarm_datetime_utc = created_alarm_data["datetime_obj"]
            alarm_entity = AlarmEntity(
                self.hass,
                self._entry,
                alarm_number,
                actual_alarm_datetime_utc,
                created_alarm_data,
            )
            if enabled:
                self._async_schedule_alarm_event_trigger(
                    alarm_number, actual_alarm_datetime_utc
                )
            return alarm_entity
        return None

    def create_entities_for_loaded_alarms_and_schedule(self) -> list[AlarmEntity]:
        """
        Create AlarmEntity instances for all loaded alarms and schedules triggers.

        Returns a list of created AlarmEntity instances.
        """
        created_entities: list[AlarmEntity] = []
        for alarm_data in self.get_all_alarms_data():
            alarm_entity = AlarmEntity(
                self.hass,
                self._entry,
                alarm_data["number"],
                alarm_data["next_run"] or dt_util.utcnow(),
                alarm_data,
            )
            created_entities.append(alarm_entity)
            if alarm_data["enabled"] and alarm_data["next_run"] is not None:
                self._async_schedule_alarm_event_trigger(
                    alarm_data["number"], alarm_data["next_run"]
                )
        return created_entities

    @callback
    def _async_schedule_alarm_event_trigger(
        self, alarm_number: int, alarm_datetime_utc: datetime
    ) -> None:
        """Schedule an event to be fired when the alarm time is reached."""

        @callback
        async def _fire_alarm_event_callback(_now: datetime) -> None:
            """Execute callback when alarm time is reached."""
            alarm = self.get_alarm(alarm_number)
            if alarm is None:
                LOGGER.warning("Triggered alarm %s no longer exists.", alarm_number)
                return

            LOGGER.info(
                "Alarm %s for entry %s triggered (scheduled for %s)",
                alarm_number,
                self._entry_id,
                alarm_datetime_utc.isoformat(),
            )
            entity = self._entry.runtime_data.alarm_entities.get(alarm_number)
            entity_id = entity.entity_id if entity else None
            event_data = {
                "config_entry_id": self._entry_id,
                "alarm_number": alarm_number,
                "entity_id": entity_id,
                "name": alarm["name"],
                "type": alarm["type"],
                "scheduled_time": alarm_datetime_utc.isoformat(),
                "alarm_datetime": alarm_datetime_utc.isoformat(),
            }
            self.hass.bus.async_fire(EVENT_ALARM_FIRED, event_data)
            self.hass.bus.async_fire(
                EVENT_ALARM_TRIGGERED,
                event_data,
            )
            self.trigger_is_alarming_sensor()
            if alarm_number in self._entry.runtime_data.scheduled_alarm_triggers:
                del self._entry.runtime_data.scheduled_alarm_triggers[alarm_number]
            if alarm["type"] == ALARM_TYPE_RECURRING:
                alarm["next_run"] = calculate_next_recurring_run(
                    alarm["time"],
                    alarm["weekdays"],
                    now=dt_util.now(),
                )
                alarm["skip_next"] = False
                self.hass.async_create_task(self._async_save_alarms_to_store())
                if entity:
                    entity.async_write_ha_state()
                self._async_schedule_alarm_event_trigger(
                    alarm_number,
                    alarm["next_run"],
                )
                self.refresh_sensor()
                return

            await self.delete_alarm(alarm_number)  # Remove one-time alarm after firing

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
    def add_alarm_data(
        self,
        alarm_number: int,
        alarm_datetime: datetime,
        *,
        name: str | None = None,
        enabled: bool = True,
    ) -> bool:
        """Add an alarm and update internal list. Returns True if successful."""
        alarm_datetime_utc = alarm_datetime.astimezone(UTC)

        if any(alarm["number"] == alarm_number for alarm in self._alarms):
            LOGGER.warning(
                "Attempted to add alarm with duplicate number %s. Skipping.",
                alarm_number,
            )
            return False

        self._alarms.append(
            create_one_time_alarm(
                alarm_number,
                alarm_datetime_utc,
                name=name,
                enabled=enabled,
                created_at=dt_util.utcnow(),
            )
        )
        if alarm_number in self._free_alarm_numbers:
            self._free_alarm_numbers.remove(alarm_number)
        LOGGER.debug(
            "Alarm %s (datetime: %s) added. Total alarms: %s. Scheduling save.",
            alarm_number,
            alarm_datetime_utc.isoformat(),
            len(self._alarms),
        )
        self.hass.async_create_task(self._async_save_alarms_to_store())
        return True

    @callback
    def create_recurring_alarm(
        self,
        time_value: str,
        weekdays: list[str],
        *,
        name: str | None = None,
        enabled: bool = True,
    ) -> AlarmEntity | None:
        """Create recurring alarm e2e."""
        alarm_number = self.get_next_alarm_number()

        if any(alarm["number"] == alarm_number for alarm in self._alarms):
            LOGGER.warning(
                "Attempted to add alarm with duplicate number %s. Skipping.",
                alarm_number,
            )
            return None

        alarm_data = create_recurring_alarm_data(
            alarm_number,
            time_value,
            weekdays,
            name=name,
            enabled=enabled,
            created_at=dt_util.utcnow(),
            now=dt_util.now(),
        )
        self._alarms.append(alarm_data)
        if alarm_number in self._free_alarm_numbers:
            self._free_alarm_numbers.remove(alarm_number)

        LOGGER.debug(
            "Recurring alarm %s added. Total alarms: %s. Scheduling save.",
            alarm_number,
            len(self._alarms),
        )
        self.hass.async_create_task(self._async_save_alarms_to_store())

        alarm_entity = AlarmEntity(
            self.hass,
            self._entry,
            alarm_number,
            alarm_data["next_run"] or dt_util.utcnow(),
            alarm_data,
        )
        if alarm_data["enabled"] and alarm_data["next_run"] is not None:
            self._async_schedule_alarm_event_trigger(
                alarm_number,
                alarm_data["next_run"],
            )
        return alarm_entity

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

    def _recalculate_alarm_next_run(
        self,
        alarm: dict[str, Any],
        *,
        skip_current: bool = False,
    ) -> None:
        """Recalculate the next run for a normalized alarm."""
        if not alarm["enabled"]:
            alarm["next_run"] = None
            return

        if alarm["type"] == ALARM_TYPE_RECURRING:
            alarm["next_run"] = calculate_next_recurring_run(
                alarm["time"],
                alarm["weekdays"],
                now=dt_util.now(),
                skip_current=skip_current,
            )
            return

        alarm["next_run"] = alarm["datetime_obj"]

    def _reschedule_alarm(self, alarm: dict[str, Any]) -> None:
        """Cancel and recreate the scheduled callback for an alarm."""
        alarm_number = alarm["number"]
        self._async_cancel_scheduled_alarm_trigger(alarm_number)
        if alarm["enabled"] and alarm["next_run"] is not None:
            self._async_schedule_alarm_event_trigger(alarm_number, alarm["next_run"])

    def _write_alarm_entity_state(self, alarm_number: int) -> None:
        """Refresh one alarm entity and the summary sensor."""
        entity = self._entry.runtime_data.alarm_entities.get(alarm_number)
        if entity:
            entity.async_write_ha_state()
        self.refresh_sensor()

    async def enable_alarm(self, alarm_number: int) -> bool:
        """Enable an alarm and schedule its next run."""
        alarm = self.get_alarm(alarm_number)
        if alarm is None:
            return False
        alarm["enabled"] = True
        self._recalculate_alarm_next_run(alarm)
        self._reschedule_alarm(alarm)
        await self._async_save_alarms_to_store()
        self._write_alarm_entity_state(alarm_number)
        return True

    async def disable_alarm(self, alarm_number: int) -> bool:
        """Disable an alarm and cancel its scheduled callback."""
        alarm = self.get_alarm(alarm_number)
        if alarm is None:
            return False
        alarm["enabled"] = False
        alarm["next_run"] = None
        self._async_cancel_scheduled_alarm_trigger(alarm_number)
        await self._async_save_alarms_to_store()
        self._write_alarm_entity_state(alarm_number)
        return True

    async def skip_next_alarm(self, alarm_number: int) -> bool:
        """Skip the next occurrence of a recurring alarm."""
        alarm = self.get_alarm(alarm_number)
        if alarm is None or alarm["type"] != ALARM_TYPE_RECURRING:
            return False
        alarm["skip_next"] = True
        self._recalculate_alarm_next_run(alarm, skip_current=True)
        alarm["skip_next"] = False
        self._reschedule_alarm(alarm)
        await self._async_save_alarms_to_store()
        self._write_alarm_entity_state(alarm_number)
        return True

    async def update_alarm(self, alarm_number: int, **changes: Any) -> bool:
        """Update an existing alarm and reschedule it."""
        alarm = self.get_alarm(alarm_number)
        if alarm is None:
            return False

        if ATTR_NAME in changes:
            alarm["name"] = changes[ATTR_NAME]
        if ATTR_ENABLED in changes:
            alarm["enabled"] = changes[ATTR_ENABLED]
        if ATTR_ALARM_TYPE in changes:
            alarm["type"] = changes[ATTR_ALARM_TYPE]
        if ATTR_ALARM_DATETIME in changes:
            alarm["datetime_obj"] = dt_util.as_utc(changes[ATTR_ALARM_DATETIME])
        if ATTR_TIME in changes:
            alarm["time"] = changes[ATTR_TIME]
        if ATTR_WEEKDAYS in changes:
            alarm["weekdays"] = list(changes[ATTR_WEEKDAYS])

        if alarm["type"] == ALARM_TYPE_ONE_TIME:
            alarm["time"] = None
            alarm["weekdays"] = []
        else:
            alarm["datetime_obj"] = None

        self._recalculate_alarm_next_run(alarm)
        self._reschedule_alarm(alarm)
        await self._async_save_alarms_to_store()
        self._write_alarm_entity_state(alarm_number)
        return True

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
        self.refresh_sensor()
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
            self.refresh_sensor()
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
        for alarm_num in list(self._entry.runtime_data.scheduled_alarm_triggers.keys()):
            self._async_cancel_scheduled_alarm_trigger(alarm_num)

    async def _async_save_alarms_to_store(self) -> None:
        """Save the current list of alarms to the store."""
        LOGGER.debug(
            "Saving %s alarms to store for %s", len(self._alarms), self._entry_id
        )
        data_to_save = [serialize_alarm(alarm) for alarm in self._alarms]
        await self._store.async_save(data_to_save)
