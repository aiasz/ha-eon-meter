import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the E.ON Manual Update Button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([EonUpdateButton(coordinator)])


class EonUpdateButton(ButtonEntity):
    """Button to naturally trigger a data fetch."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_has_entity_name = True
        self._attr_name = "Kézi adatfrissítés"
        self._attr_unique_id = "eon_manual_update_button"
        self._attr_icon = "mdi:update"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        pod = "Unknown"
        if self.coordinator.data and len(self.coordinator.data) > 0:
            pod = self.coordinator.data[0].get("Pod", "Unknown")
            
        return DeviceInfo(
            identifiers={(DOMAIN, "eon_main_device")},
            name=f"E.ON Meter {pod}",
            manufacturer="E.ON",
            model="Smart Meter API",
            sw_version="1.0.16",
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Manual Update triggered for E.ON Meter Data")
        await self.coordinator.async_request_refresh()
