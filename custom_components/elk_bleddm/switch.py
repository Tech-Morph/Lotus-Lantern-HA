"""Switch platform for ELK-BLEDDM: external mic streaming and music-reactive color.

- "Mic Streaming": toggles the strip's built-in microphone input on/off
  (cmd_mic_on_off). This is the external mic pickup the Lotus Lantern
  app calls "Streaming External Mic".
- "Music Reactive Color": doesn't send a command by itself -- it flips
  a flag on the shared device object that the light entity checks when
  building color-set commands, switching between the normal color
  command (flag 0x10) and the music-reactive color command (flag 0x20).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, cmd_mic_on_off
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
            ElkBleddmMicSwitch(device, name),
            ElkBleddmMusicReactiveSwitch(device, name),
        ]
    )


class _ElkBleddmSwitchBase(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, device: ElkBleddmDevice, name: str, key: str) -> None:
        self._device = device
        self._attr_unique_id = f"{device.address}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.address)},
            "name": name,
            "manufacturer": "EasyLink / Maxuni",
            "model": "ELK-BLEDDM",
        }

    @property
    def available(self) -> bool:
        return self._device.available


class ElkBleddmMicSwitch(_ElkBleddmSwitchBase):
    """Toggle the strip's onboard microphone input."""

    _attr_name = "Mic Streaming"
    _attr_icon = "mdi:microphone"

    def __init__(self, device: ElkBleddmDevice, name: str) -> None:
        super().__init__(device, name, "mic_streaming")
        self._is_on = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_write(cmd_mic_on_off(True))
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_write(cmd_mic_on_off(False))
        self._is_on = False
        self.async_write_ha_state()


class ElkBleddmMusicReactiveSwitch(_ElkBleddmSwitchBase):
    """Flip whether color commands use the music-reactive variant."""

    _attr_name = "Music Reactive Color"
    _attr_icon = "mdi:music-note"
    _attr_entity_category = None

    def __init__(self, device: ElkBleddmDevice, name: str) -> None:
        super().__init__(device, name, "music_reactive")

    @property
    def is_on(self) -> bool:
        return self._device.music_reactive

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._device.music_reactive = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._device.music_reactive = False
        self.async_write_ha_state()
