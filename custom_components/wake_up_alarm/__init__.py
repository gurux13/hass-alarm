"""
Custom integration to integrate wake_up_alarm with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/wake_up_alarm
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    intent,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util import dt as dt_util

from custom_components.wake_up_alarm.alarm_manager import AlarmManager

from .const import (
    ATTR_ALARM_DATETIME,
    ATTR_ALARM_NUMBER,
    DOMAIN,
    LOGGER,
    SERVICE_ADD_ALARM,
    SERVICE_DELETE_ALARM,
    SERVICE_DELETE_ALARM_BY_NUMBER,
    SIGNAL_ADD_ALARM,
    SIGNAL_DELETE_ALARM,
)
from .data import WakeUpAlarmData
from .intents.delete_all_alarms_intent import DeleteAllAlarmsIntent
from .intents.delete_alarm_intent import DeleteAlarmIntent
from .intents.get_alarms_intent import GetAlarmsIntent
from .intents.set_alarm_intent import SetAlarmIntent

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

    from .data import WakeUpAlarmConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
]

DELETE_ALARM_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

DELETE_ALARM_BY_NUMBER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ALARM_NUMBER): cv.positive_int,
        # ATTR_DEVICE_ID is removed as per the requirement
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the wake_up_alarm domain."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    async def async_handle_delete_alarm_service(service_call: ServiceCall) -> None:
        """Handle the service call to delete an alarm."""
        entity_registry = er.async_get(hass)
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
                    "Cannot delete alarm: Entity %s is not associated with a config entry.",
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
                    alarm_details = {ATTR_ALARM_NUMBER: alarm_number}
                    delete_signal = f"{SIGNAL_DELETE_ALARM}_{config_entry_id}"
                    await AlarmManager.execute_on_instance_async(
                        hass,
                        lambda am: (
                            await am.delete_alarm(alarm_number) for _ in "_"
                        ).__anext__(),
                    )
                    async_dispatcher_send(hass, delete_signal, alarm_details)
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

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_ALARM,
        async_handle_delete_alarm_service,
        schema=DELETE_ALARM_SERVICE_SCHEMA,
    )

    async def async_handle_delete_alarm_by_number_service(
        service_call: ServiceCall,
    ) -> None:
        """Handle the service call to delete an alarm by its number across all instances."""
        alarm_number_to_delete = service_call.data[ATTR_ALARM_NUMBER]

        config_entries_for_domain = hass.config_entries.async_entries(DOMAIN)

        if not config_entries_for_domain:
            LOGGER.warning(
                "Cannot delete alarm by number %s: No config entries found for the %s domain.",
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
            async_dispatcher_send(hass, delete_signal, alarm_details)
            dispatched_count += 1

        if dispatched_count > 0:
            LOGGER.info(
                "Delete signal for alarm number %s dispatched to %s instance(s) of %s.",
                alarm_number_to_delete,
                dispatched_count,
                DOMAIN,
            )
        # If no instances had the alarm, the sensor platform's handler will silently ignore it or log appropriately.

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_ALARM_BY_NUMBER,
        async_handle_delete_alarm_by_number_service,
        schema=DELETE_ALARM_BY_NUMBER_SERVICE_SCHEMA,
    )

    return True


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
) -> bool:
    """Set up this integration using UI."""

    entry.runtime_data = WakeUpAlarmData(
        integration=async_get_loaded_integration(hass, entry.domain),
        alarm_entities={},  # Initialize alarm_entities dict
    )

    intent.async_register(hass, SetAlarmIntent())
    intent.async_register(hass, GetAlarmsIntent())
    intent.async_register(hass, DeleteAllAlarmsIntent())
    intent.async_register(hass, DeleteAlarmIntent())

    # Define the service handler for adding an alarm
    async def async_handle_add_alarm_service(service_call: ServiceCall) -> None:
        """Handle the service call to add a new alarm."""
        # cv.datetime ensures alarm_datetime_obj is a datetime object
        local_alarm_datetime_obj = service_call.data[ATTR_ALARM_DATETIME]
        utc_alarm_datetime_obj = dt_util.as_utc(local_alarm_datetime_obj)

        LOGGER.info(
            "Service call to add alarm: DateTime='%s' (UTC %s) for entry %s",
            local_alarm_datetime_obj.isoformat(),
            utc_alarm_datetime_obj.isoformat(),
            entry.entry_id,
        )

        alarm_details = {
            ATTR_ALARM_DATETIME: utc_alarm_datetime_obj,
        }

        # Dispatch a signal specific to this config entry
        # The sensor platform for this entry will listen for this signal
        entry_specific_signal = f"{SIGNAL_ADD_ALARM}_{entry.entry_id}"  # alarm_details now only contains datetime
        async_dispatcher_send(
            hass, entry_specific_signal, alarm_details
        )  # alarm_details now only contains datetime

    # Define the service schema
    ADD_ALARM_SERVICE_SCHEMA = vol.Schema(
        {
            vol.Required(
                ATTR_ALARM_DATETIME
            ): cv.datetime,  # Validates and converts to datetime
        }
    )

    # Register the service
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ALARM,
        async_handle_add_alarm_service,
        schema=ADD_ALARM_SERVICE_SCHEMA,
    )

    # Ensure service is removed on unload
    def _unregister_service():
        hass.services.async_remove(DOMAIN, SERVICE_ADD_ALARM)

    entry.async_on_unload(_unregister_service)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
