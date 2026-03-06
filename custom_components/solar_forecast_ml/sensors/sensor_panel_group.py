from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import slugify

from ..const import DOMAIN
from ..coordinator import SolarForecastMLCoordinator

_LOGGER = logging.getLogger(__name__)


def _build_hourly_attributes(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    hours = {}
    for row in sorted(rows, key=lambda item: item.get("target_hour", 0)):
        hour = row.get("target_hour")
        if hour is not None:
            hours[f"{int(hour):02d}:00"] = round(
                float(row.get("prediction_kwh", 0.0) or 0.0), 3
            )
    return {"hours": hours}


class PanelGroupForecastSensor(SensorEntity):
    """Per-panel-group forecast sensor backed by prediction_panel_groups."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    _KEY_CONFIG = {
        "next_hour": {
            "name": "Next Hour Forecast",
            "unique_id_prefix": "ml_panel_group_next_hour_forecast",
            "icon": "mdi:clock-fast",
        },
        "today": {
            "name": "Forecast Today",
            "unique_id_prefix": "ml_panel_group_forecast_today",
            "icon": "mdi:calendar-today",
        },
        "remaining": {
            "name": "Forecast Today Remaining",
            "unique_id_prefix": "ml_panel_group_forecast_remaining",
            "icon": "mdi:solar-power",
        },
        "tomorrow": {
            "name": "Forecast Tomorrow",
            "unique_id_prefix": "ml_panel_group_forecast_tomorrow",
            "icon": "mdi:weather-sunset-up",
        },
        "day_after_tomorrow": {
            "name": "Forecast Day After Tomorrow",
            "unique_id_prefix": "ml_panel_group_forecast_day_after_tomorrow",
            "icon": "mdi:calendar-arrow-right",
        },
    }

    def __init__(
        self,
        coordinator: SolarForecastMLCoordinator,
        entry: ConfigEntry,
        group_name: str,
        key: str,
    ) -> None:
        if key not in self._KEY_CONFIG:
            raise ValueError(f"Unsupported panel group sensor key: {key}")

        self._coordinator = coordinator
        self.entry = entry
        self._group_name = group_name
        self._key = key
        self._cached_value = 0.0
        self._hourly_rows: list[dict[str, Any]] = []
        self._upcoming_hours: list[dict[str, Any]] = []

        key_config = self._KEY_CONFIG[key]
        group_slug = slugify(group_name) or "panel_group"
        self._attr_name = f"{key_config['name']} {group_name}"
        self._attr_unique_id = (
            f"{entry.entry_id}_{key_config['unique_id_prefix']}_{group_slug}"
        )
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_icon = key_config["icon"]
        self._attr_suggested_display_precision = 2
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self._cached_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {"panel_group": self._group_name}
        if self._key == "next_hour":
            if not self._upcoming_hours:
                return attrs
            for index, hour_data in enumerate(self._upcoming_hours, start=1):
                attrs[f"hour_{index}"] = hour_data.get("kwh", 0.0)
                attrs[f"hour_{index}_time"] = hour_data.get("time", "")
            attrs["total_upcoming"] = round(
                sum(item.get("kwh", 0.0) for item in self._upcoming_hours), 2
            )
            attrs["hours_count"] = len(self._upcoming_hours)
            attrs["hours_list"] = self._upcoming_hours
            return attrs
        if self._hourly_rows:
            attrs.update(_build_hourly_attributes(self._hourly_rows))
        return attrs

    def _target_date_for_key(self) -> Optional[str]:
        from homeassistant.util import dt as dt_util

        now_local = dt_util.now()
        if self._key in {"next_hour", "today", "remaining"}:
            return now_local.date().isoformat()
        if self._key == "tomorrow":
            return (now_local + timedelta(days=1)).date().isoformat()
        if self._key == "day_after_tomorrow":
            return (now_local + timedelta(days=2)).date().isoformat()
        return None

    async def _fetch_group_rows(self, target_date: str) -> list[dict[str, Any]]:
        db = getattr(getattr(self._coordinator, "data_manager", None), "_db_manager", None)
        if not db:
            return []
        rows = await db.fetchall(
            """SELECT hp.target_hour, ppg.prediction_kwh
               FROM prediction_panel_groups ppg
               JOIN hourly_predictions hp
                 ON hp.prediction_id = ppg.prediction_id
               WHERE ppg.group_name = ?
                 AND hp.target_date = ?
               ORDER BY hp.target_hour""",
            (self._group_name, target_date),
        )
        return [
            {
                "target_hour": int(row[0]),
                "prediction_kwh": round(float(row[1] or 0.0), 3),
            }
            for row in rows
        ]

    async def _load_from_db(self) -> None:
        try:
            from homeassistant.util import dt as dt_util

            target_date = self._target_date_for_key()
            if not target_date:
                self._cached_value = 0.0
                self._hourly_rows = []
                self._upcoming_hours = []
                return

            all_rows = await self._fetch_group_rows(target_date)
            current_hour = dt_util.now().hour
            self._upcoming_hours = []

            if self._key == "next_hour":
                upcoming_rows = [
                    row for row in all_rows if row.get("target_hour", -1) > current_hour
                ]
                self._hourly_rows = upcoming_rows
                self._upcoming_hours = [
                    {
                        "time": f"{row.get('target_hour', 0):02d}:00",
                        "kwh": row.get("prediction_kwh", 0.0),
                    }
                    for row in upcoming_rows
                ]
                self._cached_value = (
                    float(upcoming_rows[0].get("prediction_kwh", 0.0))
                    if upcoming_rows
                    else 0.0
                )
                return

            filtered_rows = (
                [row for row in all_rows if row.get("target_hour", -1) >= current_hour]
                if self._key == "remaining"
                else all_rows
            )
            self._hourly_rows = filtered_rows
            self._cached_value = round(
                sum(float(row.get("prediction_kwh", 0.0)) for row in filtered_rows), 2
            )
        except Exception as err:
            _LOGGER.warning(
                "Failed to load PanelGroupForecastSensor for %s (%s): %s",
                self._group_name,
                self._key,
                err,
            )
            self._cached_value = 0.0
            self._hourly_rows = []
            self._upcoming_hours = []

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._load_from_db()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
        if self._key == "next_hour":
            self.async_on_remove(
                async_track_time_change(
                    self.hass,
                    self._handle_hour_boundary,
                    minute=0,
                    second=0,
                )
            )
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._reload_and_update())

    async def _reload_and_update(self) -> None:
        await self._load_from_db()
        self.async_write_ha_state()

    @callback
    def _handle_hour_boundary(self, now) -> None:
        self.hass.async_create_task(self._reload_and_update())
