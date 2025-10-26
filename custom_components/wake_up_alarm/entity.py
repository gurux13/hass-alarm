"""AlarmEntity class."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity


class WakeUpAlarmEntity(Entity):
    """AlarmEntity class."""

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
