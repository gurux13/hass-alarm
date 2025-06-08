"""
Custom integration to integrate integration_blueprint with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/integration_blueprint
"""

from __future__ import annotations
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    intent,
)
from .set_alarm_intent import SetAlarmIntent
from datetime import timedelta
from typing import TYPE_CHECKING, Final
import voluptuous as vol
from homeassistant.util.json import JsonObjectType


from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN, LOGGER, HOME_LLM_API_ID, SERVICE_TOOL_NAME
from .coordinator import BlueprintDataUpdateCoordinator
from .data import IntegrationBlueprintData

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
    coordinator = BlueprintDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(hours=1),
    )
    entry.runtime_data = IntegrationBlueprintData(
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # if not any([x.id == HOME_LLM_API_ID for x in llm.async_get_apis(hass)]):
    #     llm.async_register_api(hass, HomeLLMAPI(hass))

    intent.async_register(hass, SetAlarmIntent())

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

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


class SetAlarmIntent(intent.IntentHandler):
    """Intent handler for starting a new timer."""

    intent_type = "HassSetAlarm"
    description = "Sets an alarm"
    slot_schema = {
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Optional("name"): cv.string,
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


# class HassServiceTool(llm.Tool):
#     """Tool to get the current time."""

#     name: Final[str] = SERVICE_TOOL_NAME
#     description: Final[str] = "Sets an alarm time"

#     # Optional. A voluptuous schema of the input parameters.
#     parameters = vol.Schema(
#         {
#             vol.Required("time"): str,
#         }
#     )

#     async def async_call(
#         self,
#         hass: HomeAssistant,
#         tool_input: llm.ToolInput,
#         llm_context: llm.LLMContext,
#     ) -> JsonObjectType:
#         """Call the tool."""
#         import pdb

#         pdb.set_trace()
#         # service_data = {ATTR_ENTITY_ID: target_device}
#         # for attr in ALLOWED_SERVICE_CALL_ARGUMENTS:
#         #     if attr in tool_input.tool_args.keys():
#         #         service_data[attr] = tool_input.tool_args[attr]
#         # try:
#         #     await hass.services.async_call(
#         #         domain,
#         #         service,
#         #         service_data=service_data,
#         #         blocking=True,
#         #     )
#         # except Exception:
#         #     _LOGGER.exception("Failed to execute service for model")
#         #     return {"result": "failed"}

#         return {"result": "success"}


# class HomeLLMAPI(llm.API):
#     """
#     An API that allows calling Home Assistant services to maintain compatibility
#     with the older (v3 and older) Home LLM models
#     """

#     def __init__(self, hass: HomeAssistant) -> None:
#         """Init the class."""
#         super().__init__(
#             hass=hass,
#             id=HOME_LLM_API_ID,
#             name="Home-LLM (v1-v3)",
#         )

#     async def async_get_api_instance(
#         self, llm_context: llm.LLMContext
#     ) -> llm.APIInstance:
#         """Return the instance of the API."""
#         return llm.APIInstance(
#             api=self,
#             api_prompt="Call services in Home Assistant by passing the service name and the device to control.",
#             llm_context=llm_context,
#             tools=[HassServiceTool()],
#         )
