"""Constants for integration_blueprint."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "integration_blueprint"
ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"
HOME_LLM_API_ID = "hass_alarm_llm"
SERVICE_TOOL_NAME = "HassAlarmTool"

# Signals
SIGNAL_ADD_ALARM = f"{DOMAIN}_add_alarm"

# Services
SERVICE_ADD_ALARM = "add_alarm"
ATTR_ALARM_NAME = "name"
ATTR_ALARM_DATETIME = "datetime"
