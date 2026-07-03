"""Water heater platform for A. O. Smith Tankless."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MIN_TEMP, MAX_TEMP

_LOGGER = logging.getLogger(__name__)

OPERATION_MODE_ON = "on"
OPERATION_MODE_OFF = "off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up water heater entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    client = entry_data["client"]

    entities = [
        AOSmithTanklessWaterHeater(coordinator, client, device)
        for device in coordinator.data
    ]
    async_add_entities(entities)


class AOSmithTanklessWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Representation of an A. O. Smith Tankless water heater."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name as entity name
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = MIN_TEMP
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_operation_list = [OPERATION_MODE_ON]
    _attr_current_operation = OPERATION_MODE_ON

    def __init__(self, coordinator, client, device: dict) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self._client = client
        self._junction_id: str = device["junctionId"]
        self._attr_unique_id = f"{DOMAIN}_{device['dsn']}_water_heater"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["dsn"])},
            manufacturer=MANUFACTURER,
            model=device.get("model", "ATHR-199X3"),
            name=device.get("name", "Tankless Water Heater"),
            sw_version=device.get("data", {}).get("firmwareVersion"),
            serial_number=device.get("serial"),
        )

    def _get_device_data(self) -> dict:
        """Get the current device dict from coordinator."""
        for device in self.coordinator.data:
            if device.get("junctionId") == self._junction_id:
                return device
        return {}

    @property
    def current_temperature(self) -> float | None:
        """Return None — the API exposes no measured water temperature."""
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature setpoint."""
        return self._get_device_data().get("data", {}).get("temperatureSetpoint")

    @property
    def max_temp(self) -> float:
        """Return the max allowed setpoint from the API."""
        api_max = self._get_device_data().get("data", {}).get("temperatureSetpointMaximum")
        return float(api_max) if api_max else MAX_TEMP

    @property
    def available(self) -> bool:
        """Return True if the device is online."""
        return self._get_device_data().get("data", {}).get("isOnline", False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        setpoint = int(round(temp))
        await self._client.set_setpoint(self._junction_id, setpoint)
        await self.coordinator.async_request_refresh()
