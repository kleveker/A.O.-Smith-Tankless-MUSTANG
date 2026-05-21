"""Sensor platform for A. O. Smith Tankless."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import parse_timestamp_ms
from .const import DOMAIN, MANUFACTURER


@dataclass(frozen=True)
class AOSmithSensorDescription(SensorEntityDescription):
    """Sensor entity description with value extractor."""
    value_fn: Callable[[dict], Any] | None = None


def _active_alerts(device: dict) -> str:
    alerts = device.get("data", {}).get("activeAlerts", [])
    if not alerts:
        return "None"
    active = [a for a in alerts if a.get("active")]
    if not active:
        return "None"
    return ", ".join(str(a.get("code", "")) for a in active)


def _recirc_timer(timer_key: str, field: str) -> Callable[[dict], Any]:
    def _fn(device: dict) -> Any:
        recirc = device.get("data", {}).get("recirculation", {})
        timer = recirc.get(timer_key, {})
        if field == "enabled":
            return "On" if timer.get("isEnabled") else "Off"
        if field == "start":
            return parse_timestamp_ms(timer.get("start"))
        if field == "end":
            return parse_timestamp_ms(timer.get("end"))
        return None
    return _fn


SENSOR_DESCRIPTIONS: tuple[AOSmithSensorDescription, ...] = (
    AOSmithSensorDescription(
        key="setpoint",
        name="Temperature Setpoint",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda d: d.get("data", {}).get("temperatureSetpoint"),
    ),
    AOSmithSensorDescription(
        key="setpoint_max",
        name="Max Setpoint",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("data", {}).get("temperatureSetpointMaximum"),
    ),
    AOSmithSensorDescription(
        key="online",
        name="Online Status",
        value_fn=lambda d: "Online" if d.get("data", {}).get("isOnline") else "Offline",
    ),
    AOSmithSensorDescription(
        key="firmware",
        name="Firmware Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("data", {}).get("firmwareVersion"),
    ),
    AOSmithSensorDescription(
        key="error",
        name="Error Code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("data", {}).get("error") or "None",
    ),
    AOSmithSensorDescription(
        key="active_alerts",
        name="Active Alerts",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_active_alerts,
    ),
    AOSmithSensorDescription(
        key="recirc_timer1_enabled",
        name="Recirculation Timer 1",
        value_fn=_recirc_timer("timer1", "enabled"),
    ),
    AOSmithSensorDescription(
        key="recirc_timer1_start",
        name="Recirculation Timer 1 Start",
        value_fn=_recirc_timer("timer1", "start"),
    ),
    AOSmithSensorDescription(
        key="recirc_timer1_end",
        name="Recirculation Timer 1 End",
        value_fn=_recirc_timer("timer1", "end"),
    ),
    AOSmithSensorDescription(
        key="recirc_timer2_enabled",
        name="Recirculation Timer 2",
        value_fn=_recirc_timer("timer2", "enabled"),
    ),
    AOSmithSensorDescription(
        key="recirc_timer2_start",
        name="Recirculation Timer 2 Start",
        value_fn=_recirc_timer("timer2", "start"),
    ),
    AOSmithSensorDescription(
        key="recirc_timer2_end",
        name="Recirculation Timer 2 End",
        value_fn=_recirc_timer("timer2", "end"),
    ),
    AOSmithSensorDescription(
        key="recirc_on_demand",
        name="Recirculation On-Demand",
        value_fn=lambda d: "On" if d.get("data", {}).get("recirculation", {}).get("pumpModeOnDemand") else "Off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []
    for device in coordinator.data:
        for description in SENSOR_DESCRIPTIONS:
            entities.append(AOSmithTanklessSensor(coordinator, device, description))
    async_add_entities(entities)


class AOSmithTanklessSensor(CoordinatorEntity, SensorEntity):
    """A sensor for the A. O. Smith Tankless water heater."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device: dict, description: AOSmithSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._junction_id: str = device["junctionId"]
        self._dsn: str = device["dsn"]
        self._attr_unique_id = f"{DOMAIN}_{self._dsn}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._dsn)},
            manufacturer=MANUFACTURER,
            model=device.get("model", "ATHR-199X3"),
            name=device.get("name", "Tankless Water Heater"),
        )

    def _get_device(self) -> dict:
        for device in self.coordinator.data:
            if device.get("junctionId") == self._junction_id:
                return device
        return {}

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self._get_device())
        return None
