from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from custom_components.wake_up_alarm.alarm_manager import AlarmManager
from custom_components.wake_up_alarm.alarm_model import ALARM_TYPE_ONE_TIME, WEEKDAYS
from custom_components.wake_up_alarm.const import (
    SERVICE_ADD_ALARM,
    SERVICE_ADD_RECURRING_ALARM,
    SERVICE_DELETE_ALARM,
    SERVICE_DELETE_ALARM_BY_NUMBER,
    SERVICE_DELETE_ALL_ALARMS,
    SERVICE_DISABLE_ALARM,
    SERVICE_ENABLE_ALARM,
    SERVICE_SKIP_NEXT_ALARM,
    SERVICE_UPDATE_ALARM,
    SIGNAL_DELETE_ALARM,
)

from .alarm_model import ALARM_TYPE_RECURRING
from .const import (
    ATTR_ALARM_DATETIME,
    ATTR_ALARM_NUMBER,
    ATTR_ALARM_TYPE,
    ATTR_ENABLED,
    ATTR_NAME,
    ATTR_TIME,
    ATTR_WEEKDAYS,
    DOMAIN,
    LOGGER,
    SIGNAL_ADD_ALARM,
)

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

from ._handler_base import EntryHandlerBase, HandlerBase


class AddAlarmHandler(EntryHandlerBase):
    """Handler for the add alarm service call."""

    SERVICE_NAME = SERVICE_ADD_ALARM
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_TIME): cv.string,
            vol.Required(ATTR_WEEKDAYS): vol.All(
                cv.ensure_list,
                [vol.In(WEEKDAYS)],
            ),
            vol.Optional(ATTR_NAME): cv.string,
            vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to add a new alarm."""
        # cv.datetime ensures alarm_datetime_obj is a datetime object
        local_alarm_datetime_obj = service_call.data[ATTR_ALARM_DATETIME]
        utc_alarm_datetime_obj = dt_util.as_utc(local_alarm_datetime_obj)

        LOGGER.info(
            "Service call to add alarm: DateTime='%s' (UTC %s) for entry %s",
            local_alarm_datetime_obj.isoformat(),
            utc_alarm_datetime_obj.isoformat(),
            self.entry.entry_id,
        )

        alarm_details = {
            ATTR_ALARM_DATETIME: utc_alarm_datetime_obj,
            ATTR_NAME: service_call.data.get(ATTR_NAME),
            ATTR_ENABLED: service_call.data[ATTR_ENABLED],
        }

        # Dispatch a signal specific to this config entry
        # The sensor platform for this entry will listen for this signal
        entry_specific_signal = f"{SIGNAL_ADD_ALARM}_{self.entry.entry_id}"
        async_dispatcher_send(self.hass, entry_specific_signal, alarm_details)


class AddRecurringAlarmHandler(EntryHandlerBase):
    """Handler for the add recurring alarm service call."""

    SERVICE_NAME = SERVICE_ADD_RECURRING_ALARM
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ALARM_DATETIME): cv.datetime,
            vol.Optional(ATTR_NAME): cv.string,
            vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to add a new recurring alarm."""
        alarm_details = {
            ATTR_ALARM_TYPE: ALARM_TYPE_RECURRING,
            ATTR_TIME: service_call.data[ATTR_TIME],
            ATTR_WEEKDAYS: service_call.data[ATTR_WEEKDAYS],
            ATTR_NAME: service_call.data.get(ATTR_NAME),
            ATTR_ENABLED: service_call.data[ATTR_ENABLED],
        }

        entry_specific_signal = f"{SIGNAL_ADD_ALARM}_{self.entry.entry_id}"
        async_dispatcher_send(self.hass, entry_specific_signal, alarm_details)


class UpdateAlarmHandler(EntryHandlerBase):
    """Handler for the update alarm service call."""

    SERVICE_NAME = SERVICE_UPDATE_ALARM
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ALARM_NUMBER): cv.positive_int,
            vol.Optional(ATTR_NAME): cv.string,
            vol.Optional(ATTR_ENABLED): cv.boolean,
            vol.Optional(ATTR_ALARM_DATETIME): cv.datetime,
            vol.Optional(ATTR_TIME): cv.string,
            vol.Optional(ATTR_WEEKDAYS): vol.All(
                cv.ensure_list,
                [vol.In(WEEKDAYS)],
            ),
            vol.Optional(ATTR_ALARM_TYPE): vol.In(
                [ALARM_TYPE_ONE_TIME, ALARM_TYPE_RECURRING],
            ),
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to update an existing alarm."""
        am = AlarmManager.get_instance(self.hass)
        if not am:
            LOGGER.warning("Cannot update alarm: No instance of %s found.", DOMAIN)
            return
        alarm_number = service_call.data[ATTR_ALARM_NUMBER]
        changes = dict(service_call.data)
        del changes[ATTR_ALARM_NUMBER]
        await am.update_alarm(alarm_number, **changes)


class EnableAlarmHandler(EntryHandlerBase):
    """Handler for the enable alarm service call."""

    SERVICE_NAME = SERVICE_ENABLE_ALARM
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ALARM_NUMBER): cv.positive_int,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to enable an alarm."""
        am = AlarmManager.get_instance(self.hass)
        if not am:
            LOGGER.warning("Cannot enable alarm: No instance of %s found.", DOMAIN)
            return
        await am.enable_alarm(service_call.data[ATTR_ALARM_NUMBER])


class DisableAlarmHandler(EntryHandlerBase):
    """Handler for the disable alarm service call."""

    SERVICE_NAME = SERVICE_DISABLE_ALARM
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ALARM_NUMBER): cv.positive_int,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to disable an alarm."""
        am = AlarmManager.get_instance(self.hass)
        if not am:
            LOGGER.warning("Cannot disable alarm: No instance of %s found.", DOMAIN)
            return
        await am.disable_alarm(service_call.data[ATTR_ALARM_NUMBER])


class SkipNextAlarmHandler(EntryHandlerBase):
    """Handler for the skip next alarm service call."""

    SERVICE_NAME = SERVICE_SKIP_NEXT_ALARM
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ALARM_NUMBER): cv.positive_int,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to skip the next alarm occurrence."""
        am = AlarmManager.get_instance(self.hass)
        if not am:
            LOGGER.warning("Cannot skip alarm: No instance of %s found.", DOMAIN)
            return
        await am.skip_next_alarm(service_call.data[ATTR_ALARM_NUMBER])


class DeleteAllAlarmsHandler(HandlerBase):
    """Handler for the delete all alarms service call."""

    SERVICE_NAME = SERVICE_DELETE_ALL_ALARMS
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to delete all alarms across all instances."""
        del service_call  # Unused
        am = AlarmManager.get_instance(self.hass)
        if not am:
            LOGGER.warning("Cannot delete all alarms: No instance of %s found.", DOMAIN)
            return
        await am.delete_all_alarms()


class DeleteAlarmHandler(HandlerBase):
    """Handler for the delete alarm service call."""

    SERVICE_NAME = SERVICE_DELETE_ALARM
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to delete an alarm."""
        entity_registry = er.async_get(self.hass)
        target_entity_ids = service_call.data[ATTR_ENTITY_ID]

        for entity_id_str in target_entity_ids:
            entity_entry = entity_registry.async_get(entity_id_str)

            if not entity_entry:
                LOGGER.warning(
                    "Cannot delete alarm: Entity ID %s not found.", entity_id_str
                )
                continue

            if entity_entry.platform != DOMAIN:
                LOGGER.warning(
                    "Cannot delete alarm: Entity %s is not part of the %s domain.",
                    entity_id_str,
                    DOMAIN,
                )
                continue

            if not entity_entry.config_entry_id:
                LOGGER.warning(
                    "Cannot delete alarm: Entity %s is not associated with a config.",
                    entity_id_str,
                )
                continue

            config_entry_id = entity_entry.config_entry_id
            # Unique ID format: f"{config_entry_id}_alarm_{alarm_number}"
            prefix = f"{config_entry_id}_alarm_"
            if entity_entry.unique_id and entity_entry.unique_id.startswith(prefix):
                try:
                    alarm_number_str = entity_entry.unique_id[len(prefix) :]
                    alarm_number = int(alarm_number_str)
                    am = AlarmManager.get_instance(self.hass)
                    if am:
                        await am.delete_alarm(alarm_number)
                except ValueError:
                    LOGGER.warning(
                        "Could not parse alarm_number from unique_id %s for entity %s",
                        entity_entry.unique_id,
                        entity_id_str,
                    )
            else:
                LOGGER.warning(
                    "Unique ID %s for entity %s does not match expected alarm format.",
                    entity_entry.unique_id,
                    entity_id_str,
                )


class DeleteAlarmByNumberHandler(HandlerBase):
    """Handler for the delete alarm by number service call."""

    SERVICE_NAME = SERVICE_DELETE_ALARM_BY_NUMBER
    SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ALARM_NUMBER): cv.positive_int,
        }
    )

    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call to delete an alarm by its number."""
        alarm_number_to_delete = service_call.data[ATTR_ALARM_NUMBER]

        config_entries_for_domain = self.hass.config_entries.async_entries(DOMAIN)

        if not config_entries_for_domain:
            LOGGER.warning(
                "Cannot delete alarm by number %s: No config entries found for %s.",
                alarm_number_to_delete,
                DOMAIN,
            )
            return

        dispatched_count = 0
        for config_entry in config_entries_for_domain:
            config_entry_id = config_entry.entry_id
            alarm_details = {ATTR_ALARM_NUMBER: alarm_number_to_delete}
            delete_signal = f"{SIGNAL_DELETE_ALARM}_{config_entry_id}"

            LOGGER.debug(
                "Dispatching delete signal %s for alarm number %s (config_entry: %s)",
                delete_signal,
                alarm_number_to_delete,
                config_entry_id,
            )
            async_dispatcher_send(self.hass, delete_signal, alarm_details)
            dispatched_count += 1

        if dispatched_count > 0:
            LOGGER.info(
                "Delete signal for alarm number %s dispatched to %s instance(s) of %s.",
                alarm_number_to_delete,
                dispatched_count,
                DOMAIN,
            )
        # If no instances had the alarm, the sensor platform's handler will silently
        # ignore it or log appropriately.
