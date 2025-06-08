"""Alarm Manager for integration_blueprint."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    LOGGER,
    STORAGE_KEY_ALARMS_FORMAT,
    STORAGE_VERSION,
)


class AlarmManager:
    """Manages loading, saving, and accessing alarm data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the Alarm Manager."""
        self.hass = hass
        self._entry_id = entry_id
        # _alarms stores {"number": int, "datetime_obj": datetime}
        self._alarms: list[dict[str, Any]] = []

        storage_key = STORAGE_KEY_ALARMS_FORMAT.format(entry_id=self._entry_id)
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, storage_key
        )

    async def async_load_alarms(self) -> None:
        """Load alarms from the store."""
        if not (stored_alarms_raw := await self._store.async_load()):
            LOGGER.debug("No persisted alarms found for %s", self._entry_id)
            return

        loaded_alarms: list[dict[str, Any]] = []
        for alarm_raw in stored_alarms_raw:
            try:
                if not all(k in alarm_raw for k in ("number", "datetime")):
                    LOGGER.warning("Skipping malformed alarm data: %s", alarm_raw)
                    continue
                if not isinstance(alarm_raw["number"], int) or not isinstance(
                    alarm_raw["datetime"], str
                ):
                    LOGGER.warning(
                        "Skipping alarm data with incorrect types: %s", alarm_raw
                    )
                    continue

                parsed_datetime = dt_util.parse_datetime(alarm_raw["datetime"])
                if parsed_datetime is None:
                    LOGGER.warning(
                        "Could not parse datetime string for alarm: %s", alarm_raw
                    )
                    continue

                loaded_alarms.append(
                    {"number": alarm_raw["number"], "datetime_obj": parsed_datetime}
                )
            except (TypeError, ValueError) as ex:
                LOGGER.warning("Could not parse stored alarm %s: %s", alarm_raw, ex)

        self._alarms = sorted(loaded_alarms, key=lambda x: x["number"])
        LOGGER.debug(
            "Loaded %s alarms for %s from store", len(self._alarms), self._entry_id
        )

    def get_all_alarms_data(self) -> list[dict[str, Any]]:
        """Return a copy of all current alarm data (number, datetime_obj)."""
        return list(self._alarms)  # Return a copy

    def get_next_alarm_number(self) -> int:
        """Determine the next available alarm number."""
        if not self._alarms:
            return 1
        return max(alarm["number"] for alarm in self._alarms) + 1

    @callback
    def add_alarm(self, alarm_number: int, alarm_datetime: datetime) -> None:
        """Add an alarm, update internal list, and schedule save."""
        if any(alarm["number"] == alarm_number for alarm in self._alarms):
            LOGGER.warning(
                "Attempted to add alarm with duplicate number %s. Skipping.",
                alarm_number,
            )
            return

        self._alarms.append({"number": alarm_number, "datetime_obj": alarm_datetime})
        self._alarms.sort(key=lambda x: x["number"])  # Keep sorted by number
        LOGGER.debug(
            "Alarm %s added to manager. Total alarms: %s. Scheduling save.",
            alarm_number,
            len(self._alarms),
        )
        self.hass.async_create_task(self._async_save_alarms_to_store())

    async def _async_save_alarms_to_store(self) -> None:
        """Save the current list of alarms to the store."""
        LOGGER.debug(
            "Saving %s alarms to store for %s", len(self._alarms), self._entry_id
        )
        data_to_save = [
            {"number": alarm["number"], "datetime": alarm["datetime_obj"].isoformat()}
            for alarm in self._alarms
        ]
        await self._store.async_save(data_to_save)
