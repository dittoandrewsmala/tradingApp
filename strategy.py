from collections import deque
from datetime import datetime
import config
from logger import Logger

logger = Logger()


class Strategy:

    def __init__(self):

        # ---------------- PRICE DATA ----------------
        self.prices = deque(maxlen=200)

        # ---------------- EMA ----------------
        self.ema9 = None
        self.ema21 = None
        self.prev_ema9 = None
        self.prev_ema21 = None

        self.k9 = 2 / (9 + 1)
        self.k21 = 2 / (21 + 1)

        # ---------------- VWAP ----------------
        self.total_pv = 0
        self.total_volume = 0

        # ---------------- POSITION ----------------
        self.position = None
        self.entry_price = None
        self.last_trade_time = None

        # ---------------- CONFIG ----------------
        self.cooldown_seconds = 30
        self.max_hold_seconds = 300   # 5 min timeout

        self.min_range = 1.5

    # ---------------------------------------------------
    # CHOPPY MARKET FILTER
    # ---------------------------------------------------
    def is_choppy(self, price, vwap):

        if len(self.prices) < 20 or self.ema9 is None or self.ema21 is None:
            return False

        range_val = max(self.prices) - min(self.prices)
        low_range = range_val < price * 0.0015   # 0.15%

        ema_spread = abs(self.ema9 - self.ema21)
        weak_trend = ema_spread < price * 0.0004

        near_vwap = abs(price - vwap) / price < 0.0008

        return low_range and weak_trend and near_vwap

    # ---------------------------------------------------
    def signal(self, price, volume=1):
    # ---------------------------------------------------

        now = datetime.now()
        self.prices.append(price)

        if len(self.prices) < config.MIN_CANDLES:
            return None

        # ---------------- EMA UPDATE ----------------
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

        # =====================================================
        # 🔴 EXIT LOGIC (ALWAYS FIRST)
        # =====================================================
        if self.position is not None:

            exit_signal = None

            # ---------- TREND REVERSAL ----------
            if self.position == "LONG" and self.ema9 < self.ema21:
                exit_signal = "EXIT_LONG"

            elif self.position == "SHORT" and self.ema9 > self.ema21:
                exit_signal = "EXIT_SHORT"

            # ---------- VWAP EXIT ----------
            elif self.position == "LONG" and price < vwap:
                exit_signal = "EXIT_LONG"

            elif self.position == "SHORT" and price > vwap:
                exit_signal = "EXIT_SHORT"

            # ---------- STOP LOSS (0.5%) ----------
            elif self.position == "LONG" and price < self.entry_price * 0.995:
                exit_signal = "SL_LONG"

            elif self.position == "SHORT" and price > self.entry_price * 1.005:
                exit_signal = "SL_SHORT"

            # ---------- TIME EXIT ----------
            elif (now - self.last_trade_time).seconds > self.max_hold_seconds:
                exit_signal = f"TIME_EXIT_{self.position}"

            if exit_signal:
                logger.printD(f"{exit_signal} @ {price}")
                self.reset_position()
                return exit_signal

        # ---------------- CHOPPY FILTER ----------------
        if self.is_choppy(price, vwap):
            logger.printD("CHOPPY - SKIP")
            return None

        # ---------------- RANGE FILTER ----------------
        if (max(self.prices) - min(self.prices)) < self.min_range:
            return None

        # ---------------- COOLDOWN ----------------
        if self.last_trade_time:
            if (now - self.last_trade_time).seconds < self.cooldown_seconds:
                return None

        # ---------------- TREND ----------------
        bullish = self.ema9 > self.ema21
        bearish = self.ema9 < self.ema21

        cross_up = False
        cross_down = False

        if self.prev_ema9 is not None and self.prev_ema21 is not None:
            cross_up = self.prev_ema9 <= self.prev_ema21 and bullish
            cross_down = self.prev_ema9 >= self.prev_ema21 and bearish

        trend_strength = abs(self.ema9 - self.ema21)

        signal = None

        # =====================================================
        # 🟢 ENTRY LOGIC
        # =====================================================
        if self.position is None:

            # LONG ENTRY
            if (cross_up or (bullish and trend_strength > price * 0.0005)) and price >= vwap * 0.995:

                self.position = "LONG"
                self.entry_price = price
                self.last_trade_time = now

                logger.printD(f"BUY @ {price}")
                signal = "BUY"

            # SHORT ENTRY
            elif (cross_down or (bearish and trend_strength > price * 0.0005)) and price <= vwap * 1.005:

                self.position = "SHORT"
                self.entry_price = price
                self.last_trade_time = now

                logger.printD(f"SELL @ {price}")
                signal = "SELL"

        # ---------------- STORE PREV EMA ----------------
        self.prev_ema9 = self.ema9
        self.prev_ema21 = self.ema21

        return signal

    # ---------------------------------------------------
    def reset_position(self):
    # ---------------------------------------------------

        self.position = None
        self.entry_price = None

        self.prices.clear()

        self.ema9 = None
        self.ema21 = None
        self.prev_ema9 = None
        self.prev_ema21 = None

        self.total_pv = 0
        self.total_volume = 0

        # cooldown control
        self.last_trade_time = datetime.now()