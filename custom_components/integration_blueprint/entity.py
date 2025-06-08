"""BlueprintEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import Entity

from .const import ATTRIBUTION


class IntegrationBlueprintEntity(Entity):
    """BlueprintEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
