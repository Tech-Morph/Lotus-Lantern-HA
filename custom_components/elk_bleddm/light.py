"""Light platform for ELK-BLEDDM / Lotus Lantern strips.

Handles connection through Home Assistant's Bluetooth integration
(including ESPHome Bluetooth proxies) via bleak-retry-connector, and
writes the exact byte protocol reverse engineered from the Lotus
Lantern Android app.

v0.4: `available` now also treats a live, connected BleakClient as
available, instead of relying solely on recent advertisement sightings.
The ESP32 proxy stops scanning while a GATT connection is open, so
advertisement-based availability alone caused the entity to flap to
"Unavailable" every ~10-15 minutes even while actively connected.

v0.3: adds an asyncio.Lock around all connect+write operations to stop
the keep-alive timer and real commands from racing into duplicate
connections (proxy thrashing / GATT write errors).
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    EFFECT_NAMES,
    WRITE_CHARACTERISTIC_UUID,
    cmd_brightness,
    cmd_color,
    cmd_effect,
    cmd_effect_speed,
    cmd_power,
)

_LOGGER = logging.getLogger(__name__)

EFFECT_NAME_TO_ID = {v: k for k, v in EFFECT_NAMES.items()}

KEEP_ALIVE_INTERVAL = datetime.timedelta(seconds=25)
MAX_CONNECT_ATTEMPTS = 5
POST_CONNECT_SETTLE_SECONDS = 0.3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform from a config entry."""
    address: str = entry.data["address"]
    name: str = entry.data.get("name", "ELK-BLEDDM Light")
    entity = ElkBleddmLight(hass, address, name, entry.entry_id)
    async_add_entities([entity])


class ElkBleddmLight(LightEntity):
    """Representation of an ELK-BLEDDM BLE light strip with a serialized, persistent connection."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(EFFECT_NAMES.values())

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, entry_id: str
    ) -> None:
        self._hass = hass
        self._address = address
        self._attr_unique_id = address
        self._attr_device_info = {
            "identifiers": {(DOMAIN, address)},
            "name": name,
            "manufacturer": "EasyLink / Maxuni",
            "model": "ELK-BLEDDM",
        }
        self._client: BleakClientWithServiceCache | None = None
        self._is_on = False
        self._brightness = 255
        self._rgb_color = (255, 255, 255)
        self._effect: str | None = None
        self._unsub_keep_alive = None
        self._ble_lock = asyncio.Lock()

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._rgb_color

    @property
    def effect(self) -> str | None:
        return self._effect

    @property
    def available(self) -> bool:
        # If we already hold a live, connected client, we're available
        # regardless of whether the proxy has seen a fresh advertisement
        # recently -- the proxy stops scanning while a GATT connection is
        # open, so advertisement staleness alone is not a reliable signal
        # once connected.
        if self._client is not None and self._client.is_connected:
            return True
        return (
            bluetooth.async_ble_device_from_address(
                self._hass, self._address, connectable=True
            )
            is not None
        )

    def _on_unexpected_disconnect(self, client: BleakClientWithServiceCache) -> None:
        """Called by bleak-retry-connector if the device drops the link on its own."""
        _LOGGER.warning(
            "ELK-BLEDDM %s disconnected unexpectedly; will reconnect on next write",
            self._address,
        )
        self._client = None

    async def _ensure_connected_locked(self) -> BleakClientWithServiceCache:
        """Connect (or reuse an existing connection). Caller must hold self._ble_lock."""
        if self._client is not None and self._client.is_connected:
            return self._client

        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is None:
            raise RuntimeError(
                f"Device {self._address} not visible to any Bluetooth proxy"
            )

        self._client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self._address,
            disconnected_callback=self._on_unexpected_disconnect,
            max_attempts=MAX_CONNECT_ATTEMPTS,
        )
        _LOGGER.debug("ELK-BLEDDM %s connected, settling before first write", self._address)
        await asyncio.sleep(POST_CONNECT_SETTLE_SECONDS)
        return self._client

    async def _write(self, payload: bytearray, retry: bool = True) -> None:
        async with self._ble_lock:
            try:
                client = await self._ensure_connected_locked()
                await client.write_gatt_char(
                    WRITE_CHARACTERISTIC_UUID, payload, response=False
                )
            except BleakError as err:
                self._client = None
                if not retry:
                    raise
                _LOGGER.debug(
                    "ELK-BLEDDM %s write failed (%s), reconnecting once",
                    self._address,
                    err,
                )
                client = await self._ensure_connected_locked()
                await client.write_gatt_char(
                    WRITE_CHARACTERISTIC_UUID, payload, response=False
                )

    async def _keep_alive_tick(self, _now) -> None:
        """Periodic no-op write to stop the link (or proxy slot) from idling out."""
        if not self._is_on:
            return
        if self._ble_lock.locked():
            return
        async with self._ble_lock:
            try:
                client = await self._ensure_connected_locked()
                await client.write_gatt_char(
                    WRITE_CHARACTERISTIC_UUID, cmd_power(True), response=False
                )
            except BleakError:
                self._client = None
                _LOGGER.debug(
                    "ELK-BLEDDM %s keep-alive failed, will retry next tick",
                    self._address,
                )

    async def async_added_to_hass(self) -> None:
        self._unsub_keep_alive = async_track_time_interval(
            self._hass, self._keep_alive_tick, KEEP_ALIVE_INTERVAL
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(cmd_power(True))
        self._is_on = True

        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
            await self._write(cmd_color(*self._rgb_color))

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            await self._write(cmd_brightness(self._brightness))

        if ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            effect_id = EFFECT_NAME_TO_ID.get(effect_name)
            if effect_id is not None:
                await self._write(cmd_effect(effect_id))
                self._effect = effect_name

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(cmd_power(False))
        self._is_on = False
        self.async_write_ha_state()

    async def async_set_effect_speed(self, speed: int) -> None:
        """Custom service call target: set effect animation speed (0-255)."""
        await self._write(cmd_effect_speed(speed))

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_keep_alive is not None:
            self._unsub_keep_alive()
            self._unsub_keep_alive = None
        async with self._ble_lock:
            if self._client is not None and self._client.is_connected:
                await self._client.disconnect()
