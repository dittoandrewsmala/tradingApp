from collections import deque
import numpy as np

class strategy:
    def __init__(self):
        self.prices = deque(maxlen=100)
        self.volumes = deque(maxlen=30)
        
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
        self.cooldown_seconds = 60  # Increased cooldown to avoid over-trading churn
        self.trades = []
        self.pnl = 0

        self.last_price = None
        self.avg_gain = None
        self.avg_loss = None
        self.rsi = None

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
            rs = self.avg_gain / self.avg_loss
            self.rsi = 100.0 - (100.0 / (1.0 + rs))
        self.last_price = current_price

    def detect_scenario(self, price, vwap, volume, prev_price):
        if len(self.prices) < 25 or len(self.volumes) < 15: 
            return "NO_TRADE"

        ema_gap = abs(self.ema9 - self.ema21)
        # UPGRADE 1: Require a much larger directional spread between EMAs to filter chop
        min_gap = price * 0.0004  
        
        # UPGRADE 2: Quantify volume expansion (current volume must exceed average volume by 20%)
        avg_volume = sum(self.volumes) / len(self.volumes)
        volume_spike = volume > (avg_volume * 1.2)

        bullish_trend = self.ema9 > self.ema21 and price > vwap and ema_gap > min_gap
        bearish_trend = self.ema9 < self.ema21 and price < vwap and ema_gap > min_gap

        if bullish_trend and volume_spike:
            # High probability trigger zone for momentum
            if self.rsi is not None and 50 <= self.rsi <= 68 and price > self.ema9:
                return "BUY"

        if bearish_trend and volume_spike:
            # High probability short zone
            if self.rsi is not None and 32 <= self.rsi <= 50 and price < self.ema9:
                return "SELL"

        return "NO_TRADE"

    def on_candle(self, candle, current_time):
        price = candle["close"]
        volume = candle["volume"]
        prev_price = self.prev_price
        self.prev_price = price
        
        self.prices.append(price)
        self.volumes.append(volume)
        self.calculate_rsi(price)

        if self.ema9 is None:
            self.ema9 = price
            self.ema21 = price
        else:
            self.ema9 = price * self.k9 + self.ema9 * (1 - self.k9)
            self.ema21 = price * self.k21 + self.ema21 * (1 - self.k21)
        
        # Handle day resets for VWAP tracking safely
        today = current_time.date() if hasattr(current_time, 'date') else "LIVE"
        if self.current_day is None: self.current_day = today
        if today != self.current_day:
            self.total_pv = 0
            self.total_volume = 0
            self.current_day = today

        self.total_pv += price * volume
        self.total_volume += volume
        vwap = self.total_pv / self.total_volume
        
        if len(self.prices) < 21: return None

        # Check exits first
        exit_signal = self.check_exit(price, current_time)
        if exit_signal:
            return {"action": "EXIT", "reason": exit_signal, "price": price, "time": current_time}

        # Cooldown check
        if self.last_trade_time and (current_time - self.last_trade_time).total_seconds() < self.cooldown_seconds:
            return None

        # Entry logic
        if self.position is None:
            scenario = self.detect_scenario(price, vwap, volume, prev_price)
            if scenario in ["BUY", "SELL"]:
                self.enter(price, scenario, current_time)
                return {"action": scenario, "price": price, "time": current_time}

        return None

    def enter(self, price, side, current_time):
        self.position = side
        self.entry_price = price
        self.last_trade_time = current_time
        
        # Standardize strict targets based on volatility bands
        recent_prices = list(self.prices)[-10:-1]
        volatility = max(recent_prices) - min(recent_prices) if recent_prices else 3.0
        risk_distance = max(min(volatility, 5.0), 2.0) 
        
        if side == "BUY":
            self.stoploss = price - risk_distance
            self.target = price + (risk_distance * 1.5)  # Balanced R:R ratio for optimal high-win rate mathematical expectancy
            self.highest_price_since_entry = price
        else:
            self.stoploss = price + risk_distance
            self.target = price - (risk_distance * 1.5)
            self.lowest_price_since_entry = price

    def check_exit(self, current_price, current_time):
        if self.position is None: return None

        if self.position == "BUY":
            if current_price <= self.stoploss:
                return self.exit(current_price, "STOPLOSS HIT", current_time)
            if current_price >= self.target:
                return self.exit(current_price, "TARGET HIT", current_time)
            
            # UPGRADE 3: Protect profits using a noise-tolerant trailing stop instead of cutting at exact EMA9 cross
            if current_price > self.highest_price_since_entry:
                self.highest_price_since_entry = current_price
                # Trail stop loss upward dynamically
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
        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.last_trade_time = current_time
        return reason
    def reset_position(self):
        self.position = None
        self.entry_price = None
        self.target = None
        self.stoploss = None
        self.highest_price_since_entry = None
        self.lowest_price_since_entry = None