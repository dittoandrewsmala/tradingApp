from collections import deque
from datetime import datetime

# ================= LOGGER =================

class Logger:
    def printD(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

logger = Logger()

# ================= CONFIG =================

class Config:
    MIN_CANDLES = 15

config = Config()

# ================= CANDLE BUILDER =================

class CandleBuilder:

    def __init__(self, interval_sec=60):
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

            self.current = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume
            }

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

            self.current["high"] = max(
                self.current["high"],
                price
            )

            self.current["low"] = min(
                self.current["low"],
                price
            )

            self.current["close"] = price
            self.current["volume"] += volume

        return None


# ================= STRATEGY =================

class Strategy:

    def __init__(self):

        self.prices = deque(maxlen=100)
        self.volumes = deque(maxlen=30)

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

        self.cooldown_seconds = 60

        self.trades = []
        self.pnl = 0

        # RSI

        self.rsi_period = 14
        self.gains = deque(maxlen=self.rsi_period)
        self.losses = deque(maxlen=self.rsi_period)
        self.rsi = None

    # ================= RSI =================

    def calculate_rsi(self):

        if len(self.prices) < 2:
            return

        change = self.prices[-1] - self.prices[-2]

        gain = max(change, 0)
        loss = abs(min(change, 0))

        self.gains.append(gain)
        self.losses.append(loss)

        if len(self.gains) < self.rsi_period:
            return

        avg_gain = sum(self.gains) / self.rsi_period
        avg_loss = sum(self.losses) / self.rsi_period

        if avg_loss == 0:
            self.rsi = 100
            return

        rs = avg_gain / avg_loss

        self.rsi = 100 - (100 / (1 + rs))

    # ================= SCENARIO =================

    def detect_scenario(self, price, vwap, volume):

        if len(self.prices) < 10:
            return "NO_TRADE", 0, 0

        recent = list(self.prices)[-6:-1]

        recent_high = max(recent)
        recent_low = min(recent)
        logger.printD(
        f"DISTANCE_TO_HIGH={recent_high-price:.2f} "
        f"DISTANCE_TO_LOW={price-recent_low:.2f}"
        )

        bullish = self.ema9 >= self.ema21
        bearish = self.ema9 <= self.ema21

        breakout = price >= (recent_high + 0.5)
        breakdown = price <= (recent_low - 0.5)

        momentum = price - recent[0]

        avg_volume = (
            sum(self.volumes) / len(self.volumes)
            if len(self.volumes) > 0
            else volume
        )

        volume_ok = volume >= (avg_volume * 0.90)

        logger.printD(
            f"High={recent_high:.2f} "
            f"Low={recent_low:.2f} "
            f"Price={price:.2f} "
            f"EMA_DIFF={(self.ema9-self.ema21):.4f}"
        )

        logger.printD(
            f"bullish={bullish} "
            f"bearish={bearish} "
            f"price>=vwap={price >= vwap} "
            f"breakout={breakout} "
            f"breakdown={breakdown} "
            f"momentum={momentum:.2f} "
            f"volume={volume} "
            f"avg_volume={avg_volume:.2f} "
            f"volume_ok={volume_ok} "
            f"rsi={self.rsi}"
        )

        rsi_buy_ok = (
            self.rsi is not None and
            self.rsi > 55
        )

        rsi_sell_ok = (
            self.rsi is not None and
            self.rsi < 45
        )
        reasons = []

        if not bullish:
            reasons.append("EMA")

        if not (price >= vwap):
            reasons.append("VWAP")

        if not breakout:
            reasons.append("BREAKOUT")

        if not volume_ok:
            reasons.append("VOLUME")

        if not rsi_buy_ok:
            reasons.append("RSI")

        logger.printD(
            f"BUY BLOCKERS: {reasons if reasons else 'NONE'}"
        )
        if (
            bullish and
            price >= vwap and
            breakout and
            volume_ok and
            rsi_buy_ok
        ):
            return "BULLISH_BREAKOUT", recent_high, recent_low

        elif (
            bearish and
            price <= vwap and
            breakdown and
            volume_ok and
            rsi_sell_ok
        ):
            return "BEARISH_BREAKDOWN", recent_high, recent_low

        return "NO_TRADE", recent_high, recent_low

    # ================= MAIN =================

    def on_candle(self, candle):

        now = datetime.now()

        price = candle["close"]
        volume = candle["volume"]

        self.prices.append(price)
        self.volumes.append(volume)

        self.calculate_rsi()

        # EMA warm-up immediately

        if self.ema9 is None:

            self.ema9 = price
            self.ema21 = price

        else:

            self.ema9 = (
                price * self.k9 +
                self.ema9 * (1 - self.k9)
            )

            self.ema21 = (
                price * self.k21 +
                self.ema21 * (1 - self.k21)
            )

        # VWAP

        self.total_pv += price * volume
        self.total_volume += volume

        vwap = self.total_pv / self.total_volume
        
        if len(self.prices) < config.MIN_CANDLES:
            return None


        logger.printD(
            f"P={price:.2f} "
            f"EMA9={self.ema9:.2f} "
            f"EMA21={self.ema21:.2f} "
            f"VWAP={vwap:.2f} "
            f"RSI={self.rsi if self.rsi else 0:.2f}"
        )

        if (
            self.last_trade_time and
            (now - self.last_trade_time).seconds <
            self.cooldown_seconds
        ):
            return None

        scenario, high, low = self.detect_scenario(
            price,
            vwap,
            volume
        )

        logger.printD(
            f"SCENARIO -> {scenario}"
        )

        if self.position is None:

            if scenario == "BULLISH_BREAKOUT":

                logger.printD(
                    f"BUY SIGNAL @ {price}"
                )

                return f"{price}BUY"

            elif scenario == "BEARISH_BREAKDOWN":

                logger.printD(
                    f"SELL SIGNAL @ {price}"
                )

                return f"{price}SELL"

            else:

                logger.printD(
                    f"NO TRADE ZONE "
                    f"{low:.2f}-{high:.2f}"
                )

        return None

    # ================= ENTRY =================

    def enter(self, price, side):

        self.position = side
        self.entry_price = price

        self.last_trade_time = datetime.now()

        if side == "BUY":

            self.target = price + 2
            self.stoploss = price - 2

        else:

            self.target = price - 2
            self.stoploss = price + 2

        logger.printD(
            f"ENTRY {side} @ {price}"
        )

    # ================= EXIT =================

    def exit(self, price, reason):

        pnl = (
            price - self.entry_price
            if self.position == "BUY"
            else self.entry_price - price
        )

        self.pnl += pnl
        self.trades.append(pnl)

        logger.printD(
            f"EXIT {reason} "
            f"@ {price} "
            f"PnL={pnl:.2f}"
        )

        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None

        self.last_trade_time = datetime.now()

        return reason

    # ================= POSITION CHECK =================

    def check_exit(self, current_price):

        if self.position is None:
            return None

        if self.position == "BUY":

            if current_price >= self.target:
                return self.exit(
                    current_price,
                    "TARGET HIT"
                )

            if current_price <= self.stoploss:
                return self.exit(
                    current_price,
                    "STOPLOSS HIT"
                )

        else:

            if current_price <= self.target:
                return self.exit(
                    current_price,
                    "TARGET HIT"
                )

            if current_price >= self.stoploss:
                return self.exit(
                    current_price,
                    "STOPLOSS HIT"
                )

        return None
    def reset_position(self):

        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.last_trade_time = None
        logger.printD(
            "POSITION RESET"
         )