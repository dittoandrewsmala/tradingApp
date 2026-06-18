from collections import deque
import numpy as np
import pytz
from datetime import datetime, time, timezone

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

    def update(self, price, volume, open, low, high, close):
        now = datetime.now(pytz.timezone("Asia/Kolkata"))
        bucket = int(now.timestamp() // self.interval)

        if self.last_bucket is None:
            self.last_bucket = bucket

        if bucket != self.last_bucket:
            finished = self.current

            self.current = {
                "open": open ,
                "high": high ,
                "low": low ,
                "close": close ,
                "volume": volume
            }

            self.last_bucket = bucket
            if finished:
                return finished

        if self.current is None:
            self.current = {
                "open": open ,
                "high": high ,
                "low": low ,
                "close": close,
                "volume": volume
            }
        else:
            self.current["high"] = max(self.current["high"], price)
            self.current["low"] = min(self.current["low"], price)
            self.current["close"] = price
            self.current["volume"] += volume

        return None


# ================= STRATEGY =================

class strategy:  # Kept lowercase to maintain synchronization with main.py & Order.py
    def __init__(self):
        self.prices = deque(maxlen=100)
        
        # O(1) RSI Tracker
        self.rsi_period = 14
        self.rsi_seed_count = 0
        self.seed_gain_sum = 0.0
        self.seed_loss_sum = 0.0
        
        # EMAs
        self.ema9 = None
        self.ema21 = None
        self.k9 = 2 / (9 + 1)
        self.k21 = 2 / (21 + 1)
        self.prev_price = None
        
        # VWAP
        self.total_pv = 0
        self.total_volume = 0
        self.current_day = None
        
        # Trade Status
        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.highest_price_since_entry = None
        self.lowest_price_since_entry = None
        
        self.last_trade_time = None
        self.cooldown_seconds = 60  
        self.trades = []
        self.pnl = 0

        self.last_price = None
        self.avg_gain = None
        self.avg_loss = None
        self.rsi = None
        self.candles = deque(maxlen=100)

    def calculate_rsi(self, current_price):
        if self.last_price is None:
            self.last_price = current_price
            return
        
        change = current_price - self.last_price
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))

        if self.avg_gain is None:
            self.seed_gain_sum += gain
            self.seed_loss_sum += loss
            self.rsi_seed_count += 1
            if self.rsi_seed_count < self.rsi_period:
                self.last_price = current_price
                return
            self.avg_gain = self.seed_gain_sum / self.rsi_period
            self.avg_loss = self.seed_loss_sum / self.rsi_period
        else:
            self.avg_gain = (self.avg_gain * (self.rsi_period - 1) + gain) / self.rsi_period
            self.avg_loss = (self.avg_loss * (self.rsi_period - 1) + loss) / self.rsi_period

        if self.avg_loss == 0:
            self.rsi = 100.0
        else:
            self.rs = self.avg_gain / self.avg_loss
            self.rsi = 100.0 - (100.0 / (1.0 + self.rs))
            
        self.last_price = current_price

    def _log_diagnostics(self, price, vwap):
        """Prints out a complete, scannable breakdown of criteria evaluation."""
        ema_gap = abs(self.ema9 - self.ema21) if (self.ema9 and self.ema21) else 0
        min_gap = price * 0.0001
        
        
        # Check specific filters
        ema_bullish = self.ema9 > self.ema21 if (self.ema9 and self.ema21) else False
        ema_bearish = self.ema9 < self.ema21 if (self.ema9 and self.ema21) else False
        
        

    def detect_scenario(self, price, vwap):
        if len(self.prices) < 25: 
            return "NO_TRADE"

        if self.rsi is None:
            return "NO_TRADE"

        ema_gap = abs(self.ema9 - self.ema21)
        min_gap = price * 0.0001  
        
        bullish_trend = self.ema9 > self.ema21 and price > vwap and ema_gap > min_gap
        bearish_trend = self.ema9 < self.ema21 and price < vwap and ema_gap > min_gap

        if bullish_trend:
            if self.rsi >= 55 and price > self.ema9:
                return "BUY"

        if bearish_trend:
            if self.rsi <= 45 and price < self.ema9:
                return "SELL"

        self._log_diagnostics(price, vwap)
        return "NO_TRADE"

    def on_candle(self, candle, current_time):
        price = candle["close"]
        volume = candle["volume"]
        self.candles.append(candle)
        self.prices.append(price)
        self.calculate_rsi(price)

        if self.ema9 is None:
            self.ema9 = price
            self.ema21 = price
        else:
            self.ema9 = price * self.k9 + self.ema9 * (1 - self.k9)
            self.ema21 = price * self.k21 + self.ema21 * (1 - self.k21)
        
        today = current_time.date() if hasattr(current_time, 'date') else "LIVE"
        if self.current_day is None: 
            self.current_day = today
        if today != self.current_day:
            self.total_pv = 0
            self.total_volume = 0
            self.current_day = today

        self.total_pv += price * volume
        self.total_volume += volume
        vwap = self.total_pv / self.total_volume
        
        # Synchronize lookback limits with detect_scenario (25 candles minimum)
        if len(self.prices) < 25: 
            print(f"[WARMUP] Queue building: {len(self.prices)}/25 prices collected.")
            return None

        exit_signal = self.check_exit(price, current_time)
        if exit_signal:
            return {"action": "EXIT", "reason": exit_signal, "price": price, "time": current_time}

        if self.last_trade_time and (current_time - self.last_trade_time).total_seconds() < self.cooldown_seconds:
            return None

        if self.position is None:
            scenario = self.detect_scenario(price, vwap)
            if scenario in ["BUY", "SELL"]:
                self.enter(price, scenario, current_time)
                return {"action": scenario, "price": price, "time": current_time}

        return None

    def enter(self, price, side, current_time):
        self.position = side
        self.entry_price = price
        self.last_trade_time = current_time
        
        recent_prices = list(self.prices)[-10:-1]
        volatility = max(recent_prices) - min(recent_prices) if recent_prices else 3.0
        risk_distance = max(min(volatility, 5.0), 2.0) 
        
        if side == "BUY":
            self.stoploss = price - risk_distance
            self.target = price + (risk_distance * 1.5)  
            self.highest_price_since_entry = price
            # print(f"\n[TRADE ENTERED] Long at {price:.2f} | SL: {self.stoploss:.2f} | Target: {self.target:.2f}\n")
        else:
            self.stoploss = price + risk_distance
            self.target = price - (risk_distance * 1.5)
            self.lowest_price_since_entry = price
            # print(f"\n[TRADE ENTERED] Short at {price:.2f} | SL: {self.stoploss:.2f} | Target: {self.target:.2f}\n")

    def check_exit(self, current_price, current_time):
        if self.position is None: 
            return None

        if self.position == "BUY":
            if current_price <= self.stoploss:
                return self.exit(current_price, "STOPLOSS HIT", current_time)
            if current_price >= self.target:
                return self.exit(current_price, "TARGET HIT", current_time)
            
            if current_price > self.highest_price_since_entry:
                self.highest_price_since_entry = current_price
                new_sl = current_price - (abs(self.entry_price - self.stoploss) * 0.6)
                if new_sl > self.stoploss:
                    self.stoploss = new_sl

        elif self.position == "SELL":
            if current_price >= self.stoploss:
                return self.exit(current_price, "STOPLOSS HIT", current_time)
            if current_price <= self.target:
                return self.exit(current_price, "TARGET HIT", current_time)
            
            if current_price < self.lowest_price_since_entry:
                self.lowest_price_since_entry = current_price
                new_sl = current_price + (abs(self.stoploss - self.entry_price) * 0.6)
                if new_sl < self.stoploss:
                    self.stoploss = new_sl

        return None

    def exit(self, price, reason, current_time):
        pnl = (price - self.entry_price) if self.position == "BUY" else (self.entry_price - price)
        self.pnl += pnl
        self.trades.append(pnl)
        
        # print(f"[TRADE CLOSED] Exit Reason: {reason} at {price:.2f} | Trade PnL: {pnl:.2f} | Cum. PnL: {self.pnl:.2f}\n")
        
        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.last_trade_time = current_time
        return reason
    def reset(self):
        self.prices = deque(maxlen=100)
        self.candles = deque(maxlen=100)
        # O(1) RSI Tracker
        self.rsi_period = 14
        self.rsi_seed_count = 0
        self.seed_gain_sum = 0.0
        self.seed_loss_sum = 0.0
        
        # EMAs
        self.ema9 = None
        self.ema21 = None
        self.k9 = 2 / (9 + 1)
        self.k21 = 2 / (21 + 1)
        self.prev_price = None
        
        # VWAP
        self.total_pv = 0
        self.total_volume = 0
        self.current_day = None
        
        # Trade Status
        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.highest_price_since_entry = None
        self.lowest_price_since_entry = None
        
        self.last_trade_time = None
        self.cooldown_seconds = 60  
        self.trades = []
        self.pnl = 0

        self.last_price = None
        self.avg_gain = None
        self.avg_loss = None
        self.rsi = None
    