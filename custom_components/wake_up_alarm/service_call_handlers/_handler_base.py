"""Base class for all service call handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import voluptuous as vol
    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import WakeUpAlarmConfigEntry


class HandlerBase(ABC):
    """Base class for all service call handlers."""

    SERVICE_NAME: str = ""
    SCHEMA: vol.Schema

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the handler base."""
        self.hass: HomeAssistant = hass

    @abstractmethod
    async def async_handle_service_call(self, service_call: ServiceCall) -> None:
        """Handle the service call."""
        raise NotImplementedError


class EntryHandlerBase(HandlerBase):
    """Base class for all entry related service call handlers."""

    def __init__(self, hass: HomeAssistant, entry: WakeUpAlarmConfigEntry) -> None:
        """Initialize the entry handler base."""
        super().__init__(hass)
        self.entry: WakeUpAlarmConfigEntry = entry
