"""Intent handler for setting an alarm."""

from typing import TYPE_CHECKING, ClassVar

from homeassistant.helpers import (
    intent,
)
from homeassistant.util import dt as dt_util

from .const import HASS_DATA_ALARM_MANAGER

if TYPE_CHECKING:
    from .alarm_manager import AlarmManager


class GetAlarmsIntent(intent.IntentHandler):
    """Intent handler for getting a list of alarms."""

    intent_type = "HassGetAlarms"
    description = "Gets a list of all active alarms."

    # No slots required for getting all alarms
    slot_schema: ClassVar[dict] = {}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        response = intent_obj.create_response()

        # Assuming there's only one instance of the integration/config entry
        # If multiple, we might need to iterate or specify which entry.
        # For simplicity, let's get the first/only manager instance.
        alarm_manager: AlarmManager | None = hass.data.get(HASS_DATA_ALARM_MANAGER)

        if not alarm_manager:
            msg = "No alarm manager found. Please ensure the integration is set up correctly."
            raise intent.IntentError(msg)
        alarms = alarm_manager.get_all_alarms_data()

        if not alarms:
            response.async_set_speech("You have no active alarms.")
        else:
            # Format the alarm times for speech
            alarm_list_str = ", ".join(
                [
                    f"Alarm {a['number']} at {dt_util.as_local(a['datetime_obj']).strftime('%Y-%m-%d %H:%M:%S')}"
                    for a in sorted(alarms, key=lambda x: x["datetime_obj"])
                ]
            )
            response.async_set_speech(
                f"You have {len(alarms)} active alarms: {alarm_list_str}."
            )

        return response
