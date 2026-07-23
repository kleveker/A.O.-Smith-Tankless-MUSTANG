"""Switch platform for A. O. Smith Tankless recirculation timer controls."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import time_to_ms
from .const import DOMAIN, MANUFACTURER


def _timer_to_input(t: dict, override_enabled: bool | None = None) -> dict:
    def ts_to_ms(ts):
        if ts is None:
            return None
        t_obj = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).time().replace(second=0, microsecond=0)
        return time_to_ms(t_obj)
    return {
        "start": ts_to_ms(t.get("start")),
        "end": ts_to_ms(t.get("end")),
        "isEnabled": override_enabled if override_enabled is not None else bool(t.get("isEnabled", False)),
        "isUnset": False,
    }


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
        entities.append(AOSmithTimerSwitch(coordinator, client, device, timer_number=1))
        entities.append(AOSmithTimerSwitch(coordinator, client, device, timer_number=2))
    async_add_entities(entities)


class AOSmithTimerSwitch(CoordinatorEntity, SwitchEntity):
    """Enable/disable a recirculation timer."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator, client, device: dict, timer_number: int) -> None:
        super().__init__(coordinator)
        self._client = client
        self._junction_id: str = device["junctionId"]
        self._dsn: str = device["dsn"]
        self._timer_number = timer_number
        self._timer_key = f"timer{timer_number}"
        self._attr_name = f"Recirculation Timer {timer_number}"
        self._attr_unique_id = f"{DOMAIN}_{self._dsn}_recirc_timer{timer_number}_enabled"
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
    def is_on(self) -> bool:
        return bool(self._get_recirc().get(self._timer_key, {}).get("isEnabled", False))

    async def _set_enabled(self, enabled: bool) -> None:
        recirc = self._get_recirc()
        t1 = recirc.get("timer1", {})
        t2 = recirc.get("timer2", {})
        if self._timer_key == "timer1":
            timer1_input = _timer_to_input(t1, override_enabled=enabled)
            timer2_input = _timer_to_input(t2)
        else:
            timer1_input = _timer_to_input(t1)
            timer2_input = _timer_to_input(t2, override_enabled=enabled)
        await self._client.set_timer(self._junction_id, timer1=timer1_input, timer2=timer2_input)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_enabled(False)
