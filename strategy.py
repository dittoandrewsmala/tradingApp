from collections import deque
import config
from logger import Logger

logger = Logger()

class Strategy:

    def __init__(self):

        self.prices = deque(maxlen=200)

        # EMA values
        self.ema9 = None
        self.ema21 = None

        # EMA multipliers
        self.k9 = 2 / (9 + 1)
        self.k21 = 2 / (21 + 1)

        # VWAP approximation
        self.total_price = 0
        self.total_ticks = 0

        # Previous EMA for crossover
        self.prev_ema9 = None
        self.prev_ema21 = None

        # Position state
        self.position = None
        self.entry_price = None


    def signal(self, price):

        self.prices.append(price)

        if len(self.prices) < config.MIN_CANDLES:
            return None

        # ---------------- EMA CALCULATION ----------------
        if self.ema9 is None:
            self.ema9 = price
            self.ema21 = price
        else:
            self.ema9 = (price * self.k9) + (self.ema9 * (1 - self.k9))
            self.ema21 = (price * self.k21) + (self.ema21 * (1 - self.k21))

        # ---------------- VWAP APPROX ----------------
        self.total_price += price
        self.total_ticks += 1
        vwap = self.total_price / self.total_ticks

        signal = None

        # ---------------- ENTRY ----------------
        if self.position is None:

            if self.prev_ema9 is not None and self.prev_ema21 is not None:

                bullish_cross = self.prev_ema9 <= self.prev_ema21 and self.ema9 > self.ema21
                bearish_cross = self.prev_ema9 >= self.prev_ema21 and self.ema9 < self.ema21

                if bullish_cross and price > vwap:
                    self.position = "LONG"
                    self.entry_price = price
                    logger.printD(f"BUY @ {price}")
                    #self.prices.clear()
                    signal = "BUY"

                elif bearish_cross and price < vwap:
                    self.position = "SHORT"
                    self.entry_price = price
                    logger.printD(f"SELL @ {price}")
                    #self.prices.clear()
                    signal = "SELL"

        # ---------------- EXIT ----------------
        """ else:

            if self.position == "LONG" and self.ema9 < self.ema21:
                logger.printD(f"EXIT LONG @ {price}")
                self.reset()
                signal = "EXIT"

            elif self.position == "SHORT" and self.ema9 > self.ema21:
                logger.printD(f"EXIT SHORT @ {price}")
                self.reset()
                signal = "EXIT" """

        # store previous
        self.prev_ema9 = self.ema9
        self.prev_ema21 = self.ema21

        return signal


    def reset(self):

        self.position = None
        self.entry_price = None