from datetime import datetime, timedelta, timezone
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
        # --- Aktív energia (kumulatív összeg a bufferből) ---
        EonTotalSensor(coordinator, "import", "Num1", "Import Total"),
        EonTotalSensor(coordinator, "export", "Num2", "Export Total"),
        # --- Napi / heti / havi számított értékek ---
        EonDailySensor(coordinator, "import", "Num1", "Import Daily"),
        EonDailySensor(coordinator, "export", "Num2", "Export Daily"),
        EonWeeklySensor(coordinator, "import", "Num1", "Import Weekly"),
        EonWeeklySensor(coordinator, "export", "Num2", "Export Weekly"),
        EonMonthlySensor(coordinator, "import", "Num1", "Import Monthly"),
        EonMonthlySensor(coordinator, "export", "Num2", "Export Monthly"),
        # --- Nettó egyenleg ---
        EonNetBalanceSensor(coordinator, "Napi Netto Egyenleg"),
        # --- Napi bontás (minden nap import/export/net a bufferből) ---
        EonDailyBreakdownSensor(coordinator, "Napi Fogyasztás Bontás"),
        # --- Mérőóra tényleges állása (OBIS kumulatív) ---
        EonObisLatestSensor(coordinator, "1-1:1.8.0*0", "Mérőóra Import Állás",
                            SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        EonObisLatestSensor(coordinator, "1-1:2.8.0*0", "Mérőóra Export Állás",
                            SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        # --- Reaktív energia (napi összeg) ---
        EonDailySensor(coordinator, "reaktiv_import", "+R",   "Import Reaktiv Daily"),
        EonDailySensor(coordinator, "reaktiv_export", "-R",   "Export Reaktiv Daily"),
        # --- Diagnosztika ---
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
            sw_version="1.0.14",
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
            v = row.get(key, 0)
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

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

        # Inject historical statistics so graphs/Energy Dashboard show past data
        # Uses source='recorder' + self.entity_id (ZsBT/hass-w1000-portal method)
        if self.entity_id:
            self.hass.async_create_task(self._inject_statistics(rows))

    async def _inject_statistics(self, rows) -> None:
        """Inject hourly statistics into HA recorder tied to this sensor entity."""
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import (
                async_import_statistics,
                StatisticData,
                StatisticMetaData,
            )
        except ImportError:
            try:
                from homeassistant.components.recorder import get_instance
                from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
                from homeassistant.components.recorder.statistics import async_import_statistics
            except ImportError:
                _LOGGER.warning("Recorder not available — skipping statistics injection for %s", self.entity_id)
                return

        entity_id = self.entity_id
        if not entity_id:
            _LOGGER.warning("entity_id not yet available for statistics injection, skipping")
            return

        hourly: dict = {}
        skipped = 0
        for row in rows:
            ts_str = row.get("Timestamp", "")
            if not ts_str.startswith("/Date("):
                skipped += 1
                continue
            try:
                ts_ms = int(ts_str[6:-2])
                dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                hour_dt = dt.replace(minute=0, second=0, microsecond=0)
            except Exception as e:
                _LOGGER.debug("Skipping row with bad timestamp: %s — %s", ts_str, e)
                skipped += 1
                continue
            val = self._get_val(row, self._data_key)
            hourly[hour_dt] = hourly.get(hour_dt, 0.0) + val

        _LOGGER.info(
            "Statistics injection for %s: %d hourly buckets built, %d rows skipped",
            entity_id, len(hourly), skipped,
        )

        if not hourly:
            _LOGGER.warning("No valid hourly buckets for %s — nothing injected", entity_id)
            return

        sorted_hours = sorted(hourly.keys())
        stats = []
        cumulative = 0.0
        for hour_dt in sorted_hours:
            cumulative += hourly[hour_dt]
            stats.append(StatisticData(
                start=hour_dt,
                state=round(hourly[hour_dt], 4),
                sum=round(cumulative, 4),
            ))

        meta = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=self.name,
            source="recorder",           # ties to the actual sensor entity (ZsBT módszer)
            statistic_id=entity_id,      # e.g. "sensor.e_on_meter_import_total"
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        try:
            instance = get_instance(self.hass)
            await instance.async_add_executor_job(
                lambda: async_import_statistics(self.hass, meta, stats)
            )
            _LOGGER.info(
                "✅ Injected %d hourly statistics for %s (%.4f kWh cumulative, range: %s → %s)",
                len(stats),
                entity_id,
                cumulative,
                sorted_hours[0].strftime("%Y-%m-%d %H:%M"),
                sorted_hours[-1].strftime("%Y-%m-%d %H:%M"),
            )
        except Exception as exc:
            _LOGGER.error("❌ Statistics injection FAILED for %s: %s", entity_id, exc)


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


class EonNetBalanceSensor(EonBaseSensor):
    """Napi nettó egyenleg: Import - Export az adott napra (bufferből számolva)."""

    def __init__(self, coordinator, name):
        super().__init__(coordinator, name)
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:scale-balance"
        self._current_day_str = None
        self._daily_import = 0.0
        self._daily_export = 0.0

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and "current_day_str" in last_state.attributes:
            self._current_day_str = last_state.attributes["current_day_str"]

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        attrs["current_day_str"] = self._current_day_str
        attrs["daily_import_kwh"] = round(self._daily_import, 4)
        attrs["daily_export_kwh"] = round(self._daily_export, 4)
        attrs["balance"] = "Fogyasztás" if self._attr_native_value >= 0 else "Visszatáplálás"
        return attrs

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return

        last_row = rows[-1]
        current_day = last_row.get("Datum")
        if not current_day:
            return

        daily_import = 0.0
        daily_export = 0.0
        for row in rows:
            if row.get("Datum") == current_day:
                daily_import += self._get_val(row, "Num1")
                daily_export += self._get_val(row, "Num2")

        self._daily_import = daily_import
        self._daily_export = daily_export
        self._current_day_str = current_day
        self._attr_native_value = round(daily_import - daily_export, 4)
        self.async_write_ha_state()


class EonObisLatestSensor(EonBaseSensor):
    """Sensor showing the latest non-zero value of an OBIS variable from the buffer.

    Mérőóra tényleges állásához: pl. 1-1:1.8.0*0 (kumulatív import kWh).
    Az óra legutóbbi beolvasott, nullától eltérő értékét mutatja.
    """

    def __init__(self, coordinator, obis_key: str, name: str,
                 device_class=None, state_class=None):
        super().__init__(coordinator, name)
        self._obis_key = obis_key
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:meter-electric"

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        attrs["obis_key"] = self._obis_key
        # Show last timestamp that had a non-zero reading
        rows = self.coordinator.data or []
        for row in reversed(rows):
            v = row.get(self._obis_key)
            if v is not None and float(v) > 0:
                attrs["last_reading_timestamp"] = row.get("Datum", "")
                break
        return attrs

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return

        # Find the most recent non-zero/non-None value for this OBIS key
        best_value = None
        for row in reversed(rows):
            raw = row.get(self._obis_key)
            if raw is not None:
                try:
                    v = float(raw)
                    if v > 0:
                        best_value = v
                        break
                except (ValueError, TypeError):
                    continue

        if best_value is not None:
            self._attr_native_value = round(best_value, 4)
            self.async_write_ha_state()


class EonDailyBreakdownSensor(EonBaseSensor):
    """Per-day import/export/net breakdown across all buffered days.

    State = latest complete day's net consumption (import − export) in kWh.
    Attributes contain a dict of every day in the buffer with import/export/net.
    Uses sum of +A (Num1) and -A (Num2) 15-min slots — equivalent to meter
    reading delta and works even when 1-1:1.8.0*0 is 0/None in the data.
    """

    def __init__(self, coordinator, name: str):
        super().__init__(coordinator, name)
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:calendar-month"
        self._days: dict = {}

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        attrs["daily_breakdown"] = self._days
        attrs["days_in_buffer"] = len(self._days)
        return attrs

    def _handle_coordinator_update(self) -> None:
        rows = self.coordinator.data
        if not rows:
            return

        # Aggregate per Datum
        days: dict[str, dict] = {}
        for row in rows:
            datum = row.get("Datum")
            if not datum:
                continue
            day_str = str(datum)
            if day_str not in days:
                days[day_str] = {"import": 0.0, "export": 0.0}
            days[day_str]["import"] += self._get_val(row, "Num1")
            days[day_str]["export"] += self._get_val(row, "Num2")

        # Round and compute net for each day
        for day_str, v in days.items():
            imp = round(v["import"], 4)
            exp = round(v["export"], 4)
            days[day_str] = {
                "import": imp,
                "export": exp,
                "net": round(imp - exp, 4),
            }

        self._days = days

        # State = latest complete day's net value
        if days:
            latest_day = sorted(days.keys())[-1]
            self._attr_native_value = days[latest_day]["net"]
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
            sw_version="1.0.14",
        )

    @property
    def native_value(self):
        """Return the current exact operational status."""
        return self.coordinator.sync_info.get("status", "Ismeretlen")

    @property
    def extra_state_attributes(self):
        """Include the exact last error and sync times."""
        return self.coordinator.sync_info
