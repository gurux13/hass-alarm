"""Intent handler for deleting all alarms."""

from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.helpers import (
    config_validation as cv,
    intent,
)

from ..alarm_manager import AlarmManager
from ..const import HASS_DATA_ALARM_MANAGER


class DeleteAllAlarmsIntent(intent.IntentHandler):
    """Intent handler for deleting all alarms."""

    intent_type = "HassDeleteAllAlarms"
    description = "Deletes all alarms."

    slot_schema: ClassVar[dict[vol.Marker, Any]] = {}  # No slots needed for deleting all

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass

        alarm_manager: AlarmManager | None = hass.data.get(HASS_DATA_ALARM_MANAGER)

        if not alarm_manager:
            msg = "No alarm manager found. Please ensure the integration is set up correctly."
            raise intent.IntentError(msg)

        deleted_count = await alarm_manager.delete_all_alarms()

        response = intent_obj.create_response()
        if deleted_count > 0:
            response.async_set_speech(f"All {deleted_count} alarms have been deleted.")
        else:
            response.async_set_speech("There were no alarms to delete.")

        return response