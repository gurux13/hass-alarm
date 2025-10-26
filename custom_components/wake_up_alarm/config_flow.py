"""Adds config flow for the integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class IntegrationFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the integration."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            await self.async_set_unique_id(unique_id="the-one-and-only-config")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Alarm Integration", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {},
            ),
            errors=_errors,
        )
