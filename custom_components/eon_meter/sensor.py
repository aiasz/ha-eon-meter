from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the E.ON sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        EonIntervalSensor(coordinator, "Num1", "Import 15min (+A)"),
        EonIntervalSensor(coordinator, "Num2", "Export 15min (-A)"),
        EonTotalSensor(coordinator, "import", "Num1", "Import Total"),
        EonTotalSensor(coordinator, "export", "Num2", "Export Total"),
        EonDailySensor(coordinator, "import", "Num1", "Import Daily"),
        EonDailySensor(coordinator, "export", "Num2", "Export Daily"),
        EonWeeklySensor(coordinator, "import", "Num1", "Import Weekly"),
        EonWeeklySensor(coordinator, "export", "Num2", "Export Weekly"),
        EonMonthlySensor(coordinator, "import", "Num1", "Import Monthly"),
        EonMonthlySensor(coordinator, "export", "Num2", "Export Monthly"),
        EonOutageSensor(coordinator, "Last Outage"),
        EonStatusSensor(coordinator, "API/IMAP Status"),
    ]
    
    async_add_entities(entities)


from homeassistant.helpers.entity import DeviceInfo

# ... existing imports ...

class EonBaseSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Base class for E.ON sensors."""
    
    def __init__(self, coordinator, name_suffix):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = name_suffix
        self._attr_unique_id = f"eon_{name_suffix.lower().replace(' ', '_')}"
        self._last_ts = 0  # Timestamp in ms (or s depending on parser)
        self._attr_native_value = 0.0

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Try to get POD from coordinator data
        pod = "Unknown"
        if self.coordinator.data and len(self.coordinator.data) > 0:
            pod = self.coordinator.data[0].get("Pod", "Unknown")
            
        return DeviceInfo(
            identifiers={(DOMAIN, "eon_main_device")},
            name=f"E.ON Meter {pod}",
            manufacturer="E.ON",
            model="Smart Meter API",
            sw_version="1.0.8",
        )

    async def async_added_to_hass(self):
        """Restore last state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            # Restore value
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                self._attr_native_value = 0.0
            
            # Restore last processed timestamp
            if "last_processed_ts" in last_state.attributes:
                self._last_ts = last_state.attributes["last_processed_ts"]

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return {"last_processed_ts": self._last_ts}
        
    def _parse_timestamp(self, row):
        # Extract int from "/Date(123456...)/"
        ts_str = row.get("Timestamp", "")
        if ts_str.startswith("/Date(") and ts_str.endswith(")/"):
            try:
                return int(ts_str[6:-2])
            except ValueError:
                return 0
        return 0

    def _get_val(self, row, key):
        try:
            return float(row.get(key, 0))
        except ValueError:
            return 0.0

class EonIntervalSensor(EonBaseSensor):
    """Sensor for the exact 15-minute interval raw values (+A / -A)."""
    
    def __init__(self, coordinator, data_key, name):
        super().__init__(coordinator, name)
        self._data_key = data_key
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        if self.coordinator.data and len(self.coordinator.data) > 0:
            last_row = self.coordinator.data[-1]
            for key, val in last_row.items():
                if key not in ["Timestamp", "Datum", "Pod", "Num1", "Num2"]:
                    attrs[key] = val
        return attrs

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return
            
        # Get the very last raw timestamp and value from the payload
        last_row = rows[-1]
        self._last_ts = self._parse_timestamp(last_row)
        self._attr_native_value = self._get_val(last_row, self._data_key)
        self.async_write_ha_state()

class EonTotalSensor(EonBaseSensor):
    """Sensor for cumulative total (Import/Export)."""

    def __init__(self, coordinator, type_key, data_key, name):
        super().__init__(coordinator, name)
        self._data_key = data_key
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        # Store queried data in attribute as requested
        # Limit to last 672 entries (approx 1 week) to avoid HA state database issues
        data = self.coordinator.data or []
        limit = 672 
        attrs["measurements"] = data[-limit:] if len(data) > limit else data
        return attrs

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        rows = self.coordinator.data
        if not rows:
            return

        # Re-calculate total from ALL available data to support backfill
        total = 0.0
        for row in rows:
            val = self._get_val(row, self._data_key)
            total += val
        
        self._attr_native_value = total
        self.async_write_ha_state()


class EonDailySensor(EonBaseSensor):
    """Sensor for Daily usage (resets at midnight)."""
    
    def __init__(self, coordinator, type_key, data_key, name):
        super().__init__(coordinator, name)
        self._data_key = data_key
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._current_day_str = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and "current_day_str" in last_state.attributes:
             self._current_day_str = last_state.attributes["current_day_str"]

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        attrs["current_day_str"] = self._current_day_str
        return attrs

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return

        # Identify the "current" day based on the latest available data
        last_row = rows[-1]
        current_data_day = last_row.get("Datum")
        
        if not current_data_day:
            return

        # Sum usage for this specific day
        daily_sum = 0.0
        for row in rows:
            if row.get("Datum") == current_data_day:
                val = self._get_val(row, self._data_key)
                daily_sum += val
            
        self._current_day_str = current_data_day
        self._attr_native_value = daily_sum
        self.async_write_ha_state()


class EonWeeklySensor(EonBaseSensor):
    """Sensor for Weekly usage (resets on Monday)."""

    def __init__(self, coordinator, type_key, data_key, name):
        super().__init__(coordinator, name)
        self._data_key = data_key
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._current_week_str = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and "current_week_str" in last_state.attributes:
             self._current_week_str = last_state.attributes["current_week_str"]

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        attrs["current_week_str"] = self._current_week_str
        return attrs

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return

        # Identify current Week from latest data
        last_row = rows[-1]
        ts_last = self._parse_timestamp(last_row)
        dt_last = datetime.fromtimestamp(ts_last / 1000.0)
        iso_year, iso_week, _ = dt_last.isocalendar()
        current_week_str = f"{iso_year}-W{iso_week}"
        
        # Sum usage for this specific week
        weekly_sum = 0.0
        for row in rows:
            ts = self._parse_timestamp(row)
            dt = datetime.fromtimestamp(ts / 1000.0)
            y, w, _ = dt.isocalendar()
            week_str = f"{y}-W{w}"
            
            if week_str == current_week_str:
                 val = self._get_val(row, self._data_key)
                 weekly_sum += val
        
        self._current_week_str = current_week_str
        self._attr_native_value = weekly_sum
        self.async_write_ha_state()


class EonMonthlySensor(EonBaseSensor):
    """Sensor for Monthly usage (resets on 1st)."""

    def __init__(self, coordinator, type_key, data_key, name):
        super().__init__(coordinator, name)
        self._data_key = data_key
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._current_month_str = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and "current_month_str" in last_state.attributes:
             self._current_month_str = last_state.attributes["current_month_str"]

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        attrs["current_month_str"] = self._current_month_str
        return attrs

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return

        # Identify current Month from latest data
        last_row = rows[-1]
        ts_last = self._parse_timestamp(last_row)
        dt_last = datetime.fromtimestamp(ts_last / 1000.0)
        current_month_str = dt_last.strftime("%Y-%m")
        
        # Sum usage for this specific month
        monthly_sum = 0.0
        for row in rows:
            ts = self._parse_timestamp(row)
            dt = datetime.fromtimestamp(ts / 1000.0)
            month_str = dt.strftime("%Y-%m")
            
            if month_str == current_month_str:
                val = self._get_val(row, self._data_key)
                monthly_sum += val
            
        self._current_month_str = current_month_str
        self._attr_native_value = monthly_sum
        self.async_write_ha_state()


class EonOutageSensor(EonBaseSensor):
    """Sensor to detect power outages (gaps > 15 min)."""
    
    def __init__(self, coordinator, name):
        super().__init__(coordinator, name)
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_native_value = None
        self._attr_state_class = None  # No state class for timestamp sensor

    async def async_added_to_hass(self):
        """Restore last state - timestamp sensor needs special handling."""
        await super().async_added_to_hass()
        # Override float restore - timestamps must be datetime or None
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable", "0.0", "0", "None", "none"):
            try:
                from datetime import datetime, timezone
                import re
                # Try parse ISO datetime string
                dt = datetime.fromisoformat(last_state.state)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                self._attr_native_value = dt
            except Exception:
                self._attr_native_value = None
        else:
            self._attr_native_value = None

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return
            
        # We scan for gaps in the *new* data
        # But we also need to check gap between _last_ts and first new row
        
        last_seen_ts = self._last_ts
        max_ts = self._last_ts
        found_any = False

        for row in rows:
            ts = self._parse_timestamp(row)
            if ts <= self._last_ts:
                continue
                
            found_any = True
            
            # Check gap
            # Normal interval is 15 min = 900 seconds = 900,000 ms
            if last_seen_ts > 0:
                diff = ts - last_seen_ts
                if diff > 15 * 60 * 1000 + 1000: # 15 min + tolerance
                    # Gap detected - use timezone-aware datetime as HA requires
                    from datetime import timezone
                    outage_time = datetime.fromtimestamp((last_seen_ts / 1000.0) + 900, tz=timezone.utc)
                    self._attr_native_value = outage_time
            
            last_seen_ts = ts
            max_ts = ts

        if found_any:
            self._last_ts = max_ts
            self.async_write_ha_state()

class EonStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor to display the technical status / error messages of the data fetching."""
    
    def __init__(self, coordinator, name):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_unique_id = "eon_meter_sync_status"
        self._attr_icon = "mdi:lan-check"

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
            sw_version="1.0.8",
        )

    @property
    def native_value(self):
        """Return the current exact operational status."""
        return self.coordinator.sync_info.get("status", "Ismeretlen")

    @property
    def extra_state_attributes(self):
        """Include the exact last error and sync times."""
        return self.coordinator.sync_info
