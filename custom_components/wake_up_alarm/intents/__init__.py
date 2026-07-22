"""Package with all intents of the integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    intent,
)

from .delete_alarm_intent import DeleteAlarmIntent
from .delete_all_alarms_intent import DeleteAllAlarmsIntent
from .get_alarms_intent import GetAlarmsIntent
from .set_alarm_intent import SetAlarmIntent


def register(hass: HomeAssistant) -> None:
    """Register intents for the wake up alarm integration."""
    intent.async_register(hass, SetAlarmIntent())
    intent.async_register(hass, GetAlarmsIntent())
    intent.async_register(hass, DeleteAllAlarmsIntent())
    intent.async_register(hass, DeleteAlarmIntent())


def unregister(hass: HomeAssistant) -> None:
    """Unregister intents for the wake up alarm integration."""
    intent.async_remove(hass, SetAlarmIntent.intent_type)
    intent.async_remove(hass, GetAlarmsIntent.intent_type)
    intent.async_remove(hass, DeleteAllAlarmsIntent.intent_type)
    intent.async_remove(hass, DeleteAlarmIntent.intent_type)
