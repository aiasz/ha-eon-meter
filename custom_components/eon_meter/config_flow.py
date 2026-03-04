import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from typing import Any

from .const import (
    DOMAIN, 
    CONF_URL, CONF_TOKEN, CONF_SCAN_INTERVAL, CONF_DATA_SOURCE,
    CONF_IMAP_HOST, CONF_IMAP_PORT, CONF_IMAP_USER, CONF_IMAP_PASS, CONF_EMAIL_SUBJECT,
    MODE_API, MODE_EMAIL, MODE_BOTH,
    DEFAULT_URL, DEFAULT_SCAN_INTERVAL, DEFAULT_IMAP_PORT, DEFAULT_EMAIL_SUBJECT
)

class EonMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for E.ON Meter."""

    VERSION = 1

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1: Select Data Source."""
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            mode = user_input[CONF_DATA_SOURCE]
            
            if mode == MODE_API:
                return await self.async_step_api()
            elif mode == MODE_EMAIL:
                return await self.async_step_email()
            elif mode == MODE_BOTH:
                return await self.async_step_api()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DATA_SOURCE, default=MODE_EMAIL): vol.In([MODE_EMAIL, MODE_API, MODE_BOTH]),
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
            }),
            errors=errors,
        )

    async def async_step_api(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step: API Configuration."""
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            # If BOTH mode, continue to email
            if self._data[CONF_DATA_SOURCE] == MODE_BOTH:
                return await self.async_step_email()
                
            return self.async_create_entry(title="E.ON (API)", data=self._data)

        return self.async_show_form(
            step_id="api",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=DEFAULT_URL): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
        )

    async def async_step_email(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step: Email Configuration."""
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            
            title_suffix = "Email"
            if self._data[CONF_DATA_SOURCE] == MODE_BOTH:
                title_suffix = "Hybrid"
            elif self._data[CONF_DATA_SOURCE] == MODE_API:
                title_suffix = "API"
                
            return self.async_create_entry(title=title_suffix, data=self._data)

        return self.async_show_form(
            step_id="email",
            data_schema=vol.Schema({
                vol.Required(CONF_IMAP_HOST): str,
                vol.Required(CONF_IMAP_PORT, default=DEFAULT_IMAP_PORT): int,
                vol.Required(CONF_IMAP_USER): str,
                vol.Required(CONF_IMAP_PASS): str,
                vol.Required(CONF_EMAIL_SUBJECT, default=DEFAULT_EMAIL_SUBJECT): str,
            }),
            errors=errors,
        )
