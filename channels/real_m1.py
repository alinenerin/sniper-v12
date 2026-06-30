import logging
import numpy as np
from .base_channel import BaseChannel
from indicators import technical as ind

logger = logging.getLogger(__name__)


class RealM1Channel(BaseChannel):
    """Channel 3 — REAL M1
    
    Cycle: 57s | Expiration: 1 min | Min score: 70
    Indicators:
    - EMA cascade M1 → price>EMA7>EMA9>EMA21>EMA50 = CALL
    - EMA200 macro → price against EMA200 = BLOCK
    - ATR tiny → current ATR <50% of 14p avg = blocks
    - Exhaustion → 5+ consecutive = blocks
    - RSI(14) → >70 penalizes CALL (-20pts) | <30 penalizes PUT
    - Shadow Rejection → wick >40% = VETO
    - M5 filter → price against EMA21 on M5 = BLOCK
    - DXY correlation → divergence with USD pair = BLOCK
    - Markov → divergence = VETO | HIGH = +10pts
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="REAL_M1",
            cycle=57,
            expiration=1,
            min_score=70,
            timeframe=60,
            **kwargs
        )

    def _analyze_pair(self, pair: str) -> dict:
        """Analyze pair using REAL M1 strategy."""
        data = self._get_candle_data(pair, count=250)  # Need 200+ for EMA200
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

        # --- SHADOW REJECTION (wick > 40% = VETO) ---
        if ind.shadow_rejection(last["open"], last["high"], last["low"], last["close"], threshold=0.40):
            return None  # VETO

        # --- EMA CASCADE ---
        cascade_dir = ind.check_ema_cascade(closes, periods=[7, 9, 21, 50])
        if cascade_dir is None:
            return None  # No clear trend

        direction = cascade_dir
        score += 20

        # --- EMA200 MACRO BLOCK ---
        if len(closes) >= 200:
            if ind.check_ema200_block(closes):
                return None  # Price at EMA200 = total block

            # Additional: price against EMA200 direction
            ema200 = ind.ema(closes, 200)[-1]
            if direction == "CALL" and closes[-1] < ema200:
                return None  # CALL but price below EMA200 = BLOCK
            elif direction == "PUT" and closes[-1] > ema200:
                return None  # PUT but price above EMA200 = BLOCK

        # --- ATR TINY ---
        atr_current = ind.atr(highs[-15:], lows[-15:], closes[-15:], period=14)
        atr_avg = ind.atr(highs[-30:], lows[-30:], closes[-30:], period=14)
        if atr_avg > 0 and atr_current < (atr_avg * 0.5):
            return None  # Block - no volatility
        else:
            score += 10

        # --- EXHAUSTION CHECK ---
        if ind.check_exhaustion(closes, consecutive=5):
            return None  # Block - too many consecutive candles

        # --- RSI(14) ---
        rsi_value = ind.rsi(closes, period=14)
        if direction == "CALL" and rsi_value > 70:
            score -= 20  # Penalize
        elif direction == "PUT" and rsi_value < 30:
            score -= 20  # Penalize
        else:
            score += 10

        # --- M5 FILTER ---
        # Get M5 candles for the same pair
        m5_candles = self.iq.get_candles(pair, 300, 30)
        if m5_candles and len(m5_candles) >= 21:
            m5_closes = np.array([c["close"] for c in m5_candles], dtype=float)
            ema21_m5 = ind.ema(m5_closes, 21)[-1]
            if direction == "CALL" and m5_closes[-1] < ema21_m5:
                return None  # Price below EMA21 on M5 = BLOCK for CALL
            elif direction == "PUT" and m5_closes[-1] > ema21_m5:
                return None  # Price above EMA21 on M5 = BLOCK for PUT

        # --- DXY CORRELATION ---
        if self.twelve_data:
            if not self.twelve_data.check_dxy_confluence(pair, direction):
                return None  # DXY divergence = BLOCK

        # --- MARKOV ---
        markov_dir, markov_prob = ind.markov_probability(closes, lookback=50)
        if markov_dir is not None:
            if markov_dir != direction and markov_prob >= 0.58:
                return None  # Divergence = VETO
            elif markov_dir == direction and markov_prob >= 0.6:
                score += 10  # High confluence

        # --- CHECK MINIMUM SCORE ---
        if score >= self.min_score:
            return {
                "pair": pair,
                "direction": direction,
                "score": score,
                "channel": self.name
            }

        return None
