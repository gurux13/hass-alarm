"""Intent handler for deleting an alarm."""

from typing import TYPE_CHECKING, Any, ClassVar

import voluptuous as vol
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    intent,
)

from integration_blueprint.const import ATTR_ALARM_NUMBER, HASS_DATA_ALARM_MANAGER

if TYPE_CHECKING:
    from integration_blueprint.alarm_manager import AlarmManager


class DeleteAlarmIntent(intent.IntentHandler):
    """Intent handler for deleting an alarm."""

    intent_type = "HassDeleteAlarm"
    description = "Deletes an alarm by its number."

    slot_schema: ClassVar[dict[vol.Marker, Any]] = {
        vol.Required(ATTR_ALARM_NUMBER): cv.positive_int,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        if not slots:
            msg = "Invalid slots provided for DeleteAlarmIntent."
            raise intent.IntentError(msg)

        alarm_number = slots[ATTR_ALARM_NUMBER]["value"]

        alarm_manager: AlarmManager | None = hass.data.get(HASS_DATA_ALARM_MANAGER)

        if not alarm_manager:
            msg = (
                "No alarm manager found."
                "Please ensure the integration is set up correctly."
            )
            raise intent.IntentError(msg)
        alarm = alarm_manager.get_alarm(alarm_number)

        if not alarm:
            msg = f"No alarm found with number {alarm_number}."
            raise intent.IntentError(msg)
        success = await alarm_manager.delete_alarm(alarm_number)

        response = intent_obj.create_response()
        if success:
            response.async_set_speech(
                f"Alarm for {alarm['datetime_obj'].strftime('%Y-%m-%d %H:%M:%S')} "
                "has been deleted."
            )
        else:
            response.async_set_speech(
                f"I could not find an alarm with number {alarm_number}."
            )

        return response
