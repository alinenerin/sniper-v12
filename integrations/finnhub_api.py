import logging
import requests
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FinnhubClient:
    """Client for Finnhub API - Market news and surprise events."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.alert_active = False
        self.alert_reason = None
        self.last_update = None
        self._lock = threading.Lock()

    def get_market_news(self, category="forex") -> list:
        """Fetch latest market news."""
        try:
            url = f"{self.BASE_URL}/news"
            params = {
                "category": category,
                "token": self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return []

            news = response.json()
            return news if isinstance(news, list) else []

        except Exception as e:
            logger.error(f"Error fetching Finnhub news: {e}")
            return []

    def check_surprise_events(self) -> bool:
        """Check for surprise market events that should pause trading.
        
        Looks for keywords indicating major unexpected events:
        - Fed emergency meetings/speeches
        - ECB announcements
        - Geopolitical events
        - Flash crashes
        
        Returns True if trading should be paused.
        """
        try:
            news = self.get_market_news()
            if not news:
                return False

            # Keywords that indicate high-impact surprise events
            alert_keywords = [
                "fed emergency", "rate decision", "emergency meeting",
                "flash crash", "circuit breaker", "market halt",
                "fed chair", "powell speaks", "lagarde speaks",
                "ecb emergency", "intervention", "black swan",
                "war", "invasion", "sanctions announced"
            ]

            # Only check news from last 30 minutes
            cutoff = time.time() - 1800

            for article in news[:20]:  # Check latest 20
                pub_time = article.get("datetime", 0)
                if pub_time < cutoff:
                    continue

                headline = article.get("headline", "").lower()
                summary = article.get("summary", "").lower()
                text = headline + " " + summary

                for keyword in alert_keywords:
                    if keyword in text:
                        with self._lock:
                            self.alert_active = True
                            self.alert_reason = f"SURPRISE EVENT: {headline[:100]}"
                            logger.critical(f"NEWS ALERT: {headline}")
                        return True

            with self._lock:
                self.alert_active = False
                self.alert_reason = None

            return False

        except Exception as e:
            logger.error(f"Error checking surprise events: {e}")
            return False

    def should_block(self) -> bool:
        """Check if trading should be blocked due to surprise news."""
        with self._lock:
            return self.alert_active

    def start_background_monitor(self, interval_seconds=120):
        """Start background thread to monitor news every 2 minutes."""
        def _monitor():
            while True:
                self.check_surprise_events()
                self.last_update = datetime.now()
                time.sleep(interval_seconds)

        thread = threading.Thread(target=_monitor, daemon=True)
        thread.start()
        logger.info("Finnhub news monitor started (every 2min)")

    def get_status(self) -> dict:
        """Get current news alert status for dashboard."""
        with self._lock:
            return {
                "alert_active": self.alert_active,
                "alert_reason": self.alert_reason,
                "last_update": self.last_update.isoformat() if self.last_update else None
            }
