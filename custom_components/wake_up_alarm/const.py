"""Constants for wake_up_alarm."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "wake_up_alarm"
HOME_LLM_API_ID = "hass_alarm_llm"
SERVICE_TOOL_NAME = "HassAlarmTool"

# Signals
SIGNAL_ADD_ALARM = f"{DOMAIN}_add_alarm"
SIGNAL_DELETE_ALARM = f"{DOMAIN}_delete_alarm"

# Services
SERVICE_ADD_ALARM = "add_alarm"
SERVICE_DELETE_ALARM = "delete_alarm"
SERVICE_DELETE_ALARM_BY_NUMBER = "delete_alarm_by_number"
SERVICE_DELETE_ALL_ALARMS = "delete_all_alarms"
ATTR_ALARM_DATETIME = "datetime"
ATTR_ALARM_NUMBER = "alarm_number"  # Used in signal payload
EVENT_ALARM_TRIGGERED = f"{DOMAIN}_alarm_triggered"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY_ALARMS_FORMAT = (
    f"{DOMAIN}_alarms_{{entry_id}}"  # To be formatted with entry.entry_id
)

HASS_DATA_ALARM_MANAGER = f"{DOMAIN}_alarm_manager"
