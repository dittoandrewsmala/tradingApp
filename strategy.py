from collections import deque
from datetime import datetime
import config
from logger import Logger

logger = Logger()


class Strategy:

    def __init__(self):

        self.prices = deque(maxlen=200)

        self.ema9 = None
        self.ema21 = None
        self.prev_ema9 = None
        self.prev_ema21 = None

        self.k9 = 2 / (9 + 1)
        self.k21 = 2 / (21 + 1)

        self.total_pv = 0
        self.total_volume = 0

        self.position = None
        self.last_trade_time = None
        self.cooldown_seconds = 30   # faster reaction

        self.trend_threshold = 0.02  # reduced
        self.min_range = 1.5         # reduced

    # ---------------------------------------------------
    def signal(self, price, volume=1):
    # ---------------------------------------------------

        now = datetime.now()
        self.prices.append(price)

        if len(self.prices) < config.MIN_CANDLES:
            return None

        # EMA
        if self.ema9 is None:
            self.ema9 = price
            self.ema21 = price
        else:
            self.ema9 = (price * self.k9) + (self.ema9 * (1 - self.k9))
            self.ema21 = (price * self.k21) + (self.ema21 * (1 - self.k21))

        # VWAP
        self.total_pv += price * volume
        self.total_volume += volume
        vwap = self.total_pv / self.total_volume if self.total_volume else price

        # Range filter
        if (max(self.prices) - min(self.prices)) < self.min_range:
            return None

        # Cooldown
        if self.last_trade_time:
            if (now - self.last_trade_time).seconds < self.cooldown_seconds:
                return None

        bullish = self.ema9 > self.ema21
        bearish = self.ema9 < self.ema21

        cross_up = False
        cross_down = False

        if self.prev_ema9 is not None and self.prev_ema21 is not None:
            cross_up = self.prev_ema9 <= self.prev_ema21 and bullish
            cross_down = self.prev_ema9 >= self.prev_ema21 and bearish

        trend_strength = abs(self.ema9 - self.ema21)

        signal = None

        if self.position is None:

            # LONG (relaxed VWAP)
            if (cross_up or (bullish and trend_strength > self.trend_threshold)) and price >= vwap * 0.995:

                self.position = "LONG"
                self.last_trade_time = now

                logger.printD(f"BUY @ {price}")
                signal = "BUY"

            # SHORT
            elif (cross_down or (bearish and trend_strength > self.trend_threshold)) and price <= vwap * 1.005:

                self.position = "SHORT"
                self.last_trade_time = now

                logger.printD(f"SELL @ {price}")
                signal = "SELL"

        self.prev_ema9 = self.ema9
        self.prev_ema21 = self.ema21

        return signal

    def reset_position(self):
        self.position = None