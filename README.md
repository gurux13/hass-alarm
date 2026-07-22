# Integration

This integration adds support for alarms in Home Assistant, with focus on voice assistants (it registers intents for alarm manipulation).
It supports one-time datetime alarms and recurring weekly alarms.

## Entities

The integration creates an entity per alarm, creatively named `Alarm <id>` with alarm IDs being reused when alarms are deleted / trigger.

There is a `sensor.next_alarm` entity that stores the next enabled alarm timestamp (or is unavailable if there are no enabled alarms).

`next_alarm` has extra state:
 - `alarms_count` is the number of alarms
 - `enabled_alarms_count` is the number of enabled alarms
 - `alarm_times` is an array of enabled alarm next-run times (strings in ISO format)
 - `next_alarm_entity`, `next_alarm_name`, `next_alarm_type`, `next_alarm_time`, and `next_alarm_weekdays` describe the next enabled alarm.

There is an entity called `sensor.is_alarming_now` that changes state between `NO` and `YES` momentarily when an alarm (any) is triggered.

## Events
The integration triggers an event `wake_up_alarm_fired` when an alarm is triggered.
For compatibility, it also triggers `wake_up_alarm_alarm_triggered`.
It passes the following information:

 - `alarm_number`: The integer alarm number
 - `entity_id`: The alarm entity ID
 - `name`: The alarm name
 - `type`: `one_time` or `recurring`
 - `scheduled_time`: The datetime the alarm was scheduled for
 - `alarm_datetime`: The datetime the alarm was scheduled for

## Services

The integration registers the following services:
 - `wake_up_alarm.add_alarm`: accepts a timestamp and creates a one-time alarm
 - `wake_up_alarm.add_recurring_alarm`: accepts a time and weekdays, then creates a recurring alarm
 - `wake_up_alarm.update_alarm`: updates an existing alarm
 - `wake_up_alarm.enable_alarm`: enables an alarm and schedules its next run
 - `wake_up_alarm.disable_alarm`: disables an alarm and cancels its scheduled callback
 - `wake_up_alarm.skip_next_alarm`: skips the next occurrence of a recurring alarm
 - `wake_up_alarm.delete_alarm`: accepts an alarm entity and deletes that alarm
 - `wake_up_alarm.delete_by_number`: accepts an alarm ID and deletes that alarm
 - `wake_up_alarm.delete_all_alarms`: deletes all alarms.

Example one-time alarm:

```yaml
action: wake_up_alarm.add_alarm
data:
  name: Dentist
  datetime: "2026-05-22 08:30:00"
```

Example recurring weekday alarm:

```yaml
action: wake_up_alarm.add_recurring_alarm
data:
  name: Work alarm
  time: "07:00:00"
  weekdays:
    - mon
    - tue
    - wed
    - thu
    - fri
```

Example automation:

```yaml
trigger:
  - platform: event
    event_type: wake_up_alarm_fired
action:
  - action: notify.notify
    data:
      message: "Alarm {{ trigger.event.data.name }} fired"
```

## Intents
The integration registers the following assist intents:
 - `set_alarm_intent`: Sets an alarm
 - `delete_alarm_intent`: Deletes an alarm by ID
 - `delete_all_alarms_intent`: Deletes all alarms
 - `get_alarms_intent`: Gets all alarms, with their IDs and times.

# Reacting to alarms
This integration does not do anything meaningful when an alarm is triggered, it acts as a means to trigger other things.

There are two ways the integration informs Home Assistant of an alarm: events (listen to `wake_up_alarm_fired`) and by changing the state of an entity (`sensor.is_alarming_now`).

Entity is provided as an easier trigger mechanic, and the event is more advanced and data-rich.

