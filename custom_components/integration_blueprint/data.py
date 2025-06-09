"""Custom types for integration_blueprint."""

from __future__ import annotations
from dataclasses import dataclass, field

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .alarm_entity import AlarmEntity
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration


type IntegrationBlueprintConfigEntry = ConfigEntry[IntegrationBlueprintData]


@dataclass
class IntegrationBlueprintData:
    """Data for the Blueprint integration."""

    integration: Integration
    alarm_entities: dict[int, AlarmEntity] = field(default_factory=dict)
    scheduled_alarm_triggers: dict[int, Callable[[], None]] = field(
        default_factory=dict
    )
