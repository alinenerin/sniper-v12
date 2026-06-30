import numpy as np


def ema(closes, period):
    """Calculate Exponential Moving Average."""
    closes = np.array(closes, dtype=float)
    if len(closes) < period:
        return np.full_like(closes, np.nan)
    alpha = 2.0 / (period + 1)
    ema_values = np.zeros_like(closes, dtype=float)
    ema_values[0] = closes[0]
    for i in range(1, len(closes)):
        ema_values[i] = alpha * closes[i] + (1 - alpha) * ema_values[i - 1]
    return ema_values


def macd(closes, fast=12, slow=26, signal=9):
    """Calculate MACD line, signal line, and histogram."""
    closes = np.array(closes, dtype=float)
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def rsi(closes, period=14):
    """Calculate RSI using Wilder's smoothing."""
    closes = np.array(closes, dtype=float)
    if len(closes) < period + 1:
        return 50.0  # neutral default

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def bollinger_bands(closes, period=20, std_mult=2.0):
    """Calculate Bollinger Bands. Returns (upper, middle, lower, width)."""
    closes = np.array(closes, dtype=float)
    if len(closes) < period:
        return None, None, None, None

    sma = np.mean(closes[-period:])
    std_dev = np.std(closes[-period:])
    upper = sma + std_dev * std_mult
    lower = sma - std_dev * std_mult
    width = (upper - lower) / sma if sma != 0 else 0
    return upper, sma, lower, width


def atr(highs, lows, closes, period=14):
    """Calculate Average True Range."""
    highs = np.array(highs, dtype=float)
    lows = np.array(lows, dtype=float)
    closes = np.array(closes, dtype=float)

    if len(highs) < period + 1:
        return 0.0

    tr = np.zeros(len(highs) - 1)
    for i in range(1, len(highs)):
        tr[i - 1] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )

    if len(tr) < period:
        return np.mean(tr) if len(tr) > 0 else 0.0

    atr_val = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr_val = (atr_val * (period - 1) + tr[i]) / period
    return atr_val


def adx(highs, lows, closes, period=14):
    """Calculate Average Directional Index."""
    highs = np.array(highs, dtype=float)
    lows = np.array(lows, dtype=float)
    closes = np.array(closes, dtype=float)

    if len(highs) < period * 2:
        return 0.0

    plus_dm = np.zeros(len(highs))
    minus_dm = np.zeros(len(highs))
    tr = np.zeros(len(highs))

    for i in range(1, len(highs)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )

    # Smooth with Wilder's method
    smooth_tr = np.sum(tr[1:period + 1])
    smooth_plus = np.sum(plus_dm[1:period + 1])
    smooth_minus = np.sum(minus_dm[1:period + 1])

    dx_values = []
    for i in range(period + 1, len(highs)):
        smooth_tr = smooth_tr - (smooth_tr / period) + tr[i]
        smooth_plus = smooth_plus - (smooth_plus / period) + plus_dm[i]
        smooth_minus = smooth_minus - (smooth_minus / period) + minus_dm[i]

        if smooth_tr == 0:
            continue
        plus_di = 100 * smooth_plus / smooth_tr
        minus_di = 100 * smooth_minus / smooth_tr

        di_sum = plus_di + minus_di
        if di_sum == 0:
            continue
        dx = 100 * abs(plus_di - minus_di) / di_sum
        dx_values.append(dx)

    if len(dx_values) < period:
        return np.mean(dx_values) if dx_values else 0.0

    adx_val = np.mean(dx_values[:period])
    for i in range(period, len(dx_values)):
        adx_val = (adx_val * (period - 1) + dx_values[i]) / period
    return adx_val


def check_ema_cascade(closes, periods=None):
    """Check EMA cascade alignment. Returns 'CALL', 'PUT', or None."""
    if periods is None:
        periods = [7, 9, 21, 50]
    closes = np.array(closes, dtype=float)

    if len(closes) < max(periods):
        return None

    ema_values = [ema(closes, p)[-1] for p in periods]

    # CALL: price > EMA7 > EMA9 > EMA21 > EMA50
    if closes[-1] > ema_values[0] and all(ema_values[i] > ema_values[i + 1] for i in range(len(ema_values) - 1)):
        return "CALL"
    # PUT: price < EMA7 < EMA9 < EMA21 < EMA50
    elif closes[-1] < ema_values[0] and all(ema_values[i] < ema_values[i + 1] for i in range(len(ema_values) - 1)):
        return "PUT"
    return None


def check_ema200_block(closes):
    """Check if price is against EMA200 (too close or crossing)."""
    closes = np.array(closes, dtype=float)
    if len(closes) < 200:
        return False

    ema200 = ema(closes, 200)[-1]
    current_price = closes[-1]
    # Block if price is within 0.05% of EMA200
    threshold = ema200 * 0.0005
    return abs(current_price - ema200) < threshold


def markov_probability(closes, lookback=50):
    """Calculate Markov chain transition probability. Returns (direction, probability)."""
    closes = np.array(closes, dtype=float)
    if len(closes) < lookback + 1:
        return None, 0.0

    recent = closes[-(lookback + 1):]
    # States: 0=down, 1=up
    states = (np.diff(recent) > 0).astype(int)

    # Build transition matrix
    transitions = np.zeros((2, 2))
    for i in range(len(states) - 1):
        transitions[states[i], states[i + 1]] += 1

    # Normalize
    for i in range(2):
        row_sum = transitions[i].sum()
        if row_sum > 0:
            transitions[i] /= row_sum

    current_state = states[-1]
    prob_up = transitions[current_state, 1]
    prob_down = transitions[current_state, 0]

    if prob_up > prob_down:
        return "CALL", prob_up
    elif prob_down > prob_up:
        return "PUT", prob_down
    else:
        return None, 0.5


def shadow_rejection(open_price, high, low, close, threshold=0.35):
    """Check if candle has excessive wick (shadow rejection).
    Returns True if wick > threshold * body size."""
    body = abs(close - open_price)
    if body == 0:
        body = 0.00001  # avoid division by zero

    upper_wick = high - max(open_price, close)
    lower_wick = min(open_price, close) - low

    max_wick = max(upper_wick, lower_wick)
    return max_wick > (body * threshold)


def bb_squeeze(closes, period=20, std_mult=2.0, avg_periods=50):
    """Check if Bollinger Band width is squeezed (< 50% of average width)."""
    closes = np.array(closes, dtype=float)
    if len(closes) < max(period, avg_periods):
        return False

    widths = []
    for i in range(avg_periods):
        idx = len(closes) - avg_periods + i
        if idx < period:
            continue
        segment = closes[idx - period:idx]
        sma = np.mean(segment)
        std_dev = np.std(segment)
        w = (2 * std_mult * std_dev) / sma if sma != 0 else 0
        widths.append(w)

    if not widths:
        return False

    avg_width = np.mean(widths)
    current_width = widths[-1] if widths else 0

    return current_width < (avg_width * 0.5)


def check_exhaustion(closes, consecutive=5):
    """Check if there are N+ consecutive candles in same direction."""
    closes = np.array(closes, dtype=float)
    if len(closes) < consecutive + 1:
        return False

    recent = closes[-(consecutive + 1):]
    diffs = np.diff(recent)

    all_up = all(d > 0 for d in diffs)
    all_down = all(d < 0 for d in diffs)

    return all_up or all_down
