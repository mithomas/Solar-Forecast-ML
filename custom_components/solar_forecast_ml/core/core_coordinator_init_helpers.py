# ******************************************************************************
# @copyright (C) 2026 Zara-Toorox - Solar Forecast ML DB-Version
# * This program is protected by a Proprietary Non-Commercial License.
# 1. Personal and Educational use only.
# 2. COMMERCIAL USE AND AI TRAINING ARE STRICTLY PROHIBITED.
# 3. Clear attribution to "Zara-Toorox" is required.
# * Full license terms: https://github.com/Zara-Toorox/ha-solar-forecast-ml/blob/main/LICENSE
# ******************************************************************************

"""
Containment Field Initialization Protocols V16.2.0.
Provides helper methods for warp core controller initialization and
nacelle configuration extraction. Pure utility functions with no
telemetry database dependencies. Handles cold-start antimatter injection
parameter resolution.
"""

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_ACTIVE_ENTRY_ID: ContextVar[str | None] = ContextVar(
    "solar_forecast_ml_active_entry_id", default=None
)

try:
    from ..const import (
        CONF_HOURLY,
        CONF_INVERTER_MAX_POWER,
        CONF_LEARNING_ENABLED,
        CONF_PANEL_GROUPS,
        CONF_POWER_ENTITY,
        CONF_SOLAR_CAPACITY,
        CONF_SOLAR_YIELD_TODAY,
        CONF_TOTAL_CONSUMPTION_TODAY,
        CONF_WEATHER_ENTITY,
        DEFAULT_INVERTER_MAX_POWER,
        DEFAULT_SOLAR_CAPACITY,
        DOMAIN,
    )
except ImportError:
    CONF_HOURLY = "hourly"
    CONF_INVERTER_MAX_POWER = "inverter_max_power"
    CONF_LEARNING_ENABLED = "learning_enabled"
    CONF_PANEL_GROUPS = "panel_groups"
    CONF_POWER_ENTITY = "power_entity"
    CONF_SOLAR_CAPACITY = "solar_capacity"
    CONF_SOLAR_YIELD_TODAY = "solar_yield_today"
    CONF_TOTAL_CONSUMPTION_TODAY = "total_consumption_today"
    CONF_WEATHER_ENTITY = "weather_entity"
    DEFAULT_INVERTER_MAX_POWER = 0.0
    DEFAULT_SOLAR_CAPACITY = 10.0
    DOMAIN = "solar_forecast_ml"


@dataclass
class CoordinatorConfiguration:
    """Configuration data extracted from ConfigEntry. @zara"""

    solar_capacity: float
    learning_enabled: bool
    enable_hourly: bool

    power_entity: Optional[str]
    solar_yield_today: Optional[str]
    primary_weather_entity: Optional[str]
    total_consumption_today: Optional[str]

    panel_groups: list[dict[str, Any]] = field(default_factory=list)
    inverter_max_power: float = 0.0

    @property
    def has_panel_groups(self) -> bool:
        """Check if panel groups are configured. @zara"""
        return len(self.panel_groups) > 0

    @property
    def has_inverter_clipping(self) -> bool:
        """Check if inverter clipping is enabled. @zara"""
        return self.inverter_max_power > 0.0


class CoordinatorInitHelpers:
    """Helper methods for coordinator initialization. @zara"""

    @staticmethod
    def set_active_entry(entry: ConfigEntry) -> Token[str | None]:
        """Store the config entry ID in the current task context. @zara"""
        return _ACTIVE_ENTRY_ID.set(entry.entry_id)

    @staticmethod
    def reset_active_entry(token: Token[str | None]) -> None:
        """Reset the task-local config entry context. @zara"""
        _ACTIVE_ENTRY_ID.reset(token)

    @staticmethod
    def get_config_entries(hass: HomeAssistant) -> list[ConfigEntry]:
        """Return configured Solar Forecast ML entries. @zara"""
        return hass.config_entries.async_entries(DOMAIN)

    @staticmethod
    def get_config_entry(
        hass: HomeAssistant,
        entry_id: str | None,
    ) -> ConfigEntry | None:
        """Look up a Solar Forecast ML config entry by ID. @zara"""
        if not entry_id:
            return None

        for entry in CoordinatorInitHelpers.get_config_entries(hass):
            if entry.entry_id == entry_id:
                return entry

        return None

    @staticmethod
    def get_entry_label(entry: ConfigEntry) -> str:
        """Return a readable label for a Solar Forecast ML entry. @zara"""
        title = entry.title or entry.data.get("name") or DOMAIN
        return f"{title} ({entry.entry_id[:8]})"

    @staticmethod
    def extract_configuration(entry: ConfigEntry) -> CoordinatorConfiguration:
        """Extract configuration from entry. @zara"""
        solar_capacity_value = entry.data.get(CONF_SOLAR_CAPACITY)
        if solar_capacity_value is None or solar_capacity_value == 0:
            solar_capacity_value = entry.data.get("plant_kwp", DEFAULT_SOLAR_CAPACITY)
            if solar_capacity_value != DEFAULT_SOLAR_CAPACITY:
                _LOGGER.warning(
                    f"Using legacy 'plant_kwp' value: {solar_capacity_value} kW. "
                    f"Please reconfigure to update."
                )

        panel_groups = entry.data.get(CONF_PANEL_GROUPS, [])
        if panel_groups:
            _LOGGER.info(
                "Panel groups configured: %d groups, total %.2f kWp",
                len(panel_groups),
                float(solar_capacity_value),
            )

        inverter_max_power = entry.data.get(CONF_INVERTER_MAX_POWER, DEFAULT_INVERTER_MAX_POWER)
        if inverter_max_power and inverter_max_power > 0:
            _LOGGER.info(
                "Inverter clipping enabled: max %.2f kW",
                float(inverter_max_power),
            )

        return CoordinatorConfiguration(
            solar_capacity=float(solar_capacity_value),
            learning_enabled=entry.options.get(CONF_LEARNING_ENABLED, True),
            enable_hourly=entry.options.get(CONF_HOURLY, False),
            power_entity=entry.data.get(CONF_POWER_ENTITY),
            solar_yield_today=entry.data.get(CONF_SOLAR_YIELD_TODAY),
            primary_weather_entity=entry.data.get(CONF_WEATHER_ENTITY),
            total_consumption_today=entry.data.get(CONF_TOTAL_CONSUMPTION_TODAY),
            panel_groups=panel_groups,
            inverter_max_power=float(inverter_max_power) if inverter_max_power else 0.0,
        )

    @staticmethod
    def setup_data_directory(
        hass: HomeAssistant,
        entry: ConfigEntry | None = None,
    ) -> Path:
        """Return the data directory for the active config entry. @zara"""
        base_dir = Path(hass.config.path(DOMAIN))

        active_entry_id = entry.entry_id if entry is not None else _ACTIVE_ENTRY_ID.get()
        if active_entry_id is None:
            return base_dir

        entries_dir = base_dir / "entries"
        return entries_dir / active_entry_id

    @staticmethod
    def resolve_data_directory(
        hass: HomeAssistant,
        entry_or_id: ConfigEntry | str,
    ) -> Path:
        """Resolve the data directory for a specific config entry. @zara"""
        entry = (
            entry_or_id
            if isinstance(entry_or_id, ConfigEntry)
            else CoordinatorInitHelpers.get_config_entry(hass, entry_or_id)
        )
        if entry is None:
            raise ValueError("Solar Forecast ML config entry could not be resolved")

        return CoordinatorInitHelpers.setup_data_directory(hass, entry)

    @staticmethod
    def resolve_database_path(
        hass: HomeAssistant,
        entry_or_id: ConfigEntry | str,
        filename: str = "solar_forecast.db",
    ) -> Path:
        """Resolve a database path for a specific config entry. @zara"""
        return CoordinatorInitHelpers.resolve_data_directory(hass, entry_or_id) / filename
