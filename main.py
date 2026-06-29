from collections import deque
from datetime import datetime, time, timezone
import logging
import sys
import pytz

import config
from broker import Broker
from logger import Logger
from Postion import Position 
from risk_manager import RiskManager
from strategy import strategy, CandleBuilder
from trade_manager import TradeManager
from websocket_feed import MarketFeed

logger = Logger()

# Initialize components
broker = Broker()
broker.login()
position = Position()
nifty_token = broker.get_nifty_token()

# Global Strategy Management Variables
CANDLE_TIME_FRAME = 5
builder = CandleBuilder(CANDLE_TIME_FRAME)
risk = RiskManager()
trade = TradeManager(broker, risk)

isTradeActive = False
lotIndex = 0
signalStarted = False
ord_numer = None

# --- Strategy Optimization Parameters ---
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 55
RSI_SELL_THRESHOLD = 45

EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
ATR_PERIOD = 14

MAX_LOOKBACK_CANDLES = 3  # Wait max 3 candles for pullback confirmation

# Unified history tracking (Needs at least 50+ to compute EMA50 reliably)
candle_history = deque(maxlen=100) 

# Persistent memory state machine tracking
active_setup = None    # Options: None, "BUY_STREAK_CONFIRMED", "SELL_STREAK_CONFIRMED"
setup_timer = 0        # Tracks how many candles remain before a setup expires
pullback_trigger_level = None  # Stores the high/low reference to break for entry

if not signalStarted:
    logger.printD("🚀 Starting signal generation with Trend & Pullback rules...")
    signalStarted = True
    choice = input("Do want to give index value ? ").strip()
    if choice.lower() == "yes":
        lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())


def calculate_rsi(history):
    """Calculates standard RSI using candle history."""
    if len(history) < RSI_PERIOD + 1:
        return 50.0
        
    gains = []
    losses = []
    
    for i in range(1, len(history)):
        change = history[i]['close'] - history[i-1]['close']
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
            
    avg_gain = sum(gains[-RSI_PERIOD:]) / RSI_PERIOD
    avg_loss = sum(losses[-RSI_PERIOD:]) / RSI_PERIOD
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def calculate_ema(history, period):
    """Calculates Exponential Moving Average (EMA) from close prices."""
    if len(history) < period:
        return history[-1]['close'] if history else 0.0
    
    closes = [c['close'] for c in history]
    # Seed with SMA
    ema = sum(closes[:period]) / period
    multiplier = 2 / (period + 1)
    
    for close_price in closes[period:]:
        ema = (close_price - ema) * multiplier + ema
    return ema


def calculate_atr(history, period=14):
    """Calculates Average True Range (ATR)."""
    if len(history) < period + 1:
        return history[-1]['high'] - history[-1]['low'] if history else 1.0
        
    true_ranges = []
    for i in range(1, len(history)):
        h = history[i]['high']
        l = history[i]['low']
        pc = history[i-1]['close']
        tr = max(h - l, abs(h - pc), abs(l - pc))
        true_ranges.append(tr)
        
    # Standard SMA of True Range for simplicity
    return sum(true_ranges[-period:]) / period


def on_tick(price, volume, open, low, high, close):
    global signalStarted, lotIndex, isTradeActive, ord_numer, active_setup, setup_timer, pullback_trigger_level
    
    candle = builder.update(price, 1, open, low, high, close)
    
    if candle:
        if candle_history:
            last_candle_sig = (candle_history[-1]['open'], candle_history[-1]['high'], candle_history[-1]['low'])
            new_candle_sig = (candle['open'], candle['high'], candle['low'])
            
            if last_candle_sig == new_candle_sig:
                candle_history[-1] = candle 
            else:
                candle_history.append(candle)
                if active_setup is not None:
                    setup_timer -= 1
                    if setup_timer <= 0:
                        print("⏱️ Pullback tracking window expired without entry. Resetting setup.")
                        active_setup = None
                        pullback_trigger_level = None
        else:
            candle_history.append(candle)

    # Need enough data for the filters (especially EMA50)
    if len(candle_history) >= EMA_SLOW_PERIOD and not isTradeActive:
        
        # Calculate Technical Indicators
        current_rsi = calculate_rsi(list(candle_history))
        ema20 = calculate_ema(list(candle_history), EMA_FAST_PERIOD)
        ema50 = calculate_ema(list(candle_history), EMA_SLOW_PERIOD)
        atr = calculate_atr(list(candle_history), ATR_PERIOD)
        
        # Reference past completed candles
        c1 = candle_history[-1]   # Current active/forming candle
        c2 = candle_history[-2]   # Last fully closed candle
        c3 = candle_history[-3]
        c4 = candle_history[-4]
        c5 = candle_history[-5]
        c6 = candle_history[-6]   # 5th closed candle back
        
        condition = None
        
        # --- STEP 1: Scan for Fresh 5-Candle Trend Streaks ---
        if active_setup is None:
            is_bullish_streak = (c2["close"] > c2["open"] and 
                                 c3["close"] > c3["open"] and 
                                 c4["close"] > c4["open"] and 
                                 c5["close"] > c5["open"] and 
                                 c6["close"] > c6["open"])
                                 
            is_bearish_streak = (c2["close"] < c2["open"] and 
                                 c3["close"] < c3["open"] and 
                                 c4["close"] < c4["open"] and 
                                 c5["close"] < c5["open"] and 
                                 c6["close"] < c6["open"])
            
            # Optional ATR filter: Ensures streak movement is significant relative to volatility
            streak_move_valid = True
            if hasattr(config, 'ATR_MULTIPLIER'):
                streak_move_valid = abs(c2["close"] - c6["open"]) > (config.ATR_MULTIPLIER * atr)
            elif hasattr(config, 'CANDLE_DIFF'):
                streak_move_valid = abs(c2["close"] - c6["close"]) >= config.CANDLE_DIFF

            # Evaluate BUY Setup
            if is_bullish_streak and streak_move_valid and current_rsi > RSI_BUY_THRESHOLD and ema20 > ema50:
                active_setup = "BUY_STREAK_CONFIRMED"
                setup_timer = MAX_LOOKBACK_CANDLES
                # Pullback high trigger: we track the highest point of the pullback phase to break out of
                pullback_trigger_level = c1["high"] 
                print(f"🔥 BUY Setup Confirmed! (RSI: {current_rsi:.1f}, EMA20 > EMA50). Waiting for pullback break high...")

            # Evaluate SELL Setup
            elif is_bearish_streak and streak_move_valid and current_rsi < RSI_SELL_THRESHOLD and ema20 < ema50:
                active_setup = "SELL_STREAK_CONFIRMED"
                setup_timer = MAX_LOOKBACK_CANDLES
                # Pullback low trigger: we track the lowest point of the pullback phase to breakdown from
                pullback_trigger_level = c1["low"]
                print(f"🔥 SELL Setup Confirmed! (RSI: {current_rsi:.1f}, EMA20 < EMA50). Waiting for pullback break low...")
                
        # --- STEP 2: Handle Active Setup and Breakout Triggers ---
        elif active_setup == "BUY_STREAK_CONFIRMED":
            # Update the pullback high if current price continues pulling back/forming bars
            if c1["high"] < pullback_trigger_level:
                pullback_trigger_level = c1["high"]
            
            # Entry Trigger: Price breaks above the current pullback high
            if price > pullback_trigger_level:
                condition = "BUY"
                active_setup = None
                pullback_trigger_level = None

        elif active_setup == "SELL_STREAK_CONFIRMED":
            # Update the pullback low if current price continues bouncing up
            if c1["low"] > pullback_trigger_level:
                pullback_trigger_level = c1["low"]
            
            # Entry Trigger: Price breaks below the current pullback low
            if price < pullback_trigger_level:
                condition = "SELL"
                active_setup = None
                pullback_trigger_level = None

        # --- STEP 3: Broker Execution Handler ---
        if condition is None:
            return
            
        trade.session_token = broker.session
        print(f"🚦 Order Sent: {condition} | Entry Price: {price} | RSI: {current_rsi:.2f}")
        
        isTradeActive = True
        ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex)
        
        if profitOrLoss in ["PROFIT", "LOSS"]:
            active_setup=None
            setup_timer=0
            pullback_trigger_level=None
                
        if profitOrLoss == "PROFIT":
             lotIndex = 0
        elif profitOrLoss == "LOSS":
             lotIndex += 1
             
        if ord_numer is not None:
            isTradeActive = False
            ord_numer = None


feed = MarketFeed(
    session_token=broker.session,
    symbol_token=nifty_token,
    callback=on_tick
)
feed.start()