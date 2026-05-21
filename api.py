"""A. O. Smith iCOMM API client for Tankless (MUSTANG) water heaters."""
from __future__ import annotations

import base64
import json
import logging
import urllib.parse
from datetime import datetime, timezone, time as datetime_time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://r2.wh8.co"
GRAPHQL_URL = API_BASE_URL + "/graphql"

APP_VERSION = "14.1.0"
USER_AGENT = "okhttp/4.12.0"

DEVICES_QUERY = """
query devices($forceUpdate: Boolean, $junctionIds: [String]) {
  devices(forceUpdate: $forceUpdate, junctionIds: $junctionIds) {
    brand
    deviceType
    dsn
    id
    junctionId
    model
    name
    serial
    lastUpdate
    data {
      __typename
      isOnline
      isWifi
      temperatureSetpoint
      temperatureSetpointPending
      temperatureSetpointPrevious
      temperatureSetpointMaximum
      error
      activeAlerts {
        active
        code
        type
      }
      ... on Mustang {
        firmwareVersion
        recirculation {
          recirculationCapability
          pumpModeOnDemand
          timer1 {
            start
            end
            isEnabled
            isUnset
          }
          timer2 {
            start
            end
            isEnabled
            isUnset
          }
        }
      }
    }
  }
}
"""

SET_SETPOINT_MUTATION = """
mutation updateSetpoint($junctionId: String!, $setpoint: Int!) {
  updateSetpoint(junctionId: $junctionId, setpoint: $setpoint) {
    temperatureSetpoint
  }
}
"""

SET_RECIRCULATION_MUTATION = """
mutation updateRecirculation($junctionId: String!, $pumpModeOnDemand: Boolean!) {
  updateRecirculation(junctionId: $junctionId, pumpModeOnDemand: $pumpModeOnDemand) {
    pumpModeOnDemand
  }
}
"""

SET_TIMER_MUTATION = """
mutation updateRecirculationSchedule(
  $junctionId: String!,
  $timer1: RecirculationTimerInput!,
  $timer2: RecirculationTimerInput!
) {
  updateRecirculationSchedule(
    junctionId: $junctionId,
    timer1: $timer1,
    timer2: $timer2
  )
}
"""

LOGIN_QUERY = (
    "query login($passcode: String) "
    "{ login(passcode: $passcode) { user { tokens { accessToken idToken refreshToken } } } }"
)


def _build_passcode(email: str, password: str) -> str:
    data = {"email": email, "password": password, "locale": "en"}
    json_string = json.dumps(data)
    url_encoded = urllib.parse.quote(json_string)
    return base64.b64encode(url_encoded.encode()).decode("utf-8")


class AOSmithTanklessAuthError(Exception):
    pass


class AOSmithTanklessAPIError(Exception):
    pass


class AOSmithTanklessClient:
    def __init__(self, email: str, password: str, session: aiohttp.ClientSession) -> None:
        self._email = email
        self._password = password
        self._session = session
        self._token: str | None = None

    def _base_headers(self) -> dict[str, str]:
        return {
            "brand": "icomm",
            "version": APP_VERSION,
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

    async def authenticate(self) -> None:
        passcode = _build_passcode(self._email, self._password)
        data = await self._graphql(LOGIN_QUERY, {"passcode": passcode}, authenticated=False)
        token = (
            data.get("login", {})
            .get("user", {})
            .get("tokens", {})
            .get("accessToken")
        )
        if not token:
            raise AOSmithTanklessAuthError("No access token in login response")
        self._token = token

    async def _graphql(self, query: str, variables: dict[str, Any] | None = None, authenticated: bool = True) -> dict[str, Any]:
        if authenticated and not self._token:
            await self.authenticate()
        headers = self._base_headers()
        if authenticated and self._token:
            headers["authorization"] = f"Bearer {self._token}"
        body: dict[str, Any] = {"query": query, "variables": variables or {}}
        try:
            async with self._session.post(GRAPHQL_URL, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 401 and authenticated:
                    _LOGGER.debug("Token expired, re-authenticating")
                    await self.authenticate()
                    headers["authorization"] = f"Bearer {self._token}"
                    async with self._session.post(GRAPHQL_URL, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp2:
                        resp2.raise_for_status()
                        result = await resp2.json()
                else:
                    resp.raise_for_status()
                    result = await resp.json()
        except aiohttp.ClientError as err:
            raise AOSmithTanklessAPIError(f"API request failed: {err}") from err
        if "errors" in result:
            errors = result["errors"]
            if any(e.get("extensions", {}).get("code") == "INVALID_CREDENTIALS" for e in errors):
                raise AOSmithTanklessAuthError("Invalid email or password")
            raise AOSmithTanklessAPIError(f"GraphQL error: {errors}")
        return result.get("data", {})

    async def get_devices(self) -> list[dict[str, Any]]:
        data = await self._graphql(DEVICES_QUERY, {"forceUpdate": True})
        devices = data.get("devices", [])
        mustang_devices = [d for d in devices if d.get("deviceType") == "MUSTANG"]
        _LOGGER.debug("Found %d MUSTANG device(s)", len(mustang_devices))
        return mustang_devices

    async def get_device(self, junction_id: str) -> dict[str, Any] | None:
        devices = await self.get_devices()
        return next((d for d in devices if d.get("junctionId") == junction_id), None)

    async def set_setpoint(self, junction_id: str, setpoint: int) -> None:
        await self._graphql(SET_SETPOINT_MUTATION, {"junctionId": junction_id, "setpoint": setpoint})

    async def set_recirculation_on_demand(self, junction_id: str, enabled: bool) -> None:
        await self._graphql(SET_RECIRCULATION_MUTATION, {"junctionId": junction_id, "pumpModeOnDemand": enabled})

    async def set_timer(self, junction_id: str, timer1: dict, timer2: dict) -> None:
        await self._graphql(SET_TIMER_MUTATION, {"junctionId": junction_id, "timer1": timer1, "timer2": timer2})


def parse_timestamp_ms(ts_ms: int | None, tz_name: str = "UTC") -> str | None:
    if ts_ms is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime("%H:%M")
    except (OSError, ValueError, OverflowError):
        return None


def time_to_ms(t: datetime_time) -> float:
    today = datetime.now(tz=timezone.utc).date()
    dt = datetime(today.year, today.month, today.day, t.hour, t.minute, 0, tzinfo=timezone.utc)
    return dt.timestamp() * 1000
