import logging
import numpy as np
from .base_channel import BaseChannel
from indicators import technical as ind

logger = logging.getLogger(__name__)


class RealM5Channel(BaseChannel):
    """Channel 4 — REAL M5
    
    Cycle: 290s | Expiration: 5 min | Min score: 75
    Indicators:
    - EMA cascade M5 → EMA9>EMA21>EMA50 = CALL
    - ATR M5 → current ≥60% avg
    - RSI(14) → >72 / <28 blocks
    - M15 macro (proxy) → 15 M5 candles = 75min trend
    - DXY mandatory → no confluence = -25pts
    - Shadow Rejection → wick >35% = VETO
    - Markov → prob <58% = VETO
    - M1×M5 Conflict → opposite directions = M5 wins
    """

    def __init__(self, m1_channel=None, **kwargs):
        super().__init__(
            name="REAL_M5",
            cycle=290,
            expiration=5,
            min_score=75,
            timeframe=300,
            **kwargs
        )
        self.m1_channel = m1_channel  # Reference to REAL_M1

    def _analyze_pair(self, pair: str) -> dict:
        """Analyze pair using REAL M5 strategy."""
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

        # --- SHADOW REJECTION (wick > 35% = VETO) ---
        if ind.shadow_rejection(last["open"], last["high"], last["low"], last["close"], threshold=0.35):
            return None  # VETO

        # --- EMA CASCADE M5 ---
        cascade_dir = ind.check_ema_cascade(closes, periods=[9, 21, 50])
        if cascade_dir is None:
            return None  # No clear trend

        direction = cascade_dir
        score += 20

        # --- ATR M5 ---
        atr_current = ind.atr(highs[-15:], lows[-15:], closes[-15:], period=14)
        atr_avg = ind.atr(highs[-30:], lows[-30:], closes[-30:], period=14)
        if atr_avg > 0 and atr_current < (atr_avg * 0.6):
            return None  # Block - ATR too low
        else:
            score += 15

        # --- RSI(14) ---
        rsi_value = ind.rsi(closes, period=14)
        if rsi_value > 72 and direction == "CALL":
            return None  # Block
        elif rsi_value < 28 and direction == "PUT":
            return None  # Block
        else:
            score += 10

        # --- M15 MACRO (proxy: 15 M5 candles = 75min trend) ---
        if len(closes) >= 15:
            macro_closes = closes[-15:]
            macro_trend_up = macro_closes[-1] > macro_closes[0]
            macro_trend_down = macro_closes[-1] < macro_closes[0]

            if direction == "CALL" and macro_trend_up:
                score += 15
            elif direction == "PUT" and macro_trend_down:
                score += 15
            elif direction == "CALL" and macro_trend_down:
                score -= 10  # Against macro trend
            elif direction == "PUT" and macro_trend_up:
                score -= 10

        # --- DXY MANDATORY ---
        if self.twelve_data:
            if not self.twelve_data.check_dxy_confluence(pair, direction):
                score -= 25  # No confluence = -25pts (not a block, but heavy penalty)
        else:
            score -= 25  # Can't check DXY = penalty

        # --- MARKOV ---
        markov_dir, markov_prob = ind.markov_probability(closes, lookback=50)
        if markov_dir is not None:
            if markov_prob < 0.58:
                return None  # VETO
            if markov_dir == direction:
                score += 15
            else:
                return None  # Divergence = VETO

        # --- M1×M5 CONFLICT ---
        if self.m1_channel and self.m1_channel.last_signal:
            m1_signal = self.m1_channel.last_signal
            if m1_signal.get("pair") == pair:
                m1_direction = m1_signal.get("direction")
                if m1_direction and m1_direction != direction:
                    # M5 wins in conflict, but log it
                    logger.info(f"{self.name}: M1×M5 conflict on {pair}, M5 direction wins")

        # --- CHECK MINIMUM SCORE ---
        if score >= self.min_score:
            return {
                "pair": pair,
                "direction": direction,
                "score": score,
                "channel": self.name
            }

        return None
