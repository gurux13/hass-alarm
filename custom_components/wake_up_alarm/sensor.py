"""Sensor platform for wake_up_alarm."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .alarm_manager import (
    async_remove_entry as am_async_remove_entry,
)
from .alarm_manager import (
    async_setup_entry as am_async_setup_entry,
)
from .const import (
    LOGGER,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import WakeUpAlarmConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform for wake_up_alarm."""
    await am_async_setup_entry(hass, entry, async_add_entities)


async def async_remove_entry(
    hass: HomeAssistant,
    entry: WakeUpAlarmConfigEntry,
) -> bool:
    """Handle removal of the entry."""
    LOGGER.debug("Removing entry for %s", entry.entry_id)

    await am_async_remove_entry(hass, entry)
    return True
