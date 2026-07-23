"""Time platform for A. O. Smith Tankless recirculation timer start/end editing."""
from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import time_to_ms
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    client = entry_data["client"]
    entities = []
    for device in coordinator.data:
        recirc = device.get("data", {}).get("recirculation") or {}
        if not recirc.get("recirculationCapability"):
            continue
        for timer_number in (1, 2):
            entities.append(AOSmithTimerTimeEntity(coordinator, client, device, timer_number, "start"))
            entities.append(AOSmithTimerTimeEntity(coordinator, client, device, timer_number, "end"))
    async_add_entities(entities)


def _timer_to_input(t: dict, override_field: str | None = None, override_value: time | None = None) -> dict:
    """Convert a timer dict from the API into a RecirculationTimerInput dict."""
    def ts_to_time(ts):
        if ts is None:
            return None
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).time().replace(second=0, microsecond=0)

    start_t = override_value if override_field == "start" else ts_to_time(t.get("start"))
    end_t = override_value if override_field == "end" else ts_to_time(t.get("end"))

    return {
        "start": time_to_ms(start_t) if start_t is not None else None,
        "end": time_to_ms(end_t) if end_t is not None else None,
        "isEnabled": bool(t.get("isEnabled", False)),
        "isUnset": False,
    }


class AOSmithTimerTimeEntity(CoordinatorEntity, TimeEntity):
    """Time entity to edit the start or end of a recirculation timer."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, client, device: dict, timer_number: int, field: str) -> None:
        super().__init__(coordinator)
        self._client = client
        self._junction_id: str = device["junctionId"]
        self._dsn: str = device["dsn"]
        self._timer_number = timer_number
        self._timer_key = f"timer{timer_number}"
        self._other_timer_key = "timer2" if timer_number == 1 else "timer1"
        self._field = field
        label = "Start" if field == "start" else "End"
        self._attr_name = f"Recirculation Timer {timer_number} {label}"
        self._attr_unique_id = f"{DOMAIN}_{self._dsn}_recirc_timer{timer_number}_{field}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._dsn)},
            manufacturer=MANUFACTURER,
            model=device.get("model", "ATHR-199X3"),
            name=device.get("name", "Tankless Water Heater"),
        )

    def _get_recirc(self) -> dict:
        for device in self.coordinator.data:
            if device.get("junctionId") == self._junction_id:
                return device.get("data", {}).get("recirculation") or {}
        return {}

    @property
    def native_value(self) -> time | None:
        recirc = self._get_recirc()
        timer = recirc.get(self._timer_key, {})
        ts_ms = timer.get(self._field)
        if ts_ms is None:
            return None
        try:
            return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).time().replace(second=0, microsecond=0)
        except (OSError, ValueError, OverflowError):
            return None

    async def async_set_value(self, value: time) -> None:
        recirc = self._get_recirc()
        t1_raw = recirc.get("timer1", {})
        t2_raw = recirc.get("timer2", {})

        if t1_raw is None or t2_raw is None:
            _LOGGER.warning("Skipping set_value for %s - timer data not ready.", self.entity_id)
            return
        if self._timer_key == "timer1":
            timer1_input = _timer_to_input(t1_raw, override_field=self._field, override_value=value)
            timer2_input = _timer_to_input(t2_raw)
        else:
            timer1_input = _timer_to_input(t1_raw)
            timer2_input = _timer_to_input(t2_raw, override_field=self._field, override_value=value)


        await self._client.set_timer(
            self._junction_id,
            timer1=timer1_input,
            timer2=timer2_input,
        )
        await self.coordinator.async_request_refresh()
