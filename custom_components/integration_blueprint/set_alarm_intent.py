"""Intent handler for setting an alarm."""

import datetime
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    intent,
)

from .const import ATTR_ALARM_DATETIME, DOMAIN, SERVICE_ADD_ALARM


class SetAlarmIntent(intent.IntentHandler):
    """Intent handler for starting a new timer."""

    intent_type = "HassSetAlarm"
    description = (
        "Sets an alarm. Try to guess the date if not provided. "
        "Make sure the alarm time is in the future. "
        "Reply to the user with the time and date set in a human-understandable way."
    )

    slot_schema: ClassVar[dict[vol.Marker, Any]] = {
        vol.Required("year"): cv.positive_int,
        vol.Required("month"): cv.positive_int,
        vol.Required("day"): cv.positive_int,
        vol.Required("hour"): cv.positive_int,
        vol.Required("minute"): cv.positive_int,
        vol.Required("seconds"): cv.positive_int,
    }

    def get_local_tz(self) -> datetime.tzinfo:
        """Get the local timezone."""
        return datetime.datetime.now(datetime.UTC).astimezone().tzinfo or datetime.UTC

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        if not slots:
            msg = "Invalid slots provided for SetAlarmIntent."
            raise intent.IntentError(msg)
        time_for_alarm = datetime.datetime(
            year=slots["year"]["value"],
            month=slots["month"]["value"],
            day=slots["day"]["value"],
            hour=slots["hour"]["value"],
            minute=slots["minute"]["value"],
            second=slots.get("seconds", {}).get("value", 0),
            tzinfo=self.get_local_tz(),
        )
        if time_for_alarm.astimezone(datetime.UTC) <= datetime.datetime.now(
            datetime.UTC
        ):
            msg = "Alarm time must be in the future."
            raise intent.IntentError(msg)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_ALARM,
            {
                ATTR_ALARM_DATETIME: time_for_alarm.isoformat(),
            },
            blocking=True,  # Wait for the service call to complete
        )

        response = intent_obj.create_response()
        response.async_set_speech(
            f"Alarm set for {time_for_alarm.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return response
