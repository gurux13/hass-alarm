# Integration

This integration adds support for alarms in home assistant, with focus on voice assistants (it registers intents for alarm manipulation).

## Entities

The integration creates an entity per alarm, creatively named `Alarm <id>` with alarm IDs being reused when alarms are deleted / trigger.

There is also `next_alarm` entity that stores the next alarm timestamp (or is unavailable if there are no alarms).

`next_alarm` has extra state:
 - `alarms_count` is the number of alarms
 - `alarm_times` is an array of all alarm times (strings in ISO format).

## Services

The integration registers the following services:
 - `wake_up_alarm.add_alarm`: accepts a timestamp and creates a new alarm
 - `wake_up_alarm.delete_alarm`: accepts an alarm entity and deletes that alarm
 - `wake_up_alarm.delete_by_number`: accepts an alarm ID and deletes that alarm
 - `wake_up_alarm.delete_all_alarms`: deletes all alarms.

## Intents
The integration registers the following assist intents:
 - `set_alarm_intent`: Sets an alarm
 - `delete_alarm_intent`: Deletes an alarm by ID
 - `delete_all_alarms_intent`: Deletes all alarms
 - `get_alarms_intent`: Gets all alarms, with their IDs and times.