# Integration

This integration adds support for alarms in home assistant, with focus on voice assistants (it registers intents for alarm manipulation).

## Entities

The integration creates an entity per alarm, creatively named `Alarm <id>` with alarm IDs being reused when alarms are deleted / trigger.

There is a `sensor.next_alarm` entity that stores the next alarm timestamp (or is unavailable if there are no alarms).

`next_alarm` has extra state:
 - `alarms_count` is the number of alarms
 - `alarm_times` is an array of all alarm times (strings in ISO format).

There is an entity called `sensor.is_alarming_now` that changes state between `NO` and `YES` momentarily when an alarm (any) is triggered.

## Events
The integration triggers an event `wake_up_alarm_alarm_triggered` when an alarm is triggered.
It passes the following information:

 - `alarm_number`: The integer alarm number
 - `alarm_datetime`: The (UTC) datetime when the alarm was set for

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

# Reacting to alarms
This integration does not do anything meaningful when an alarm is triggered, it acts as a means to trigger other things.

There are two ways the integration informs Home Assistant of an alarm: events (listen to `wake_up_alarm_alarm_triggered` event) and by changing the state of an entity (`sensor.is_alarming_now`).

Entity is provided as an easier trigger mechanic, and the event is more advanced and data-rich.

