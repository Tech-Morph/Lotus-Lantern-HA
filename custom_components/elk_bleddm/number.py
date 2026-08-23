"""Number platform for ELK-BLEDDM: mic sensitivity, effect speed, mic EQ mode.

All three map directly to command builders in const.py that were
extracted from the decompiled Lotus Lantern app. Mic EQ mode's actual
named presets weren't recoverable from the decompiled strings, so it's
exposed as a raw 0-7 index -- experiment to find which value matches
which behavior on your specific strip.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, cmd_effect_speed, cmd_mic_eq_mode, cmd_mic_sensitivity
from .device import ElkBleddmDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: ElkBleddmDevice = hass.data[DOMAIN][entry.entry_id]
    name: str = entry.data.get("name", "ELK-BLEDDM Light")
    async_add_entities(
        [
            ElkBleddmMicSensitivity(device, name),
            ElkBleddmEffectSpeed(device, name),
            ElkBleddmMicEqMode(device, name),
        ]
    )


class _ElkBleddmNumberBase(NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, device: ElkBleddmDevice, name: str, key: str) -> None:
        self._device = device
        self._attr_unique_id = f"{device.address}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.address)},
            "name": name,
            "manufacturer": "EasyLink / Maxuni",
            "model": "ELK-BLEDDM",
        }
        self._value: float = 0

    @property
    def available(self) -> bool:
        return self._device.available

    @property
    def native_value(self) -> float:
        return self._value


class ElkBleddmMicSensitivity(_ElkBleddmNumberBase):
    """0-255 mic input sensitivity for music-reactive effects."""

    _attr_name = "Mic Sensitivity"
    _attr_icon = "mdi:microphone-settings"
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1

    def __init__(self, device: ElkBleddmDevice, name: str) -> None:
        super().__init__(device, name, "mic_sensitivity")
        self._value = 50

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        await self._device.async_write(cmd_mic_sensitivity(int(value)))
        self.async_write_ha_state()


class ElkBleddmEffectSpeed(_ElkBleddmNumberBase):
    """0-255 animation speed for the built-in effect modes."""

    _attr_name = "Effect Speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1

    def __init__(self, device: ElkBleddmDevice, name: str) -> None:
        super().__init__(device, name, "effect_speed")
        self._value = 128

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        await self._device.async_write(cmd_effect_speed(int(value)))
        self.async_write_ha_state()


class ElkBleddmMicEqMode(_ElkBleddmNumberBase):
    """Raw 0-7 EQ preset index for mic-reactive mode (names unconfirmed)."""

    _attr_name = "Mic EQ Mode"
    _attr_icon = "mdi:equalizer"
    _attr_native_min_value = 0
    _attr_native_max_value = 7
    _attr_native_step = 1

    def __init__(self, device: ElkBleddmDevice, name: str) -> None:
        super().__init__(device, name, "mic_eq_mode")
        self._value = 0

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        await self._device.async_write(cmd_mic_eq_mode(int(value)))
        self.async_write_ha_state()
