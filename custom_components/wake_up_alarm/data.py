"""Custom types for wake_up_alarm."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .alarm_entity import AlarmEntity


type WakeUpAlarmConfigEntry = ConfigEntry[WakeUpAlarmData]


@dataclass
class WakeUpAlarmData:
    """Data for the WakeUp Alarm integration."""

    integration: Integration
    alarm_entities: dict[int, AlarmEntity] = field(default_factory=dict)
    scheduled_alarm_triggers: dict[int, Callable[[], None]] = field(
        default_factory=dict
    )
