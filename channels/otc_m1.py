import logging
import numpy as np
from .base_channel import BaseChannel
from indicators import technical as ind

logger = logging.getLogger(__name__)


class OtcM1Channel(BaseChannel):
    """Channel 1 — OTC M1
    
    Cycle: 57s | Expiration: 1 min | Min score: 150
    Indicators:
    - MACD(5,13,4) → crossover at zero line
    - ADX(14) → <18 blocks | 18-22 gray | >22 ok
    - Bollinger(20,2) → price in correct third
    - RSI(14) → >75 blocks CALL | <25 blocks PUT
    - Shadow Rejection → wick >35% = VETO
    - Markov → divergence = VETO | high = +10pts
    - Trap Zones → :02 :17 :32 :47 = VETO
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="OTC_M1",
            cycle=57,
            expiration=1,
            min_score=150,
            timeframe=60,
            **kwargs
        )

    def _analyze_pair(self, pair: str) -> dict:
        """Analyze pair using OTC M1 strategy."""
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
        veto = False

        # --- TRAP ZONE CHECK ---
        if self.protections.check_trap_zone():
            return None

        # --- SHADOW REJECTION (wick > 35% = VETO) ---
        if ind.shadow_rejection(last["open"], last["high"], last["low"], last["close"], threshold=0.35):
            return None  # VETO

        # --- MACD(5,13,4) ---
        macd_line, signal_line, histogram = ind.macd(closes, fast=5, slow=13, signal=4)
        if len(histogram) > 1:
            # Crossover detection
            if histogram[-1] > 0 and histogram[-2] <= 0:
                direction = "CALL"
                score += 40
            elif histogram[-1] < 0 and histogram[-2] >= 0:
                direction = "PUT"
                score += 40
            elif histogram[-1] > 0:
                direction = "CALL"
                score += 20
            elif histogram[-1] < 0:
                direction = "PUT"
                score += 20

        if direction is None:
            return None

        # --- ADX(14) ---
        adx_value = ind.adx(highs, lows, closes, period=14)
        if adx_value < 18:
            return None  # Block - no trend
        elif adx_value <= 22:
            score += 10  # Gray zone
        else:
            score += 30  # Good trend

        # --- BOLLINGER BANDS(20,2) ---
        upper, middle, lower, width = ind.bollinger_bands(closes, period=20, std_mult=2.0)
        if upper is not None:
            current_price = closes[-1]
            bb_range = upper - lower
            if bb_range > 0:
                position = (current_price - lower) / bb_range
                # CALL: price in lower third (0.0-0.33)
                # PUT: price in upper third (0.67-1.0)
                if direction == "CALL" and position < 0.33:
                    score += 30
                elif direction == "PUT" and position > 0.67:
                    score += 30
                elif direction == "CALL" and position < 0.5:
                    score += 15
                elif direction == "PUT" and position > 0.5:
                    score += 15

        # --- RSI(14) ---
        rsi_value = ind.rsi(closes, period=14)
        if direction == "CALL" and rsi_value > 75:
            return None  # Block CALL when overbought
        elif direction == "PUT" and rsi_value < 25:
            return None  # Block PUT when oversold
        elif 40 <= rsi_value <= 60:
            score += 20  # Neutral zone, good
        elif (direction == "CALL" and rsi_value < 40) or (direction == "PUT" and rsi_value > 60):
            score += 25  # Favorable RSI

        # --- MARKOV ---
        markov_dir, markov_prob = ind.markov_probability(closes, lookback=50)
        if markov_dir is not None:
            if markov_dir == direction:
                if markov_prob >= 0.6:
                    score += 10  # High confluence
                else:
                    score += 5
            else:
                # Divergence = VETO
                if markov_prob >= 0.6:
                    return None  # Strong divergence = VETO

        # --- CHECK MINIMUM SCORE ---
        if score >= self.min_score:
            return {
                "pair": pair,
                "direction": direction,
                "score": score,
                "channel": self.name
            }

        return None
