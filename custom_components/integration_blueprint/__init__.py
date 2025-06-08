"""
Custom integration to integrate integration_blueprint with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/integration_blueprint
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING, Final

import voluptuous as vol
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    intent,
    llm,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util.json import JsonObjectType
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    ATTR_ALARM_DATETIME,
    DOMAIN,
    LOGGER,
    SERVICE_ADD_ALARM,
    SIGNAL_ADD_ALARM,
)
from .data import IntegrationBlueprintData
from .set_alarm_intent import SetAlarmIntent

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationBlueprintConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationBlueprintConfigEntry,
) -> bool:
    """Set up this integration using UI."""

    entry.runtime_data = IntegrationBlueprintData(
        integration=async_get_loaded_integration(hass, entry.domain),
    )
    # if not any([x.id == HOME_LLM_API_ID for x in llm.async_get_apis(hass)]):
    #     llm.async_register_api(hass, HomeLLMAPI(hass))

    intent.async_register(hass, SetAlarmIntent())

    # Define the service handler for adding an alarm
    async def async_handle_add_alarm_service(service_call: ServiceCall) -> None:
        """Handle the service call to add a new alarm."""
        # cv.datetime ensures alarm_datetime_obj is a datetime object
        alarm_datetime_obj = service_call.data[ATTR_ALARM_DATETIME]

        LOGGER.info(
            "Service call to add alarm: DateTime='%s' for entry %s",
            alarm_datetime_obj.isoformat(),
            entry.entry_id,
        )

        alarm_details = {
            ATTR_ALARM_DATETIME: alarm_datetime_obj,
        }

        # Dispatch a signal specific to this config entry
        # The sensor platform for this entry will listen for this signal
        entry_specific_signal = f"{SIGNAL_ADD_ALARM}_{entry.entry_id}"
        async_dispatcher_send(hass, entry_specific_signal, alarm_details) # alarm_details now only contains datetime

    # Define the service schema
    ADD_ALARM_SERVICE_SCHEMA = vol.Schema(
        {
            vol.Required(ATTR_ALARM_DATETIME): cv.datetime,  # Validates and converts to datetime
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
    entry: IntegrationBlueprintConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: IntegrationBlueprintConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
