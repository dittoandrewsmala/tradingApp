from collections import deque
from datetime import datetime, timedelta
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

        # VWAP (REAL)
        self.total_pv = 0
        self.total_volume = 0

        # Position state
        self.position = None
        self.entry_price = None
        self.stop_loss = None
        self.target = None

        # Trade control
        self.last_trade_time = None
        self.cooldown_seconds = 60   # avoid overtrading

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

        # ---------------- REAL VWAP ----------------
        self.total_pv += price * volume
        self.total_volume += volume
        vwap = self.total_pv / self.total_volume if self.total_volume else price

        signal = None

        # ---------------- COOLDOWN ----------------
        if self.last_trade_time:
            if (now - self.last_trade_time).seconds < self.cooldown_seconds:
                return None

        # ---------------- ENTRY ----------------
        if self.position is None:

            if self.prev_ema9 is not None and self.prev_ema21 is not None:

                bullish_cross = self.prev_ema9 <= self.prev_ema21 and self.ema9 > self.ema21
                bearish_cross = self.prev_ema9 >= self.prev_ema21 and self.ema9 < self.ema21

                # LONG ENTRY
                if bullish_cross and price > vwap:
                    self.position = "LONG"
                    self.entry_price = price

                    # Risk management
                    self.stop_loss = price * 0.8      # 20% SL (options)
                    self.target = price * 1.4         # 40% target

                    self.last_trade_time = now

                    logger.printD(f"BUY @ {price}")
                    signal = "BUY"

                # SHORT ENTRY
                elif bearish_cross and price < vwap:
                    self.position = "SHORT"
                    self.entry_price = price

                    self.stop_loss = price * 1.2
                    self.target = price * 0.6

                    self.last_trade_time = now

                    logger.printD(f"SELL @ {price}")
                    signal = "SELL"

        

        # store previous EMA
        self.prev_ema9 = self.ema9
        self.prev_ema21 = self.ema21
        self.reset() 
        return signal

    # ---------------------------------------------------
    def reset(self):
    # ---------------------------------------------------
        self.position = None
        self.entry_price = None
        self.stop_loss = None
        self.target = None
        self.prices.clear()