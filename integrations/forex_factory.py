import logging
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import threading
import time

logger = logging.getLogger(__name__)


class ForexFactoryCalendar:
    """Scrapes ForexFactory calendar for HIGH impact events."""

    def __init__(self):
        self.events = []
        self.last_update = None
        self._lock = threading.Lock()
        self._update_interval = 3600  # Update every hour

    def update_calendar(self):
        """Fetch today's economic calendar from ForexFactory."""
        try:
            url = "https://www.forexfactory.com/calendar"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"ForexFactory returned status {response.status_code}")
                # Try alternative source
                self._update_from_alternative()
                return

            soup = BeautifulSoup(response.text, "html.parser")
            events = []

            # Parse calendar rows
            rows = soup.find_all("tr", class_="calendar__row")
            current_time = None

            for row in rows:
                try:
                    # Get time
                    time_cell = row.find("td", class_="calendar__time")
                    if time_cell and time_cell.text.strip():
                        current_time = time_cell.text.strip()

                    # Get impact
                    impact_cell = row.find("td", class_="calendar__impact")
                    if not impact_cell:
                        continue

                    impact_span = impact_cell.find("span")
                    if not impact_span:
                        continue

                    impact_class = impact_span.get("class", [])
                    is_high = any("high" in c.lower() for c in impact_class)

                    if not is_high:
                        continue

                    # Get currency
                    currency_cell = row.find("td", class_="calendar__currency")
                    currency = currency_cell.text.strip() if currency_cell else ""

                    # Get event name
                    event_cell = row.find("td", class_="calendar__event")
                    event_name = event_cell.text.strip() if event_cell else ""

                    if current_time and event_name:
                        events.append({
                            "time": current_time,
                            "currency": currency,
                            "event": event_name,
                            "impact": "HIGH"
                        })
                except Exception:
                    continue

            with self._lock:
                self.events = events
                self.last_update = datetime.now()
                logger.info(f"ForexFactory calendar updated: {len(events)} HIGH events found")

        except Exception as e:
            logger.error(f"Error updating ForexFactory calendar: {e}")
            self._update_from_alternative()

    def _update_from_alternative(self):
        """Try alternative economic calendar source."""
        try:
            # Use investing.com economic calendar API as fallback
            url = "https://economic-calendar.tradingview.com/events"
            params = {
                "from": datetime.now().strftime("%Y-%m-%dT00:00:00Z"),
                "to": datetime.now().strftime("%Y-%m-%dT23:59:59Z"),
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                events = []
                for item in data.get("result", []):
                    if item.get("importance", 0) >= 2:  # High importance
                        events.append({
                            "time": item.get("date", ""),
                            "currency": item.get("currency", ""),
                            "event": item.get("title", ""),
                            "impact": "HIGH"
                        })
                with self._lock:
                    self.events = events
                    self.last_update = datetime.now()
                    logger.info(f"Alternative calendar: {len(events)} HIGH events")
        except Exception as e:
            logger.warning(f"Alternative calendar also failed: {e}")

    def should_block(self, pair: str = None) -> bool:
        """Check if trading should be blocked due to upcoming HIGH event.
        
        Blocks 30 minutes before and 10 minutes after HIGH impact events.
        """
        # Auto-update if stale
        if not self.last_update or (datetime.now() - self.last_update).seconds > self._update_interval:
            threading.Thread(target=self.update_calendar, daemon=True).start()

        now = datetime.now()

        with self._lock:
            for event in self.events:
                try:
                    event_time_str = event.get("time", "")
                    # Try to parse event time
                    if ":" in event_time_str:
                        # Parse time like "8:30am" or "14:30"
                        event_time = self._parse_event_time(event_time_str)
                        if event_time is None:
                            continue

                        # Check if within block window
                        block_start = event_time - timedelta(minutes=30)
                        block_end = event_time + timedelta(minutes=10)

                        if block_start <= now <= block_end:
                            # If pair specified, check currency relevance
                            if pair:
                                currency = event.get("currency", "").upper()
                                pair_upper = pair.upper().replace("-OTC", "")
                                if currency and currency not in pair_upper:
                                    continue
                            logger.warning(f"NEWS BLOCK: {event['event']} ({event['currency']}) at {event_time_str}")
                            return True
                except Exception:
                    continue

        return False

    def _parse_event_time(self, time_str: str) -> datetime:
        """Parse various time formats from calendar."""
        try:
            now = datetime.now()
            time_str = time_str.strip().lower()

            if "am" in time_str or "pm" in time_str:
                # Format: "8:30am" or "2:30pm"
                time_str = time_str.replace(" ", "")
                parsed = datetime.strptime(time_str, "%I:%M%p")
                return now.replace(hour=parsed.hour, minute=parsed.minute, second=0)
            elif ":" in time_str:
                # Format: "14:30"
                parts = time_str.split(":")
                hour = int(parts[0])
                minute = int(parts[1])
                return now.replace(hour=hour, minute=minute, second=0)
        except Exception:
            pass
        return None

    def get_upcoming_events(self) -> list:
        """Get list of upcoming HIGH events for dashboard."""
        with self._lock:
            return self.events.copy()

    def start_background_update(self):
        """Start background thread to periodically update calendar."""
        def _updater():
            while True:
                self.update_calendar()
                time.sleep(self._update_interval)

        thread = threading.Thread(target=_updater, daemon=True)
        thread.start()
        logger.info("ForexFactory background updater started")
