from broker import Broker
from strategy import strategy, CandleBuilder
from risk_manager import RiskManager
from trade_manager import TradeManager
from websocket_feed import MarketFeed
from Postion import Position 
from datetime import datetime, time, timezone
from logger import Logger
import config
import sys
import pytz
import logging
from collections import deque

logger = Logger()

broker = Broker()
broker.login()
position = Position()
nifty_token = broker.get_nifty_token()

builder = CandleBuilder(10)
strategy = strategy()
risk = RiskManager()
trade = TradeManager(broker, risk)
isTradeActive = False
lotIndex = 0
signalStarted = False
ord_numer = None
condition = None
candles = deque(maxlen=5)

if not signalStarted:
    logger.printD("🚀 Starting signal generation...")
    signalStarted = True
    choice = input("Do want to give index value ? ").strip()
    if choice.lower() == "yes":
        lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())


def on_tick(price, volume, open, low, high, close):
    global signalStarted, lotIndex, isTradeActive, ord_numer, signal, checkLot
    signal = None
    checkLot = True

    candle = builder.update(price, 1, open, low, high, close)
    
    # --- FIX: Prevent duplicate ticks from pushing identical candles into your deque ---
    if candle:
        if candles:
            # Create a signature from the candle's core prices to identify uniqueness
            last_candle_sig = (candles[-1]['open'], candles[-1]['high'], candles[-1]['low'])
            new_candle_sig = (candle['open'], candle['high'], candle['low'])
            
            if last_candle_sig == new_candle_sig:
                # Update the existing live candle properties in-place rather than appending
                candles[-1] = candle 
            else:
                candles.append(candle)
        else:
            candles.append(candle)
    # ----------------------------------------------------------------------------------

    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).time()
    cutoff_time = time(config.CUT_OFF_TIME, 0)

    if checkLot and len(candles) >= 5 and not isTradeActive:
        
        last_candle = candles[-1]
        last_candle_2 = candles[-2]
        last_candle_3 = candles[-3]
        last_candle_4 = candles[-4]
        last_candle_5 = candles[-5]
        
        print("Last 5 candles:")
        for i, c in enumerate([last_candle_5, last_candle_4, last_candle_3, last_candle_2, last_candle], start=1):
            print(f"Candle {i}: Open={c['open']}, High={c['high']}, Low={c['low']}, Close={c['close']}, Volume={c['volume']}")

        trade.session_token = broker.session
        
        condition = None
        if last_candle["close"] > last_candle_2["close"] and last_candle_2["close"] > last_candle_3["close"] and last_candle_3["close"] > last_candle_4["close"] and last_candle_4["close"] > last_candle_5["close"]:
            if last_candle["close"] - last_candle_5["close"] >= config.CANDLE_DIFF:
                condition = "BUY"
        elif last_candle["close"] < last_candle_2["close"] and last_candle_2["close"] < last_candle_3["close"] and last_candle_3["close"] < last_candle_4["close"] and last_candle_4["close"] < last_candle_5["close"]:
            if last_candle_5["close"] - last_candle["close"] >= config.CANDLE_DIFF:
                condition = "SELL"
                
        if condition is None:
            return
            
        ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex)
        if profitOrLoss in ["PROFIT", "LOSS"]:
            strategy.reset()
        if profitOrLoss == "PROFIT":
             lotIndex = 0
        elif profitOrLoss == "LOSS":
             lotIndex = lotIndex + 1
        if ord_numer is not None:
            isTradeActive = False
            ord_numer = None


feed = MarketFeed(
    session_token=broker.session,
    symbol_token=nifty_token,
    callback=on_tick
)
feed.start()