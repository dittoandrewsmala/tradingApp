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
RSI_PERIOD = 14
RSI_OVERBOUGHT = 65
RSI_OVERSOLD = 35
MAX_LOOKBACK_CANDLES = 4  # Maximum candles to wait for a pullback confirmation

rsi_candles = deque(maxlen=RSI_PERIOD + 1) 
candles = deque(maxlen=7) 

# Persistent memory state machine tracking
active_setup = None   # Options: None, "BUY_STREAK_CONFIRMED", "SELL_STREAK_CONFIRMED"
setup_timer = 0       # Tracks how many candles remain before a setup expires

if not signalStarted:
    logger.printD("🚀 Starting signal generation...")
    signalStarted = True
    choice = input("Do want to give index value ? ").strip()
    if choice.lower() == "yes":
        lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())


def calculate_rsi(candle_history):
    """Calculates standard RSI using a list of candle dicts."""
    if len(candle_history) < RSI_PERIOD + 1:
        return 50.0  # Default neutral midpoint structure
        
    gains = []
    losses = []
    
    for i in range(1, len(candle_history)):
        change = candle_history[i]['close'] - candle_history[i-1]['close']
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


def on_tick(price, volume, open, low, high, close):
    global signalStarted, lotIndex, isTradeActive, ord_numer, active_setup, setup_timer
    
    candle = builder.update(price, 1, open, low, high, close)
    
    if candle:
        # Prevent duplicate ticks from pushing identical candle data
        if candles:
            last_candle_sig = (candles[-1]['open'], candles[-1]['high'], candles[-1]['low'])
            new_candle_sig = (candle['open'], candle['high'], candle['low'])
            
            if last_candle_sig == new_candle_sig:
                candles[-1] = candle 
                rsi_candles[-1] = candle
            else:
                candles.append(candle)
                rsi_candles.append(candle)
                # Count down the validation window timer when a candle officially finishes
                if active_setup is not None:
                    setup_timer -= 1
                    if setup_timer <= 0:
                        print("⏱️ Pullback tracking window expired without confirmation. Resetting setup.")
                        active_setup = None
        else:
            candles.append(candle)
            rsi_candles.append(candle)

    # Validate historical queue depth
    if len(candles) >= 6 and not isTradeActive:
        
        current_rsi = calculate_rsi(list(rsi_candles))
        
        # Pull candle structures cleanly
        c1 = candles[-1]   # Present/Live active forming candle
        c2 = candles[-2]   # Prior closed candle
        c3 = candles[-3]
        c4 = candles[-4]
        c5 = candles[-5]
        c6 = candles[-6]   # Oldest check point
        
        condition = None
        
        # --- STEP 1: Scan for fresh streaks ONLY if we aren't already tracking one ---
        if active_setup is None:
            is_bullish_streak = (c2["close"] > c3["close"] > c4["close"] > c5["close"] > c6["close"]) and (c2["close"] - c6["close"] >= config.CANDLE_DIFF)
            is_bearish_streak = (c2["close"] < c3["close"] < c4["close"] < c5["close"] < c6["close"]) and (c6["close"] - c2["close"] >= config.CANDLE_DIFF)
            
            if is_bullish_streak:
                active_setup = "BUY_STREAK_CONFIRMED"
                setup_timer = MAX_LOOKBACK_CANDLES
                print(f"🔥 Bullish Streak Confirmed! Waiting for a confirmation bounce within {MAX_LOOKBACK_CANDLES} candles. RSI: {current_rsi:.2f}")
            elif is_bearish_streak:
                active_setup = "SELL_STREAK_CONFIRMED"
                setup_timer = MAX_LOOKBACK_CANDLES
                print(f"🔥 Bearish Streak Confirmed! Waiting for a confirmation breakdown within {MAX_LOOKBACK_CANDLES} candles. RSI: {current_rsi:.2f}")
                
        # --- STEP 2: Persistent Evaluation of the Trigger Loop ---
        if active_setup == "BUY_STREAK_CONFIRMED":
            # Valid confirmation bounce: price moving above the current tick's opening level
            if price > c1["open"]: 
                if current_rsi < RSI_OVERBOUGHT:
                    condition = "BUY"
                    active_setup = None  # Reset tracking state machine
                else:
                    print(f"⚠️ BUY blocked. Overbought territory (RSI: {current_rsi:.2f} > {RSI_OVERBOUGHT})")
                    active_setup = None

        elif active_setup == "SELL_STREAK_CONFIRMED":
            # Valid confirmation bounce: price dropping below the current tick's opening level
            if price < c1["open"]:
                if current_rsi > RSI_OVERSOLD:
                    condition = "SELL"
                    active_setup = None  # Reset tracking state machine
                else:
                    print(f"⚠️ SELL blocked. Oversold territory (RSI: {current_rsi:.2f} < {RSI_OVERSOLD})")
                    active_setup = None

        # --- STEP 3: Broker Execution Handler ---
        if condition is None:
            return
            
        trade.session_token = broker.session
        print(f"🚦 Execution Verification Cleared: Sending {condition} Signal to Broker | RSI: {current_rsi:.2f}")
        
        isTradeActive = True
        ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex)
        
        if profitOrLoss in ["PROFIT", "LOSS"]:
            if hasattr(strategy, 'reset'):
                strategy.reset()
                
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