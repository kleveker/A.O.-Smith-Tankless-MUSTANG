"""A. O. Smith Tankless (MUSTANG) integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AOSmithTanklessAPIError,
    AOSmithTanklessAuthError,
    AOSmithTanklessClient,
)
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.WATER_HEATER, Platform.SENSOR, Platform.SWITCH, Platform.TIME]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up A. O. Smith Tankless from a config entry."""
    session = async_get_clientsession(hass)
    client = AOSmithTanklessClient(
        entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], session
    )

    try:
        await client.authenticate()
    except AOSmithTanklessAuthError as err:
        raise ConfigEntryAuthFailed("Invalid A. O. Smith credentials") from err
    except AOSmithTanklessAPIError as err:
        raise ConfigEntryNotReady(f"A. O. Smith API unreachable: {err}") from err

    async def async_update_data() -> list[dict]:
        """Fetch data from the API."""
        try:
            return await client.get_devices()
        except AOSmithTanklessAuthError as err:
            raise ConfigEntryAuthFailed("Re-authentication required") from err
        except AOSmithTanklessAPIError as err:
            raise UpdateFailed(f"Error communicating with A. O. Smith API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
