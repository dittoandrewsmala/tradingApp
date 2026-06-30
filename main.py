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
CANDLE_TIME_FRAME = 10
builder = CandleBuilder(CANDLE_TIME_FRAME)
risk = RiskManager()
trade = TradeManager(broker, risk)

isTradeActive = False
lotIndex = 0
signalStarted = False
ord_numer = None

# --- Strategy Optimization Parameters ---
EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
MAX_LOOKBACK_CANDLES = 4  # Maximum candles to wait for a pullback confirmation

# Increased queue maxlen to accommodate computing the 50 EMA accurately
candles = deque(maxlen=100) 

# Persistent memory state machine tracking
active_setup = None   # Options: None, "BUY_STREAK_CONFIRMED", "SELL_STREAK_CONFIRMED"
setup_timer = 0       # Tracks how many candles remain before a setup expires
current_candle_open = None  # Safely preserves the entry anchor price point

if not signalStarted:
    logger.printD("🚀 Starting signal generation with EMA filters...")
    signalStarted = True
    choice = input("Do want to give index value ? ").strip()
    if choice.lower() == "yes":
        lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())


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


def on_tick(price, volume, open, low, high, close):
    global signalStarted, lotIndex, isTradeActive, ord_numer, active_setup, setup_timer, current_candle_open
    
    candle = builder.update(price, 1, open, low, high, close)
    
    if candle:
        # Check if a new candle has officially started
        is_new_candle = False
        if candles:
            last_candle_sig = (candles[-1]['open'], candles[-1]['high'], candles[-1]['low'])
            new_candle_sig = (candle['open'], candle['high'], candle['low'])
            
            if last_candle_sig == new_candle_sig:
                candles[-1] = candle  # Update current live candle
            else:
                candles.append(candle) # Append new closed candle to history
                is_new_candle = True
        else:
            candles.append(candle)
            is_new_candle = True

        # Keep track of the opening level of the current running candle
        current_candle_open = candle["open"]

        # Handle expiration timers only when a bar transitions/closes
        if is_new_candle and active_setup is not None:
            setup_timer -= 1
            if setup_timer <= 0:
                print("⏱️ Pullback tracking window expired without confirmation. Resetting setup.")
                active_setup = None

    # Ensure we have enough data history to calculate the indicators
    if len(candles) >= EMA_SLOW_PERIOD and not isTradeActive:
        
        # Calculate Moving Averages
        ema20 = calculate_ema(list(candles), EMA_FAST_PERIOD)
        ema50 = calculate_ema(list(candles), EMA_SLOW_PERIOD)
        
        # Reference past fully completed historic bars cleanly
        c2 = candles[-2]   # Last fully closed candle
        c3 = candles[-3]
        c4 = candles[-4]
        c5 = candles[-5]
        c6 = candles[-6]   # 5th closed candle back
        
        condition = None
        
        # --- STEP 1: Scan for fresh streaks ONLY if we aren't already tracking one ---
        if active_setup is None:
            is_bullish_streak = (c2["close"] > c3["close"] > c4["close"] > c5["close"] > c6["close"]) and (c2["close"] - c6["close"] >= config.CANDLE_DIFF)
            is_bearish_streak = (c2["close"] < c3["close"] < c4["close"] < c5["close"] < c6["close"]) and (c6["close"] - c2["close"] >= config.CANDLE_DIFF)
            
            if is_bullish_streak:
                active_setup = "BUY_STREAK_CONFIRMED"
                setup_timer = MAX_LOOKBACK_CANDLES
                print(f"🔥 Bullish Streak Confirmed! Waiting for confirmation bounce. EMA20: {ema20:.2f} | EMA50: {ema50:.2f}")
            elif is_bearish_streak:
                active_setup = "SELL_STREAK_CONFIRMED"
                setup_timer = MAX_LOOKBACK_CANDLES
                print(f"🔥 Bearish Streak Confirmed! Waiting for confirmation breakdown. EMA20: {ema20:.2f} | EMA50: {ema50:.2f}")
                
        # --- STEP 2: Persistent Evaluation of the Trigger Loop (With EMA Checks) ---
        # Safeguard anchor value if tick calculation starts before candle initialization complete
        anchor_price = current_candle_open if current_candle_open is not None else candles[-1]["open"]

        if active_setup == "BUY_STREAK_CONFIRMED":
            # Valid confirmation bounce: price moving above the candle's opening level
            if price > anchor_price: 
                if ema20 > ema50:
                    condition = "BUY"
                    active_setup = None  # Reset tracking state machine
                else:
                    print(f"⚠️ BUY blocked. Trend is not Bullish (EMA20: {ema20:.2f} <= EMA50: {ema50:.2f})")
                    active_setup = None

        elif active_setup == "SELL_STREAK_CONFIRMED":
            # Valid confirmation bounce: price dropping below the candle's opening level
            if price < anchor_price:
                if ema20 < ema50:
                    condition = "SELL"
                    active_setup = None  # Reset tracking state machine
                else:
                    print(f"⚠️ SELL blocked. Trend is not Bearish (EMA20: {ema20:.2f} >= EMA50: {ema50:.2f})")
                    active_setup = None

        # --- STEP 3: Broker Execution Handler ---
        if condition is None:
            return
            
        trade.session_token = broker.session
        print(f"🚦 Execution Verification Cleared: Sending {condition} Signal to Broker | EMA20: {ema20:.2f} vs EMA50: {ema50:.2f}")
        
        isTradeActive = True
        ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex)
        
        # FIX: Resetting memory state without clearing candle data 
        if profitOrLoss in ["PROFIT", "LOSS"]:
            active_setup = None
            setup_timer = 0
            
                
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