import logging
import requests
import time
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class TwelveDataClient:
    """Client for Twelve Data API - DXY (Dollar Index) data."""

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.dxy_trend = None  # "UP", "DOWN", or None
        self.dxy_value = None
        self.last_update = None
        self._lock = threading.Lock()

    def get_dxy_data(self, interval="1min", outputsize=50) -> list:
        """Fetch DXY (US Dollar Index) time series data."""
        try:
            url = f"{self.BASE_URL}/time_series"
            params = {
                "symbol": "DXY",
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") == "error":
                logger.error(f"Twelve Data error: {data.get('message')}")
                return []

            values = data.get("values", [])
            return [{"close": float(v["close"]), "time": v["datetime"]} for v in reversed(values)]

        except Exception as e:
            logger.error(f"Error fetching DXY data: {e}")
            return []

    def get_dxy_trend(self) -> str:
        """Get current DXY trend direction.
        
        Returns:
            'UP' if dollar is strengthening
            'DOWN' if dollar is weakening
            None if unable to determine
        """
        try:
            data = self.get_dxy_data(interval="5min", outputsize=20)
            if len(data) < 5:
                return None

            closes = [d["close"] for d in data]
            
            # Simple trend: compare last 5 candles average vs previous 5
            recent_avg = sum(closes[-5:]) / 5
            previous_avg = sum(closes[-10:-5]) / 5

            with self._lock:
                self.dxy_value = closes[-1]
                if recent_avg > previous_avg:
                    self.dxy_trend = "UP"
                elif recent_avg < previous_avg:
                    self.dxy_trend = "DOWN"
                else:
                    self.dxy_trend = None
                self.last_update = datetime.now()

            return self.dxy_trend

        except Exception as e:
            logger.error(f"Error determining DXY trend: {e}")
            return None

    def check_dxy_confluence(self, pair: str, direction: str) -> bool:
        """Check if DXY trend is confluent with trade direction on USD pair.
        
        Logic:
        - If DXY UP (dollar strong) + CALL on USDJPY = confluent
        - If DXY UP (dollar strong) + PUT on EURUSD = confluent
        - If DXY DOWN (dollar weak) + CALL on EURUSD = confluent
        - If DXY DOWN (dollar weak) + PUT on USDJPY = confluent
        
        Returns True if confluent or if pair doesn't contain USD.
        """
        pair_clean = pair.upper().replace("-OTC", "")

        # Only filter USD pairs
        if "USD" not in pair_clean:
            return True

        trend = self.dxy_trend
        if trend is None:
            # Try to update
            trend = self.get_dxy_trend()
            if trend is None:
                return True  # Can't determine, don't block

        # Determine if USD is base or quote
        usd_is_base = pair_clean.startswith("USD")

        if usd_is_base:
            # e.g., USDJPY - DXY UP means pair goes UP
            if trend == "UP" and direction == "CALL":
                return True
            elif trend == "DOWN" and direction == "PUT":
                return True
            return False
        else:
            # e.g., EURUSD - DXY UP means pair goes DOWN
            if trend == "UP" and direction == "PUT":
                return True
            elif trend == "DOWN" and direction == "CALL":
                return True
            return False

    def start_background_update(self, interval_seconds=300):
        """Start background thread to update DXY trend periodically."""
        def _updater():
            while True:
                self.get_dxy_trend()
                time.sleep(interval_seconds)

        thread = threading.Thread(target=_updater, daemon=True)
        thread.start()
        logger.info("DXY background updater started (every 5min)")

    def get_status(self) -> dict:
        """Get current DXY status for dashboard."""
        with self._lock:
            return {
                "dxy_value": self.dxy_value,
                "dxy_trend": self.dxy_trend,
                "last_update": self.last_update.isoformat() if self.last_update else None
            }
