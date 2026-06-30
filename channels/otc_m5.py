import logging
import numpy as np
from .base_channel import BaseChannel
from indicators import technical as ind

logger = logging.getLogger(__name__)


class OtcM5Channel(BaseChannel):
    """Channel 2 — OTC M5
    
    Cycle: 290s | Expiration: 5 min | Min score: 160
    Indicators:
    - MACD(8,21,5) → longer periods = less noise
    - RSI(14) → >65 / <35 blocks
    - BB squeeze → width <50% avg = blocks
    - Shadow Rejection → wick >30% = VETO
    - Markov → prob <58% = VETO
    - M1×M5 Conflict → opposite directions = BOTH BLOCKED
    - Trap Zones → :02 :17 :32 :47 = VETO
    """

    def __init__(self, m1_channel=None, **kwargs):
        super().__init__(
            name="OTC_M5",
            cycle=290,
            expiration=5,
            min_score=160,
            timeframe=300,
            **kwargs
        )
        self.m1_channel = m1_channel  # Reference to OTC_M1 for conflict check

    def _analyze_pair(self, pair: str) -> dict:
        """Analyze pair using OTC M5 strategy."""
        data = self._get_candle_data(pair, count=100)
        if data is None:
            return None

        closes = data["closes"]
        highs = data["highs"]
        lows = data["lows"]
        opens = data["opens"]
        last = data["last_candle"]

        score = 0
        direction = None

        # --- TRAP ZONE CHECK ---
        if self.protections.check_trap_zone():
            return None

        # --- SHADOW REJECTION (wick > 30% = VETO) ---
        if ind.shadow_rejection(last["open"], last["high"], last["low"], last["close"], threshold=0.30):
            return None  # VETO

        # --- MACD(8,21,5) ---
        macd_line, signal_line, histogram = ind.macd(closes, fast=8, slow=21, signal=5)
        if len(histogram) > 1:
            if histogram[-1] > 0 and histogram[-2] <= 0:
                direction = "CALL"
                score += 40
            elif histogram[-1] < 0 and histogram[-2] >= 0:
                direction = "PUT"
                score += 40
            elif histogram[-1] > 0:
                direction = "CALL"
                score += 25
            elif histogram[-1] < 0:
                direction = "PUT"
                score += 25

        if direction is None:
            return None

        # --- RSI(14) ---
        rsi_value = ind.rsi(closes, period=14)
        if rsi_value > 65 and direction == "CALL":
            return None  # Block
        elif rsi_value < 35 and direction == "PUT":
            return None  # Block
        elif 40 <= rsi_value <= 60:
            score += 30
        elif (direction == "CALL" and rsi_value < 45) or (direction == "PUT" and rsi_value > 55):
            score += 35

        # --- BB SQUEEZE ---
        if ind.bb_squeeze(closes, period=20, std_mult=2.0, avg_periods=50):
            return None  # Block - no volatility

        # BB position bonus
        upper, middle, lower, width = ind.bollinger_bands(closes, period=20, std_mult=2.0)
        if upper is not None and width is not None:
            score += 30  # Normal BB width

        # --- MARKOV ---
        markov_dir, markov_prob = ind.markov_probability(closes, lookback=50)
        if markov_dir is not None:
            if markov_prob < 0.58:
                return None  # VETO - probability too low
            if markov_dir == direction:
                score += 30
            else:
                return None  # Divergence = VETO

        # --- M1×M5 CONFLICT CHECK ---
        if self.m1_channel and self.m1_channel.last_signal:
            m1_signal = self.m1_channel.last_signal
            # Check if M1 signal is recent (within last 2 minutes)
            if m1_signal.get("pair") == pair:
                m1_direction = m1_signal.get("direction")
                if m1_direction and m1_direction != direction:
                    return None  # Opposite directions = BOTH BLOCKED

        # --- CHECK MINIMUM SCORE ---
        if score >= self.min_score:
            return {
                "pair": pair,
                "direction": direction,
                "score": score,
                "channel": self.name
            }

        return None
