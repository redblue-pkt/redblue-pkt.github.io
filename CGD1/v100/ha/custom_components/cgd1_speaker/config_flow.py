"""Discover a CGD1 or select it by Bluetooth address."""
import re
import probatio as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME

DOMAIN = "cgd1_speaker"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _discovery = None

    async def async_step_bluetooth(self, discovery_info):
        self._discovery = discovery_info
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery.name,
                data={CONF_ADDRESS: self._discovery.address, CONF_NAME: self._discovery.name},
            )
        return self.async_show_form(step_id="confirm")

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
                errors[CONF_ADDRESS] = "invalid_address"
            elif bluetooth.async_ble_device_from_address(self.hass, address, connectable=True) is None:
                errors["base"] = "not_discovered"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_ADDRESS: address, CONF_NAME: user_input[CONF_NAME]},
                )
        return self.async_show_form(
            step_id="user", errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str,
                                    vol.Optional(CONF_NAME, default="CGD1"): str}),
        )
