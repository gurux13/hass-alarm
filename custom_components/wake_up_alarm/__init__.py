"""
Custom integration to integrate wake_up_alarm with Home Assistant.

For more details about this integration, please refer to
https://github.com/gurux13/wake_up_alarm
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import intents
import service_call_handlers
from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .alarm_manager import async_remove_entry as am_async_remove_entry
from .const import (
    DOMAIN,
    LOGGER,
)
from .data import WakeUpAlarmData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .data import WakeUpAlarmConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the wake_up_alarm domain."""
    del config  # Unused
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    service_call_handlers.register(hass)

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
    intents.register(hass)

    service_call_handlers.register_entry(hass, entry)

    entry.async_on_unload(service_call_handlers.unregister(hass))

    intents.unregister(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    LOGGER.debug("init: Unloading entry for %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_remove_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
) -> bool:
    """Handle removal of the entry."""
    LOGGER.debug("Removing entry for %s", entry.entry_id)

    await am_async_remove_entry(hass, entry)
    return True
