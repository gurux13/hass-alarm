from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    intent,
)
import voluptuous as vol


class SetAlarmIntent(intent.IntentHandler):
    """Intent handler for starting a new timer."""

    intent_type = "HassSetAlarm"
    description = "Sets an alarm"
    slot_schema = {
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Optional("conversation_command"): cv.string,
    }  # type: ignore

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""

        import pdb

        pdb.set_trace()
        # hass = intent_obj.hass
        # timer_manager: TimerManager = hass.data[TIMER_DATA]
        # slots = self.async_validate_slots(intent_obj.slots)

        # conversation_command: str | None = None
        # if "conversation_command" in slots:
        #     conversation_command = slots["conversation_command"]["value"].strip()

        # if (not conversation_command) and (
        #     not (
        #         intent_obj.device_id
        #         and timer_manager.is_timer_device(intent_obj.device_id)
        #     )
        # ):
        #     # Fail early if this is not a delayed command
        #     raise TimersNotSupportedError(intent_obj.device_id)

        # name: str | None = None
        # if "name" in slots:
        #     name = slots["name"]["value"]

        # hours: int | None = None
        # if "hours" in slots:
        #     hours = int(slots["hours"]["value"])

        # minutes: int | None = None
        # if "minutes" in slots:
        #     minutes = int(slots["minutes"]["value"])

        # seconds: int | None = None
        # if "seconds" in slots:
        #     seconds = int(slots["seconds"]["value"])

        # timer_manager.start_timer(
        #     intent_obj.device_id,
        #     hours,
        #     minutes,
        #     seconds,
        #     language=intent_obj.language,
        #     name=name,
        #     conversation_command=conversation_command,
        #     conversation_agent_id=intent_obj.conversation_agent_id,
        # )

        return intent_obj.create_response()
