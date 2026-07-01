import logging
import time
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class IQOptionClient:
    """Wrapper for IQ Option API connection with robust reconnection."""

    def __init__(self, email, password, mode="PRACTICE"):
        self.email = email
        self.password = password
        self.mode = mode  # PRACTICE or REAL
        self.api = None
        self.connected = False
        self._lock = threading.Lock()
        self._reconnect_lock = threading.Lock()
        self._last_reconnect = 0
        self._reconnect_cooldown = 5  # seconds between reconnect attempts

    def connect(self) -> bool:
        """Connect to IQ Option."""
        try:
            from iqoptionapi.stable_api import IQ_Option
            self.api = IQ_Option(self.email, self.password)
            
            # Try connecting with retries
            for attempt in range(3):
                check, reason = self.api.connect()
                if check:
                    self.connected = True
                    self.api.change_balance(self.mode)
                    balance = self.get_balance()
                    logger.info(f"Connected to IQ Option ({self.mode}). Balance: ${balance:.2f}")
                    return True
                else:
                    logger.warning(f"Connection attempt {attempt+1}/3 failed: {reason}")
                    time.sleep(5)

            logger.error(f"Failed to connect to IQ Option after 3 attempts")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"IQ Option connection error: {e}")
            self.connected = False
            return False

    def reconnect(self) -> bool:
        """Reconnect if disconnected, with cooldown to prevent spam."""
        try:
            if self.api and self.api.check_connect():
                return True
        except Exception:
            pass

        # Cooldown between reconnect attempts
        now = time.time()
        if now - self._last_reconnect < self._reconnect_cooldown:
            return False

        with self._reconnect_lock:
            # Double-check after acquiring lock
            try:
                if self.api and self.api.check_connect():
                    return True
            except Exception:
                pass

            self._last_reconnect = now
            logger.warning("Connection lost. Reconnecting...")
            return self.connect()

    def get_balance(self) -> float:
        """Get current account balance."""
        try:
            if not self.connected:
                return 0.0
            return self.api.get_balance()
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0

    def get_candles(self, pair: str, timeframe: int, count: int) -> list:
        """Get historical candles with retry logic.
        
        Args:
            pair: Asset name (e.g., 'EURUSD-OTC')
            timeframe: Candle timeframe in seconds (60, 300, etc.)
            count: Number of candles to fetch
            
        Returns:
            List of candle dicts with keys: open, close, high, low, time
        """
        for attempt in range(3):
            try:
                if not self.reconnect():
                    time.sleep(2)
                    continue

                candles = self.api.get_candles(pair, timeframe, count, time.time())
                
                if not candles:
                    time.sleep(1)
                    continue
                    
                result = []
                for c in candles:
                    result.append({
                        "open": c["open"],
                        "close": c["close"],
                        "high": c["max"],
                        "low": c["min"],
                        "time": c["from"],
                        "volume": c.get("volume", 0)
                    })
                return result
            except Exception as e:
                if attempt < 2:
                    logger.debug(f"Retry {attempt+1} getting candles for {pair}: {e}")
                    time.sleep(2)
                else:
                    logger.error(f"Error getting candles for {pair} after 3 attempts: {e}")
        return []

    def buy(self, pair: str, amount: float, direction: str, expiration: int) -> tuple:
        """Place a binary option trade.
        
        Args:
            pair: Asset name
            amount: Trade amount in USD
            direction: 'call' or 'put'
            expiration: Expiration in minutes (1 or 5)
            
        Returns:
            (success: bool, order_id: int)
        """
        try:
            if not self.reconnect():
                return False, None

            with self._lock:
                logger.info(f"Placing {direction.upper()} on {pair} | ${amount:.2f} | Exp: {expiration}min")
                success, order_id = self.api.buy(amount, pair, direction, expiration)

                if success:
                    logger.info(f"Order placed successfully. ID: {order_id}")
                    return True, order_id
                else:
                    logger.error(f"Order failed for {pair}")
                    return False, None
        except Exception as e:
            logger.error(f"Error placing order on {pair}: {e}")
            return False, None

    def check_result(self, order_id) -> tuple:
        """Check the result of a completed trade.
        
        Returns:
            (win: bool, profit: float)
        """
        try:
            if not self.reconnect():
                return False, 0.0

            # Wait for result with timeout
            max_wait = 120  # 2 minutes max
            start = time.time()
            while time.time() - start < max_wait:
                try:
                    result = self.api.check_win_v4(order_id)
                    if result is not None:
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                logger.warning(f"Timeout waiting for result of order {order_id}")
                return False, 0.0

            if isinstance(result, (int, float)):
                win = result > 0
                return win, float(result)
            return False, 0.0
        except Exception as e:
            logger.error(f"Error checking result for order {order_id}: {e}")
            return False, 0.0

    def get_realtime_candles(self, pair: str, timeframe: int):
        """Subscribe to real-time candle stream."""
        try:
            if not self.reconnect():
                return None
            self.api.start_candles_stream(pair, timeframe, 1)
            return self.api.get_realtime_candles(pair, timeframe)
        except Exception as e:
            logger.error(f"Error getting realtime candles: {e}")
            return None

    def stop_candles_stream(self, pair: str, timeframe: int):
        """Stop real-time candle stream."""
        try:
            if self.api:
                self.api.stop_candles_stream(pair, timeframe)
        except Exception:
            pass

    def is_asset_open(self, pair: str) -> bool:
        """Check if an asset is currently available for trading."""
        try:
            if not self.reconnect():
                return False
            all_assets = self.api.get_all_open_time()
            # Check in binary options
            if "turbo" in all_assets:
                asset_info = all_assets["turbo"].get(pair, {})
                return asset_info.get("open", False)
            return False
        except Exception as e:
            logger.error(f"Error checking asset availability: {e}")
            return False
