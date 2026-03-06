"""Helpers for config entry display names and device metadata."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_POWER_ENTITY, DOMAIN, NAME


def _clean_text(value: object) -> str | None:
    """Normalize an optional text value."""
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None


def _entity_id_to_name(entity_id: str) -> str:
    """Build a readable fallback name from an entity ID."""
    object_id = entity_id.split(".", 1)[-1]
    words = object_id.replace("_", " ").strip()
    return words.title() if words else NAME


def derive_entry_title(
    hass: HomeAssistant,
    power_entity: object,
    entry_id: str | None = None,
) -> str:
    """Resolve a stable config entry title from the configured power entity."""
    power_entity_id = _clean_text(power_entity)
    if power_entity_id:
        state = hass.states.get(power_entity_id)
        if state is not None:
            friendly_name = _clean_text(state.attributes.get("friendly_name"))
            if friendly_name:
                return friendly_name

        return _entity_id_to_name(power_entity_id)

    if entry_id:
        return f"{NAME} {entry_id[:6]}"

    return NAME


def get_entry_display_name(entry: ConfigEntry) -> str:
    """Return the current visible name for a config entry."""
    title = _clean_text(entry.title)
    if title:
        return title

    power_entity_id = _clean_text(entry.data.get(CONF_POWER_ENTITY))
    if power_entity_id:
        return _entity_id_to_name(power_entity_id)

    return f"{NAME} {entry.entry_id[:6]}" if entry.entry_id else NAME


def build_device_info(
    entry: ConfigEntry,
    *,
    manufacturer: str,
    model: str,
    sw_version: str | None = None,
    configuration_url: str | None = None,
) -> DeviceInfo:
    """Build consistent device metadata for a forecast instance."""
    info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=get_entry_display_name(entry),
        manufacturer=manufacturer,
        model=model,
    )

    if sw_version is not None:
        info["sw_version"] = sw_version
    if configuration_url is not None:
        info["configuration_url"] = configuration_url

    return info
