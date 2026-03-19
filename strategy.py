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
        self.cooldown_seconds = 60

    # ---------------------------------------------------
    def signal(self, price, volume=1):
    # ---------------------------------------------------

        now = datetime.now()
        signal = None

        # Store price
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

        # ---------------- EXIT FIRST ----------------
        if self.position is not None:

            # LONG EXIT
            if self.position == "LONG":

                # Trailing SL
                if price > self.entry_price:
                    self.stop_loss = max(self.stop_loss, price * 0.85)

                if price <= self.stop_loss:
                    logger.printD(f"SL HIT LONG @ {price}")
                    self.reset()
                    return "EXIT"

                elif price >= self.target:
                    logger.printD(f"TARGET HIT LONG @ {price}")
                    self.reset()
                    return "EXIT"

            # SHORT EXIT
            elif self.position == "SHORT":

                if price < self.entry_price:
                    self.stop_loss = min(self.stop_loss, price * 1.15)

                if price >= self.stop_loss:
                    logger.printD(f"SL HIT SHORT @ {price}")
                    self.reset()
                    return "EXIT"

                elif price <= self.target:
                    logger.printD(f"TARGET HIT SHORT @ {price}")
                    self.reset()
                    return "EXIT"

        

        # Store previous EMA
        self.prev_ema9 = self.ema9
        self.prev_ema21 = self.ema21

        return signal

    # ---------------------------------------------------
    def reset(self):
    # ---------------------------------------------------
        self.position = None
        self.entry_price = None
        self.stop_loss = None
        self.target = None