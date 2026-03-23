from collections import deque
from datetime import datetime
import config
from logger import Logger

logger = Logger()


class Strategy:

    def __init__(self):

        # Price buffer
        self.prices = deque(maxlen=200)

        # EMA values
        self.ema9 = None
        self.ema21 = None
        self.prev_ema9 = None
        self.prev_ema21 = None

        # EMA multipliers
        self.k9 = 2 / (9 + 1)
        self.k21 = 2 / (21 + 1)

        # VWAP
        self.total_pv = 0
        self.total_volume = 0

        # Position state
        self.position = None

        # Trade control
        self.last_trade_time = None
        self.cooldown_seconds = 60

        # Filters (tune these)
        self.min_range = 5              # avoid sideways
        self.trend_threshold = 0.2      # EMA strength

    # ---------------------------------------------------
    def signal(self, price, volume=1):
    # ---------------------------------------------------

        now = datetime.now()
        self.prices.append(price)

        if len(self.prices) < config.MIN_CANDLES:
            return None

        # ---------------- EMA ----------------
        if self.ema9 is None:
            self.ema9 = price
            self.ema21 = price
        else:
            self.ema9 = (price * self.k9) + (self.ema9 * (1 - self.k9))
            self.ema21 = (price * self.k21) + (self.ema21 * (1 - self.k21))

        # ---------------- VWAP ----------------
        self.total_pv += price * volume
        self.total_volume += volume
        vwap = self.total_pv / self.total_volume if self.total_volume else price

        # ---------------- RANGE FILTER ----------------
        if (max(self.prices) - min(self.prices)) < self.min_range:
            return None

        # ---------------- COOLDOWN ----------------
        if self.last_trade_time:
            if (now - self.last_trade_time).seconds < self.cooldown_seconds:
                return None

        signal = None

        # ---------------- ENTRY ----------------
        if self.position is None:

            if self.prev_ema9 is not None and self.prev_ema21 is not None:

                bullish_cross = self.prev_ema9 <= self.prev_ema21 and self.ema9 > self.ema21
                bearish_cross = self.prev_ema9 >= self.prev_ema21 and self.ema9 < self.ema21

                trend_strength = abs(self.ema9 - self.ema21)

                # LONG ENTRY
                if (bullish_cross and
                    price > vwap and
                    price > self.ema9 and
                    trend_strength > self.trend_threshold):

                    self.position = "LONG"
                    self.last_trade_time = now

                    logger.printD(f"BUY @ {price}")
                    signal = "BUY"

                # SHORT ENTRY
                elif (bearish_cross and
                      price < vwap and
                      price < self.ema9 and
                      trend_strength > self.trend_threshold):

                    self.position = "SHORT"
                    self.last_trade_time = now

                    logger.printD(f"SELL @ {price}")
                    signal = "SELL"

        # store previous EMA
        self.prev_ema9 = self.ema9
        self.prev_ema21 = self.ema21

        return signal

    # ---------------------------------------------------
    def reset_position(self):
    # ---------------------------------------------------
        """Call this after your order system exits"""
        self.position = None