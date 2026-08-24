"""Shared BLE connection manager for a Lotus Lantern / ELK-BLEDDM device.

All entity platforms (light, switch, number) for a given device share
one instance of this class, so they reuse a single BLE connection
instead of each opening their own -- important since ESPHome Bluetooth
proxies only support a handful of simultaneous connections.
"""

from __future__ import annotations

import asyncio
import datetime
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import WRITE_CHARACTERISTIC_UUID, cmd_power

_LOGGER = logging.getLogger(__name__)

KEEP_ALIVE_INTERVAL = datetime.timedelta(seconds=25)
MAX_CONNECT_ATTEMPTS = 5
POST_CONNECT_SETTLE_SECONDS = 0.3


class ElkBleddmDevice:
    """Owns the single BLE connection to one Lotus Lantern / ELK-BLEDDM device."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._unsub_keep_alive = None

        # Shared state flags, read/written by whichever entity platform
        # cares about them.
        self.is_on = False
        self.music_reactive = False

    @property
    def available(self) -> bool:
        if self._client is not None and self._client.is_connected:
            return True
        return (
            bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            is not None
        )

    def _on_unexpected_disconnect(self, client: BleakClientWithServiceCache) -> None:
        _LOGGER.warning("Lotus Lantern %s disconnected unexpectedly", self.address)
        self._client = None

    async def _ensure_connected_locked(self) -> BleakClientWithServiceCache:
        """Connect (or reuse). Caller must hold self._lock."""
        if self._client is not None and self._client.is_connected:
            return self._client

        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise RuntimeError(
                f"Device {self.address} not visible to any Bluetooth proxy"
            )

        self._client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.address,
            disconnected_callback=self._on_unexpected_disconnect,
            max_attempts=MAX_CONNECT_ATTEMPTS,
        )
        await asyncio.sleep(POST_CONNECT_SETTLE_SECONDS)
        return self._client

    async def async_write(self, payload: bytearray, retry: bool = True) -> None:
        """Write a command payload, connecting first if needed."""
        async with self._lock:
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
                    "Lotus Lantern %s write failed (%s), reconnecting once",
                    self.address,
                    err,
                )
                client = await self._ensure_connected_locked()
                await client.write_gatt_char(
                    WRITE_CHARACTERISTIC_UUID, payload, response=False
                )

    async def _keep_alive_tick(self, _now) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            try:
                client = await self._ensure_connected_locked()
                await client.write_gatt_char(
                    WRITE_CHARACTERISTIC_UUID, cmd_power(self.is_on), response=False
                )
            except BleakError:
                self._client = None
                _LOGGER.debug(
                    "Lotus Lantern %s keep-alive failed, will retry next tick",
                    self.address,
                )

    def start_keep_alive(self) -> None:
        if self._unsub_keep_alive is None:
            self._unsub_keep_alive = async_track_time_interval(
                self.hass, self._keep_alive_tick, KEEP_ALIVE_INTERVAL
            )

    async def async_shutdown(self) -> None:
        if self._unsub_keep_alive is not None:
            self._unsub_keep_alive()
            self._unsub_keep_alive = None
        async with self._lock:
            if self._client is not None and self._client.is_connected:
                await self._client.disconnect()
