import logging
import asyncio
from datetime import timedelta, datetime, timezone
from typing import Any, List, Dict
import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN, MODE_API, MODE_EMAIL, MODE_BOTH, CONF_URL, CONF_TOKEN, CONF_IMAP_HOST, CONF_IMAP_PORT, CONF_IMAP_USER, CONF_IMAP_PASS, CONF_EMAIL_SUBJECT, CONF_SCAN_INTERVAL, CONF_DATA_SOURCE
from .imap_client import fetch_from_email

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1

class EonDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching E.ON data from API and/or Email."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any], entry_id: str = "default"):
        """Initialize."""
        self.config = config
        self.mode = config.get(CONF_DATA_SOURCE, MODE_EMAIL)
        
        # API config
        self.api_url = config.get(CONF_URL, "").rstrip("/")
        self.api_token = config.get(CONF_TOKEN, "")
        
        # Email config
        self.imap_host = config.get(CONF_IMAP_HOST, "")
        self.imap_port = config.get(CONF_IMAP_PORT, 993)
        self.imap_user = config.get(CONF_IMAP_USER, "")
        self.imap_pass = config.get(CONF_IMAP_PASS, "")
        self.email_subject = config.get(CONF_EMAIL_SUBJECT, "")
        
        scan_interval = config.get(CONF_SCAN_INTERVAL, 3600)

        # Persistent storage (survives HA restarts)
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.buffer")

        # In-memory buffer (loaded from storage on startup)
        self._data_buffer: Dict[int, Dict] = {}

        # Diagnostics property for easy sensor representation
        self.sync_info = {
            "status": "Inicializálás alatt",
            "last_error": "-",
            "last_sync": "-",
            "rows_fetched": 0,
            "buffer_size": 0
        }
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def async_load_buffer(self) -> None:
        """Load persisted data buffer from HA storage."""
        stored = await self._store.async_load()
        if stored and isinstance(stored, dict):
            # Keys are stored as strings in JSON, convert back to int
            self._data_buffer = {int(k): v for k, v in stored.items()}
            _LOGGER.info(f"Loaded {len(self._data_buffer)} rows from persistent storage.")
        else:
            self._data_buffer = {}

    async def async_save_buffer(self) -> None:
        """Save data buffer to HA storage."""
        # JSON keys must be strings
        await self._store.async_save({str(k): v for k, v in self._data_buffer.items()})

    async def _async_update_data(self) -> List[Dict[str, Any]]:
        """Fetch data from configured source(s)."""
        rows_api = []
        rows_email = []
        errors = []

        try:
            async with async_timeout.timeout(60): # Increased timeout for IMAP
                if self.mode == MODE_API:
                    # 1. API Only
                    try:
                        rows_api = await self._fetch_api()
                    except Exception as e:
                        _LOGGER.warning(f"API Fetch failed: {e}")
                        errors.append(f"API: {e}")
                
                elif self.mode == MODE_EMAIL:
                    # 2. Email Only
                    try:
                        rows_email = await self.hass.async_add_executor_job(
                            fetch_from_email,
                            self.imap_host,
                            self.imap_port,
                            self.imap_user,
                            self.imap_pass,
                            self.email_subject
                        )
                    except Exception as e:
                        _LOGGER.warning(f"Email Fetch failed: {e}")
                        errors.append(f"Email: {e}")

                elif self.mode == MODE_BOTH:
                    # 3. Both - Try both, collect all
                    # API first
                    try:
                        rows_api = await self._fetch_api()
                    except Exception as e:
                        _LOGGER.warning(f"API Fetch failed (in dual mode): {e}")
                        errors.append(f"API: {e}")
                    
                    # Email second
                    try:
                        rows_email = await self.hass.async_add_executor_job(
                            fetch_from_email,
                            self.imap_host,
                            self.imap_port,
                            self.imap_user,
                            self.imap_pass,
                            self.email_subject
                        )
                    except Exception as e:
                        _LOGGER.warning(f"Email Fetch failed (in dual mode): {e}")
                        errors.append(f"Email: {e}")

                # Check for critical failure
                if self.mode == MODE_API and not rows_api and errors:
                    self._update_sync_info("Hiba történt", "\n".join(errors), 0)
                    raise UpdateFailed(f"API Error: {errors[0]}")
                if self.mode == MODE_EMAIL and not rows_email and errors:
                    self._update_sync_info("Hiba történt", "\n".join(errors), 0)
                    raise UpdateFailed(f"Email Error: {errors[0]}")
                if self.mode == MODE_BOTH and not rows_api and not rows_email and errors:
                   self._update_sync_info("Kettős Hiba", "\n".join(errors), 0)
                   raise UpdateFailed(f"Both sources failed: {errors}")

                # If no errors but no data
                if not rows_api and not rows_email:
                    self._update_sync_info("Nincs új adat", "Nem talált feldolgozható levelet/API adatot.", 0)
                    return list(self._data_buffer.values())
                    
                # We have data! Update sync info to Success
                self._update_sync_info("Sikeres Frissítés", "-", len(rows_api) + len(rows_email))

                # Merge and Deduplicate
                new_rows = rows_api + rows_email
                
                # Smart merge into consistent buffer
                # Key is timestamp int (ms)
                for row in new_rows:
                    ts = self._get_ts_int(row)
                    if not ts:
                        continue
                        
                    existing = self._data_buffer.get(ts)
                    if existing:
                        # Logic: If existing value is 0 and new value > 0, update it (Backfill).
                        # If existing value > 0 and new value is 0, keep existing (Prevent regression).
                        # If both > 0, update to new (Correction).
                        
                        n1_new = float(row.get("Num1", 0))
                        n2_new = float(row.get("Num2", 0))
                        n1_old = float(existing.get("Num1", 0))
                        n2_old = float(existing.get("Num2", 0))
                        
                        # Update Num1 (Import)
                        if n1_new > 0:
                            existing["Num1"] = n1_new
                        elif n1_old == 0:
                            existing["Num1"] = n1_new # Even if 0, update if old was 0
                            
                        # Update Num2 (Export)
                        if n2_new > 0:
                            existing["Num2"] = n2_new
                        elif n2_old == 0:
                            existing["Num2"] = n2_new

                        # Update metadata fields
                        for k, v in row.items():
                            if k not in ["Num1", "Num2", "Timestamp"]:
                                existing[k] = v
                    else:
                        # New timestamp
                        self._data_buffer[ts] = row.copy()
                
                # Prepare final list from buffer, sorted by time
                final_rows = list(self._data_buffer.values())
                
                # Sort
                final_rows.sort(key=self._get_ts_int)
                
                _LOGGER.debug(f"Fetched & Merged {len(final_rows)} rows (Buffer Size: {len(self._data_buffer)})")
                self.sync_info["buffer_size"] = len(self._data_buffer)

                # Persist the buffer so it survives HA restarts
                await self.async_save_buffer()

                # Inject historical statistics into HA recorder for graph/Energy Dashboard
                await self._async_inject_statistics(final_rows)

                return final_rows

        except UpdateFailed:
            raise
        except Exception as exc:
            self._update_sync_info("Kritikus Rendszerhiba", str(exc), 0)
            raise UpdateFailed(f"Unexpected error fetching E.ON data: {exc}") from exc

    def _update_sync_info(self, status, error, fetched):
        self.sync_info["status"] = status
        self.sync_info["last_error"] = error
        self.sync_info["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.sync_info["rows_fetched"] = fetched

    async def _async_inject_statistics(self, rows: List[Dict]) -> None:
        """Inject historical energy statistics into HA recorder so graphs show past data."""
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
            from homeassistant.components.recorder.statistics import async_add_external_statistics
            from homeassistant.const import UnitOfEnergy
        except ImportError:
            _LOGGER.warning("Recorder not available - skipping historical statistics injection")
            return

        if not rows:
            return

        # Group 15-min rows into hourly buckets for statistics (HA requires hourly granularity)
        # For each column (Num1=import, Num2=export) - sum each hour's 4x 15min values
        hourly_import: Dict[datetime, float] = {}
        hourly_export: Dict[datetime, float] = {}

        for row in rows:
            ts_str = row.get("Timestamp", "")
            if not ts_str.startswith("/Date("):
                continue
            try:
                ts_ms = int(ts_str[6:-2])
                dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                # Truncate to whole hour
                hour_dt = dt.replace(minute=0, second=0, microsecond=0)
            except Exception:
                continue

            n1 = float(row.get("Num1", 0) or 0)
            n2 = float(row.get("Num2", 0) or 0)
            hourly_import[hour_dt] = hourly_import.get(hour_dt, 0.0) + n1
            hourly_export[hour_dt] = hourly_export.get(hour_dt, 0.0) + n2

        if not hourly_import:
            return

        # Build cumulative sum statistics (required by HA energy stats)
        sorted_hours = sorted(hourly_import.keys())
        import_stats = []
        export_stats = []
        cumulative_import = 0.0
        cumulative_export = 0.0

        for hour_dt in sorted_hours:
            cumulative_import += hourly_import.get(hour_dt, 0.0)
            cumulative_export += hourly_export.get(hour_dt, 0.0)

            import_stats.append(StatisticData(
                start=hour_dt,
                sum=round(cumulative_import, 4),
                state=round(hourly_import.get(hour_dt, 0.0), 4),
            ))
            export_stats.append(StatisticData(
                start=hour_dt,
                sum=round(cumulative_export, 4),
                state=round(hourly_export.get(hour_dt, 0.0), 4),
            ))

        import_meta = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="E.ON Import (+A)",
            source=DOMAIN,
            statistic_id=f"{DOMAIN}:import_kwh",
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )
        export_meta = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="E.ON Export (-A)",
            source=DOMAIN,
            statistic_id=f"{DOMAIN}:export_kwh",
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        instance = get_instance(self.hass)
        await instance.async_add_executor_job(
            lambda: async_add_external_statistics(self.hass, import_meta, import_stats)
        )
        await instance.async_add_executor_job(
            lambda: async_add_external_statistics(self.hass, export_meta, export_stats)
        )
        _LOGGER.info(f"Injected {len(import_stats)} hourly statistics records into HA recorder")

    async def _fetch_api(self) -> List[Dict[str, Any]]:
        session = async_get_clientsession(self.hass)
        headers = {"X-Api-Key": self.api_token}
        url = f"{self.api_url}/adatok"
            
        async with session.get(url, headers=headers) as resp:
            if resp.status == 404:
                return []
            resp.raise_for_status()
            data = await resp.json()
            return data.get("adatok", [])

    def _get_ts_int(self, row):
        ts_str = row.get("Timestamp", "")
        if ts_str.startswith("/Date(") and ts_str.endswith(")/"):
            try:
                return int(ts_str[6:-2])
            except ValueError:
                return 0
        return 0
