from collections import deque
from datetime import datetime
import time
import random

# ================= LOGGER =================
class Logger:
    def printD(self, msg):
         print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

logger = Logger()

# ================= CONFIG =================
class Config:
    MIN_CANDLES = 10

config = Config()

# ================= CANDLE BUILDER =================
class CandleBuilder:

    def __init__(self, interval_sec=2):
        self.interval = interval_sec
        self.current = None
        self.last_bucket = None

    def update(self, price, volume=1):
        now = datetime.now()
        bucket = int(now.timestamp() // self.interval)

        if self.last_bucket is None:
            self.last_bucket = bucket

        if bucket != self.last_bucket:
            finished = self.current
            self.current = None
            self.last_bucket = bucket
            return finished

        if self.current is None:
            self.current = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume
            }
        else:
            self.current["high"] = max(self.current["high"], price)
            self.current["low"] = min(self.current["low"], price)
            self.current["close"] = price
            self.current["volume"] += volume

        return None

# ================= STRATEGY =================
class Strategy:

    def __init__(self):

        self.prices = deque(maxlen=100)

        self.ema9 = None
        self.ema21 = None

        self.k9 = 2 / (9 + 1)
        self.k21 = 2 / (21 + 1)

        self.total_pv = 0
        self.total_volume = 0

        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None

        self.last_trade_time = None

        self.cooldown_seconds = 3
        self.max_hold_seconds = 40

        self.min_range = 0.05

        self.trades = []
        self.pnl = 0

    # ================= SCENARIO =================
    def detect_scenario(self, price, vwap):
        recent = list(self.prices)[-5:]
        recent_high = max(recent)
        recent_low = min(recent)

        bullish = self.ema9 > self.ema21
        bearish = self.ema9 < self.ema21

        breakout = price >= recent_high
        breakdown = price <= recent_low

        momentum = price - recent[0]

        if bullish and price > vwap and breakout and momentum > 0:
            return "BULLISH_BREAKOUT", recent_high, recent_low

        elif bearish and price < vwap and breakdown and momentum < 0:
            return "BEARISH_BREAKDOWN", recent_high, recent_low

        else:
            return "NO_TRADE", recent_high, recent_low

    # ================= MAIN =================
    def on_candle(self, candle):

        now = datetime.now()
        price = candle["close"]
        volume = candle["volume"]

        self.prices.append(price)

        if len(self.prices) < config.MIN_CANDLES:
            return None

        # EMA
        if self.ema9 is None:
            self.ema9 = price
            self.ema21 = price
        else:
            self.ema9 = price * self.k9 + self.ema9 * (1 - self.k9)
            self.ema21 = price * self.k21 + self.ema21 * (1 - self.k21)

        # VWAP
        self.total_pv += price * volume
        self.total_volume += volume
        vwap = self.total_pv / self.total_volume

        logger.printD(f"P={price:.2f} EMA9={self.ema9:.2f} EMA21={self.ema21:.2f} VWAP={vwap:.2f}")

        # # EXIT LOGIC
        # if self.position:
        #     if self.position == "BUY":
        #         if price >= self.target:
        #             return self.exit(price, "TARGET HIT")
        #         if price <= self.stoploss:
        #             return self.exit(price, "STOPLOSS HIT")

        #     elif self.position == "SELL":
        #         if price <= self.target:
        #             return self.exit(price, "TARGET HIT")
        #         if price >= self.stoploss:
        #             return self.exit(price, "STOPLOSS HIT")

        #     if (now - self.last_trade_time).seconds > self.max_hold_seconds:
        #         return self.exit(price, "TIME EXIT")

        # FILTERS
        if self.last_trade_time and (now - self.last_trade_time).seconds < self.cooldown_seconds:
            return None

        # SCENARIO
        scenario, high, low = self.detect_scenario(price, vwap)
        logger.printD(f"SCENARIO → {scenario}")

        if self.position is None:

            if scenario == "BULLISH_BREAKOUT":
                return  str(price)+"BUY"

            elif scenario == "BEARISH_BREAKDOWN":
                return str(price)+"SELL"

            else:
                logger.printD(f"⛔ NO TRADE ZONE {low}-{high}")

        return None

    def enter(self, price, side):
        self.position = side
        self.entry_price = price
        self.last_trade_time = datetime.now()

        if side == "BUY":
            self.target = price + 0.20
            self.stoploss = price - 0.10
        else:
            self.target = price - 0.20
            self.stoploss = price + 0.10

        logger.printD(f"🚀 {side} @ {price} | T={self.target} SL={self.stoploss}")
        return side

    def exit(self, price, reason):
        pnl = price - self.entry_price if self.position == "BUY" else self.entry_price - price
        self.pnl += pnl
        self.trades.append(pnl)

        logger.printD(f"❌ {reason} @ {price} | PnL={pnl:.2f} | Total={self.pnl:.2f}")

        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.last_trade_time = datetime.now()

        return reason

    def reset_position(self):
        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.last_trade_time = None
        self.prices = deque(maxlen=100)
        logger.printD("🔄 Position reset")

