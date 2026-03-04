import logging
import asyncio
from datetime import timedelta
from typing import Any, List, Dict
import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MODE_API, MODE_EMAIL, MODE_BOTH, CONF_URL, CONF_TOKEN, CONF_IMAP_HOST, CONF_IMAP_PORT, CONF_IMAP_USER, CONF_IMAP_PASS, CONF_EMAIL_SUBJECT, CONF_SCAN_INTERVAL, CONF_DATA_SOURCE
from .imap_client import fetch_from_email

_LOGGER = logging.getLogger(__name__)

class EonDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching E.ON data from API and/or Email."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        """Initialize."""
        self.config = config
        self.mode = config.get(CONF_DATA_SOURCE, MODE_EMAIL) # Default to email if missing
        
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

        # Buffer to store historical data points to handle backfill and accumulation
        self._data_buffer = {} 
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

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
                    raise UpdateFailed(f"API Error: {errors[0]}")
                if self.mode == MODE_EMAIL and not rows_email and errors:
                    raise UpdateFailed(f"Email Error: {errors[0]}")
                if self.mode == MODE_BOTH and not rows_api and not rows_email and errors:
                   raise UpdateFailed(f"Both sources failed: {errors}")

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
                return final_rows

        except Exception as exc:
            raise UpdateFailed(f"Unexpected error fetching E.ON data: {exc}") from exc

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
