# ******************************************************************************
# @copyright (C) 2025 Zara-Toorox - Solar Forecast ML - ML Weather
# * This program is protected by a Proprietary Non-Commercial License.
# 1. Personal and Educational use only.
# 2. COMMERCIAL USE AND AI TRAINING ARE STRICTLY PROHIBITED.
# 3. Clear attribution to "Zara-Toorox" is required.
# * Full license terms: https://github.com/Zara-Toorox/ha-solar-forecast-ml/blob/main/LICENSE
# ******************************************************************************
"""Config flow for ML Weather integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from ...core.core_coordinator_init_helpers import CoordinatorInitHelpers
from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_SFML_CONFIG_ENTRY_ID,
)

_LOGGER = logging.getLogger(__name__)


def _get_sfml_options(hass) -> list[selector.SelectOptionDict]:
    """Build selector options for Solar Forecast ML entries."""
    return [
        selector.SelectOptionDict(
            value=entry.entry_id,
            label=CoordinatorInitHelpers.get_entry_label(entry),
        )
        for entry in CoordinatorInitHelpers.get_config_entries(hass)
    ]


class MLWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ML Weather."""

    VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        sfml_options = _get_sfml_options(self.hass)

        if not sfml_options:
            return self.async_abort(reason="no_sfml_entries")

        if user_input is not None:
            sfml_entry_id = user_input.get(CONF_SFML_CONFIG_ENTRY_ID)
            if CoordinatorInitHelpers.get_config_entry(self.hass, sfml_entry_id) is None:
                errors["base"] = "invalid_sfml_binding"
            else:
                name = user_input.get(CONF_NAME, "ML Weather")
                await self.async_set_unique_id(f"ml_weather_{name.lower().replace(' ', '_')}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        # Show the form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="ML Weather"): str,
                vol.Required(
                    CONF_SFML_CONFIG_ENTRY_ID,
                    default=sfml_options[0]["value"],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sfml_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return MLWeatherOptionsFlow(config_entry)


class MLWeatherOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ML Weather."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        sfml_options = _get_sfml_options(self.hass)

        if not sfml_options:
            return self.async_abort(reason="no_sfml_entries")

        if user_input is not None:
            sfml_entry_id = user_input.get(CONF_SFML_CONFIG_ENTRY_ID)
            if CoordinatorInitHelpers.get_config_entry(self.hass, sfml_entry_id) is None:
                errors["base"] = "invalid_sfml_binding"
            else:
                new_data = {
                    **self.config_entry.data,
                    CONF_SFML_CONFIG_ENTRY_ID: sfml_entry_id,
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        current_binding = self.config_entry.data.get(
            CONF_SFML_CONFIG_ENTRY_ID,
            sfml_options[0]["value"],
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SFML_CONFIG_ENTRY_ID,
                    default=current_binding,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sfml_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
