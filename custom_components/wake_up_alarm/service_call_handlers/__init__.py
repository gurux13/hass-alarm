"""Service call handlers for the wake up alarm component."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry import WakeUpAlarmConfigEntry

from custom_components.wake_up_alarm.const import DOMAIN
from custom_components.wake_up_alarm.service_call_handlers._handler_base import (
    EntryHandlerBase,
    HandlerBase,
)

from ._handlers import (
    AddAlarmHandler,
    AddRecurringAlarmHandler,
    DeleteAlarmByNumberHandler,
    DeleteAlarmHandler,
    DeleteAllAlarmsHandler,
    DisableAlarmHandler,
    EnableAlarmHandler,
    SkipNextAlarmHandler,
    UpdateAlarmHandler,
)

ENTRY_HANDLERS: list[type[EntryHandlerBase]] = [
    DisableAlarmHandler,
    AddAlarmHandler,
    EnableAlarmHandler,
    UpdateAlarmHandler,
    SkipNextAlarmHandler,
    AddRecurringAlarmHandler,
]

HANDLERS: list[type[HandlerBase]] = [
    DeleteAllAlarmsHandler,
    DeleteAlarmHandler,
    DeleteAlarmByNumberHandler,
]


def register_entry(hass: HomeAssistant, entry: WakeUpAlarmConfigEntry) -> None:
    """Register the service call entry related handlers."""
    for handler in ENTRY_HANDLERS:
        instance = handler(hass, entry)
        hass.services.register(
            DOMAIN,
            handler.SERVICE_NAME,
            instance.async_handle_service_call,
            handler.SCHEMA,
        )


def register(hass: HomeAssistant) -> None:
    """Register the service call handlers for the wake up alarm component."""
    for handler in HANDLERS:
        instance = handler(hass)
        hass.services.register(
            DOMAIN,
            handler.SERVICE_NAME,
            instance.async_handle_service_call,
            handler.SCHEMA,
        )


def unregister(hass: HomeAssistant) -> None:
    """Unregister the service call handlers for the wake up alarm component."""
    for handler in ENTRY_HANDLERS:
        hass.services.remove(
            DOMAIN,
            handler.SERVICE_NAME,
        )
