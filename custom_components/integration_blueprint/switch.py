"""Switch platform for integration_blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import IntegrationBlueprintEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import IntegrationBlueprintConfigEntry

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="alarms_enabled",
        name="Alarms enabled",
        icon="mdi:format-quote-close",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    async_add_entities(
        IntegrationBlueprintSwitch(
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationBlueprintSwitch(
    IntegrationBlueprintEntity, SwitchEntity, RestoreEntity
):
    """integration_blueprint switch class."""

    def __init__(
        self,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch class."""
        super().__init__()
        self.entity_description = entity_description
        self._state = True


    async def async_added_to_hass(self) -> None:
        state = await self.async_get_last_state()
        if state is not None and state.state in ("on", "off"):
            self._state = state.state == "on"
        else:
            self._state = True
        self.async_write_ha_state()
        await super().async_added_to_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._state = True
        self.hass.states.async_set(self.entity_id, "on")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._state = False
        self.hass.states.async_set(self.entity_id, "off")
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._state
