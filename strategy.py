import pandas as pd
from collections import deque
import config
from logger import Logger

logger = Logger()

class Strategy:

    def __init__(self):
        self.prices = deque(maxlen=200)

        # Trade state
        self.position = None      # "LONG", "SHORT", or None
        self.entry_price = None

        # Store previous EMA values for crossover detection
        self.prev_ema9 = None
        self.prev_ema21 = None


    # ---------------------------------------
    # MAIN SIGNAL FUNCTION
    # ---------------------------------------
    def signal(self, price):

        self.prices.append(price)
        print("self.prices: "+ str(self.prices))
        print("self.prices length: "+ str(len(self.prices)))
        if len(self.prices) < config.MIN_CANDLES:
            return None
        print("signal starts")
        df = pd.DataFrame(list(self.prices), columns=["price"])

        # Indicators    
        ema9_series = df["price"].ewm(span=9, adjust=False).mean()
        ema21_series = df["price"].ewm(span=21, adjust=False).mean()

        ema9 = ema9_series.iloc[-1]
        ema21 = ema21_series.iloc[-1]

        # Simplified VWAP (tick-based approximation)
        vwap = df["price"].expanding().mean().iloc[-1]

        signal = None

        # ================= ENTRY LOGIC =================
        if self.position is None:

            # Detect bullish crossover
            if (self.prev_ema9 is not None and
                self.prev_ema21 is not None):

                bullish_cross = self.prev_ema9 <= self.prev_ema21 and ema9 > ema21
                bearish_cross = self.prev_ema9 >= self.prev_ema21 and ema9 < ema21

                # LONG ENTRY
                if bullish_cross and price > vwap:
                    self.position = "LONG"
                    self.entry_price = price
                    logger.printD(f"✅ BUY @ {price}")
                    signal = "BUY"

                # SHORT ENTRY
                elif bearish_cross and price < vwap:
                    self.position = "SHORT"
                    self.entry_price = price
                    logger.printD(f"❌ SELL @ {price}")
                    signal = "SELL"

        # ================= EXIT LOGIC =================
        """ else:

            # Exit LONG
            if self.position == "LONG" and ema9 < ema21:
                logger.printD(f"🔁 EXIT LONG @ {price}")
                self.reset()
                signal = "EXIT"

            # Exit SHORT
            elif self.position == "SHORT" and ema9 > ema21:
                logger.printD(f"🔁 EXIT SHORT @ {price}")
                self.reset()
                signal = "EXIT" """

        # Store previous EMA values
        self.prev_ema9 = ema9
        self.prev_ema21 = ema21

        return signal


    # ---------------------------------------
    # RESET TRADE STATE
    # ---------------------------------------
    def reset(self):
        self.position = None
        self.entry_price = None