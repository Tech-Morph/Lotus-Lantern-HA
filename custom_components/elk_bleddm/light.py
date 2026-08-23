"""Light platform for ELK-BLEDDM / Lotus Lantern strips.

Handles connection through Home Assistant's Bluetooth integration
(including ESPHome Bluetooth proxies) via bleak-retry-connector, and
writes the exact byte protocol reverse engineered from the Lotus
Lantern Android app.
"""

from __future__ import annotations

import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform from a config entry."""
    address: str = entry.data["address"]
    name: str = entry.data.get("name", "ELK-BLEDDM Light")
    async_add_entities([ElkBleddmLight(hass, address, name, entry.entry_id)])


class ElkBleddmLight(LightEntity):
    """Representation of an ELK-BLEDDM BLE light strip."""

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
        return (
            bluetooth.async_ble_device_from_address(
                self._hass, self._address, connectable=True
            )
            is not None
        )

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        """Connect (or reuse an existing connection) via HA's Bluetooth stack."""
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
            BleakClientWithServiceCache, ble_device, self._address
        )
        return self._client

    async def _write(self, payload: bytearray) -> None:
        client = await self._ensure_connected()
        await client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, payload, response=False)

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
        if self._client is not None and self._client.is_connected:
            await self._client.disconnect()
