from datetime import datetime, time, timedelta
import pytz
from broker import Broker
from logger import Logger

from risk_manager import RiskManager
from strategy import CandleBuilder
from trade_manager import TradeManager
from websocket_feed import MarketFeed

logger = Logger()

# Initialize components
broker = Broker()
broker.setLogin()


# --- Single Stock Configuration (Tata Power) ---
STOCK_NAME = 'TATAPOWER'
STOCK_TOKEN = '3426'  # Standard NSE token for Tata Power

# --- Single Asset Tracking Structure ---
asset_state = {
    "name": STOCK_NAME,
    "last_price": None,
    "anchors": {
        time(9, 15): {"open": None, "low": None, "high": None, "close": None, "direction": None},
        time(9, 20): {"open": None, "low": None, "high": None, "close": None, "direction": None},
        time(9, 25): {"open": None, "low": None, "high": None, "close": None, "direction": None},
        time(9, 35): {"open": None, "low": None, "high": None, "close": None, "direction": None},
    },
    "history": {},  # Remembers all minutes for fallback searching
    "trade_triggered": False,
    "builder": CandleBuilder(60)  
}

# Global Strategy Management Variables
risk = RiskManager()
trade = TradeManager(broker, risk)

isTradeActive = False
lotIndex = 0
signalStarted = False
ord_numer = None

# Initialized Strategy Control Variables Globally to avoid reference errors
diffFlag = False
directionFlag = False
highest_high = None
lowest_low = None
difference = None
condition = None 

IST = pytz.timezone('Asia/Kolkata')

if not signalStarted:
    logger.printD(f"🚀 Starting Advanced Anchor OHL Strategy for: {STOCK_NAME}")
    signalStarted = True
    choice = input("Do you want to give index value? ").strip()
    if choice.lower() == "yes":
        lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())


def on_tick_multi_asset(price, volume, open_val, low_val, high_val, close_val):
    global isTradeActive, difference, diffFlag, highest_high, lowest_low, directionFlag, condition, ord_numer
            
    # Track live price inside state structure
    asset_state["last_price"] = price
    
    candle = asset_state["builder"].update(price, volume, open_val, low_val, high_val, close_val)
    now_ist = datetime.now(IST).time()
    
    # -----------------------------------------------------------------
    # STEP 1: Process Target Anchor Bars when they Close
    # -----------------------------------------------------------------
    if time(9, 15) <= now_ist <= time(9, 26):   
        if candle is not None:
            candle_open_time = candle['time'].time() 
            
            # Build raw history for fallback searching
            direction = "UP" if candle["close"] >= candle["open"] else "DOWN"
            candle_data = {
                "open": candle["open"], "low": candle["low"], 
                "high": candle["high"], "close": candle["close"], "direction": direction
            }
            asset_state["history"][candle_open_time] = candle_data
            
            # Map straight to assigned static anchors if matching
            if candle_open_time in asset_state["anchors"]:
                asset_state["anchors"][candle_open_time].update(candle_data)
    
    # -----------------------------------------------------------------
    # STEP 2: Value Range Setup (9:27 AM - 9:30 AM)
    # -----------------------------------------------------------------
    if time(9, 27) <= now_ist <= time(9, 32) and not diffFlag:
        anchor_keys = list(asset_state["anchors"].keys())
        a15 = asset_state["anchors"][anchor_keys[0]]
        a20 = asset_state["anchors"][anchor_keys[1]]
        a25 = asset_state["anchors"][anchor_keys[2]]
        
        if (a15 and a20 and a25 and 
            None not in (a15["high"], a20["high"], a25["high"], a15["low"], a20["low"], a25["low"])):

            highest_high = max(a15["high"], a20["high"], a25["high"])
            lowest_low = min(a15["low"], a20["low"], a25["low"])
            difference = highest_high - lowest_low
            
            # Calculated as a ratio of the absolute trading range relative to the price
            percentage = (difference / price) * 100
            diffFlag = True  
            
            print(f"✅ Range Formed -> High: {highest_high} | Low: {lowest_low} | Diff: {difference}")
            print(f"📊 Range Percentage Size: {percentage:.3f}%")
            
            if percentage >= 0.75:
                print("⚠️ Volatility range is too wide (>= 0.75%). Exiting strategy context for safety.")
                exit(0)

    # -----------------------------------------------------------------
    # STEP 3: Breakout Detection (9:31 AM - 10:00 AM)
    # -----------------------------------------------------------------
    # Changed 'not diffFlag' to 'diffFlag' so this block actually runs after values are found
    if time(9, 34) <= now_ist <= time(10, 00) and diffFlag and not asset_state["trade_triggered"]:
        if price >= highest_high:
            directionFlag = True
            condition = "BUY"
        elif price <= lowest_low:
            directionFlag = True
            condition = "SELL"

    # -----------------------------------------------------------------
    # STEP 4: Hardstop Strategy Expiration
    # -----------------------------------------------------------------
    if now_ist >= time(10, 5):
        print("⏰ Time limit reached (10:05 AM). Shutting down engine pipeline.")
        exit(0)
    
    # -----------------------------------------------------------------
    # STEP 5: Order Execution Control Block
    # -----------------------------------------------------------------
    if directionFlag and not isTradeActive and condition is not None:
        directionFlag = False  # Reset flag immediately to block micro-tick spam loops
        isTradeActive = True
        asset_state["trade_triggered"] = True
        
        print(f"🎯 Breakout Confirmed: {STOCK_NAME} | Direction: {condition} at Price: {price}")
        
        try:
            trade.session_token = broker.session
            ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex,STOCK_NAME,difference)
            print("🚀 Execution Order Successfully Conveyed to Broker.")
            exit(0)
        except Exception as e:
            print(f"❌ Order execution failure: {e}")
            asset_state["trade_triggered"] = False  # Fallback to retry if order failed structurally
        finally:
            isTradeActive = False
            ord_numer = None


# --- WebSocket Connection Setup for Single Token ---
feed = MarketFeed(
    session_token=broker.session,
    symbol_token=STOCK_TOKEN,  
    callback=on_tick_multi_asset
)
feed.start()