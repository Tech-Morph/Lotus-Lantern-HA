"""Config flow for Lotus Lantern / ELK-BLEDDM lights.

Supports automatic discovery via any Bluetooth proxy (ESPHome active
proxy or local adapter) AND manual entry by MAC address as a fallback
for cases where auto-discovery doesn't fire (e.g. device still bonded
to the original phone app, or advertisement not yet cached by HA).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DOMAIN

MATCH_PREFIXES = ("ELK-BLEDDM", "ELK-BLEDOM", "ELK-BLEDOB", "MELK", "LEDBLE")


def _matches(name: str | None) -> bool:
    if not name:
        return False
    return any(name.startswith(p) for p in MATCH_PREFIXES)


class ElkBleddmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lotus Lantern / ELK-BLEDDM lights."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, str] = {}
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle automatic Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery_info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or self._discovery_info.address,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: self._discovery_info.name
                    or self._discovery_info.address,
                },
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery_info.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: pick from discovered devices, or enter MAC manually."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices.get(address, address),
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: self._discovered_devices.get(address, address),
                },
            )

        current_addresses = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_addresses:
                continue
            if _matches(info.name):
                self._discovered_devices[info.address] = info.name

        if self._discovered_devices:
            options = {
                addr: f"{name} ({addr})"
                for addr, name in self._discovered_devices.items()
            }
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_ADDRESS): vol.In(options)}
                ),
                errors=errors,
            )

        # Nothing auto-discovered: fall back to free-text MAC entry.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "hint": "No devices found automatically. Enter the MAC "
                "address manually (e.g. BE:27:3C:00:65:26)."
            },
        )
