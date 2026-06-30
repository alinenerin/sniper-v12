import logging
import time
import threading
import numpy as np
from datetime import datetime
from indicators import technical as ind

logger = logging.getLogger(__name__)


class BaseChannel:
    """Base class for all trading channels."""

    def __init__(self, name, cycle, expiration, min_score, timeframe,
                 pairs, iq_client, protections, forex_factory, twelve_data, finnhub):
        self.name = name
        self.cycle = cycle
        self.expiration = expiration
        self.min_score = min_score
        self.timeframe = timeframe  # in seconds (60 or 300)
        self.pairs = pairs
        self.iq = iq_client
        self.protections = protections
        self.forex_factory = forex_factory
        self.twelve_data = twelve_data
        self.finnhub = finnhub
        self.running = False
        self.last_signal = None
        self.signals_history = []
        self._thread = None

    def start(self):
        """Start the channel loop in a separate thread."""
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"Channel-{self.name}")
        self._thread.start()
        logger.info(f"Channel {self.name} started (cycle={self.cycle}s, exp={self.expiration}min)")

    def stop(self):
        """Stop the channel loop."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info(f"Channel {self.name} stopped")

    def _loop(self):
        """Main channel loop."""
        while self.running:
            try:
                cycle_start = time.time()

                # Check global protections
                if self.protections.is_paused():
                    time.sleep(self.cycle)
                    continue

                if self.protections.check_daily_stop():
                    logger.info(f"{self.name}: Daily stop active, sleeping...")
                    time.sleep(60)
                    continue

                if not self.protections.can_open_order():
                    time.sleep(5)
                    continue

                # Check news blocks
                if self.finnhub and self.finnhub.should_block():
                    logger.info(f"{self.name}: News alert active, skipping cycle")
                    time.sleep(self.cycle)
                    continue

                # Scan all pairs
                for pair in self.pairs:
                    if not self.running:
                        break

                    if not self.protections.can_open_order():
                        break

                    signal = self._analyze_pair(pair)
                    if signal:
                        self._execute_signal(signal)
                        break  # One trade per cycle max

                # Wait for next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.cycle - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"{self.name} loop error: {e}")
                time.sleep(10)

    def _analyze_pair(self, pair: str) -> dict:
        """Analyze a pair and return signal if conditions met.
        Override in subclasses for specific logic."""
        raise NotImplementedError

    def _execute_signal(self, signal: dict):
        """Execute a trading signal or send to Telegram (SIGNAL_ONLY mode)."""
        from config import SIGNAL_ONLY, ENTRY_PERCENT
        from integrations.telegram_notifier import notifier

        pair = signal["pair"]
        direction = signal["direction"]
        score = signal["score"]

        # Final protection checks
        if self.protections.check_cooldown(pair, self.name):
            logger.debug(f"{self.name}: {pair} in cooldown, skipping")
            return

        if self.protections.check_trap_zone():
            logger.debug(f"{self.name}: Trap zone detected, skipping")
            notifier.notify_veto(self.name, pair, "Trap Zone")
            return

        if self.forex_factory and self.forex_factory.should_block(pair):
            logger.info(f"{self.name}: ForexFactory block for {pair}")
            notifier.notify_veto(self.name, pair, "ForexFactory - Evento HIGH")
            return

        if not self.protections.can_open_order():
            return

        # Send signal to Telegram
        notifier.notify_signal(self.name, pair, direction, score, self.min_score)

        # Record signal
        signal_record = {
            "time": datetime.now().isoformat(),
            "pair": pair,
            "direction": direction,
            "score": score,
            "channel": self.name,
            "executed": not SIGNAL_ONLY
        }
        self.last_signal = signal_record
        self.signals_history.append(signal_record)

        # If SIGNAL_ONLY mode, just log and return (no execution)
        if SIGNAL_ONLY:
            logger.info(f"SIGNAL (no exec): {self.name} | {pair} | {direction} | Score: {score}")
            self.protections.record_trade(pair, self.name)
            return

        # === EXECUTION MODE ===
        balance = self.iq.get_balance()
        if balance <= 0:
            return

        amount = round(balance * ENTRY_PERCENT, 2)
        amount = max(1.0, amount)  # Minimum $1

        # Place order
        with self.protections.order_lock:
            self.protections.set_order_active()

            success, order_id = self.iq.buy(pair, amount, direction.lower(), self.expiration)

            if success and order_id:
                self.protections.record_trade(pair, self.name)
                signal_record["amount"] = amount
                signal_record["order_id"] = order_id

                notifier.notify_trade_opened(self.name, pair, direction, amount)
                logger.info(f"SIGNAL EXECUTED: {self.name} | {pair} | {direction} | Score: {score} | ${amount:.2f}")

                # Wait for result
                win, profit = self.iq.check_result(order_id)
                signal_record["win"] = win
                signal_record["profit"] = profit

                self.protections.record_result(win, pair, self.name, amount)
                self.protections.set_order_closed()

                new_balance = self.iq.get_balance()
                notifier.notify_trade_result(pair, direction, "WIN" if win else "LOSS", profit if win else amount, new_balance)

                if win:
                    logger.info(f"\u2705 WIN: {pair} ({self.name}) +${profit:.2f}")
                else:
                    logger.warning(f"\u274c LOSS: {pair} ({self.name}) -${amount:.2f}")
            else:
                self.protections.set_order_closed()

    def _get_candle_data(self, pair: str, count: int = 100) -> dict:
        """Fetch candle data and extract OHLC arrays."""
        candles = self.iq.get_candles(pair, self.timeframe, count)
        if not candles or len(candles) < 20:
            return None

        data = {
            "opens": np.array([c["open"] for c in candles], dtype=float),
            "highs": np.array([c["high"] for c in candles], dtype=float),
            "lows": np.array([c["low"] for c in candles], dtype=float),
            "closes": np.array([c["close"] for c in candles], dtype=float),
            "last_candle": candles[-1]
        }
        return data

    def get_status(self) -> dict:
        """Get channel status for dashboard."""
        return {
            "name": self.name,
            "running": self.running,
            "cycle": self.cycle,
            "expiration": self.expiration,
            "min_score": self.min_score,
            "last_signal": self.last_signal,
            "total_signals": len(self.signals_history),
            "recent_signals": self.signals_history[-10:]
        }
