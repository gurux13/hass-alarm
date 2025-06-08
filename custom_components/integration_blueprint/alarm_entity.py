from custom_components.integration_blueprint.entity import IntegrationBlueprintEntity
from homeassistant.helpers.device_registry import DeviceInfo
from datetime import date, datetime, timedelta


class AlarmEntity(IntegrationBlueprintEntity):
    """AlarmEntity class."""

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()

        self._attr_unique_id = self.entity_id
        self._attr_device_info = DeviceInfo(
            identifiers={(self.platform.domain, self.entity_id)},
            name="Integration Blueprint Alarm",
            manufacturer="Home Assistant",
            model="Alarm Model",
        )
        self._alarm_at = datetime.now()

    @property
    def state(self) -> str:
        return self._alarm_at.strftime("%Y-%m-%d %H:%M:%S")
