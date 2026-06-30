import threading
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ProtectionManager:
    """Manages all trading protections: stops, cooldowns, pauses, locks."""

    def __init__(self, daily_stop_limit=4, sequential_stop_limit=3,
                 seq_pause_minutes=30, cooldown_seconds=120):
        self.daily_losses = 0
        self.daily_wins = 0
        self.sequential_losses = 0
        self.daily_stop_limit = daily_stop_limit
        self.sequential_stop_limit = sequential_stop_limit
        self.seq_pause_minutes = seq_pause_minutes
        self.cooldown_seconds = cooldown_seconds
        self.last_trade_time = {}
        self.paused_until = None
        self.bot_stopped = False
        self.global_lock = threading.Lock()
        self.order_lock = threading.Lock()  # Only 1 order at a time
        self.active_order = False
        self.trade_history = []
        self._reset_date = datetime.now().date()

    def _check_daily_reset(self):
        """Reset daily counters at midnight."""
        today = datetime.now().date()
        if today != self._reset_date:
            self.daily_losses = 0
            self.daily_wins = 0
            self.sequential_losses = 0
            self.bot_stopped = False
            self.paused_until = None
            self._reset_date = today
            logger.info("Daily counters reset")

    def check_daily_stop(self):
        """Returns True if daily loss limit reached (bot should stop)."""
        self._check_daily_reset()
        return self.daily_losses >= self.daily_stop_limit

    def check_sequential_stop(self):
        """Returns True if sequential loss limit reached (should pause)."""
        return self.sequential_losses >= self.sequential_stop_limit

    def record_result(self, win: bool, pair: str, channel: str, amount: float):
        """Record trade result and update counters."""
        with self.global_lock:
            self._check_daily_reset()
            result = {
                "time": datetime.now().isoformat(),
                "pair": pair,
                "channel": channel,
                "win": win,
                "amount": amount
            }
            self.trade_history.append(result)

            if win:
                self.daily_wins += 1
                self.sequential_losses = 0
                logger.info(f"WIN: {pair} ({channel}) +${amount:.2f}")
            else:
                self.daily_losses += 1
                self.sequential_losses += 1
                logger.warning(f"LOSS: {pair} ({channel}) -${amount:.2f}")

                if self.check_daily_stop():
                    self.bot_stopped = True
                    logger.critical(f"DAILY STOP REACHED: {self.daily_losses} losses. Bot stopped.")

                if self.check_sequential_stop():
                    self.paused_until = datetime.now() + timedelta(minutes=self.seq_pause_minutes)
                    logger.warning(f"SEQUENTIAL STOP: {self.sequential_losses} losses. Paused until {self.paused_until}")

    def check_cooldown(self, pair: str, channel: str) -> bool:
        """Returns True if pair is still in cooldown (should NOT trade)."""
        key = f"{pair}:{channel}"
        if key in self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time[key]).total_seconds()
            if elapsed < self.cooldown_seconds:
                return True
        return False

    def record_trade(self, pair: str, channel: str):
        """Record that a trade was placed (for cooldown tracking)."""
        key = f"{pair}:{channel}"
        self.last_trade_time[key] = datetime.now()

    def is_paused(self) -> bool:
        """Returns True if bot is in pause period."""
        if self.bot_stopped:
            return True
        if self.paused_until and datetime.now() < self.paused_until:
            return True
        if self.paused_until and datetime.now() >= self.paused_until:
            self.paused_until = None
            self.sequential_losses = 0
            logger.info("Pause period ended, resuming operations")
        return False

    def check_trap_zone(self) -> bool:
        """Returns True if current second is in trap zone (:02, :17, :32, :47 ±2s)."""
        current_second = datetime.now().second
        trap_seconds = [2, 17, 32, 47]
        for ts in trap_seconds:
            if abs(current_second - ts) <= 2:
                return True
        return False

    def can_open_order(self) -> bool:
        """Check if we can open a new order (global lock: 1 at a time)."""
        return not self.active_order

    def set_order_active(self):
        """Mark that an order is currently active."""
        self.active_order = True

    def set_order_closed(self):
        """Mark that the active order has closed."""
        self.active_order = False

    def get_stats(self) -> dict:
        """Get current protection stats for dashboard."""
        return {
            "daily_wins": self.daily_wins,
            "daily_losses": self.daily_losses,
            "sequential_losses": self.sequential_losses,
            "is_paused": self.is_paused(),
            "bot_stopped": self.bot_stopped,
            "paused_until": self.paused_until.isoformat() if self.paused_until else None,
            "active_order": self.active_order,
            "total_trades": len(self.trade_history),
            "win_rate": (self.daily_wins / max(1, self.daily_wins + self.daily_losses)) * 100
        }
