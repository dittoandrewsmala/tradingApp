from datetime import datetime, time, timedelta
import pytz
from broker import Broker
from logger import Logger
import time as tm
from risk_manager import RiskManager
from strategy import CandleBuilder
from trade_manager import TradeManager
from websocket_feed import MarketFeed

logger = Logger()

# Initialize components
broker = Broker()
broker.setLogin()


# --- Single Stock Configuration (Tata Power) ---
STOCK_NAME = 'TATAPOWER-EQ'
STOCK_TOKEN = '3426'  # Standard NSE token for Tata Power

# --- Single Asset Tracking Structure ---
asset_state = {
    "name": STOCK_NAME,
    "last_price": None,
    "anchors": {
        0: {"open": None, "low": None, "high": None, "close": None, "direction": None},
        1: {"open": None, "low": None, "high": None, "close": None, "direction": None},
        2: {"open": None, "low": None, "high": None, "close": None, "direction": None}
    },
    "history": {},  # Remembers all minutes for fallback searching
    "trade_triggered": False,
    "builder": CandleBuilder(60)  
}

# Global Strategy Management Variables
risk = RiskManager()
trade = TradeManager(broker, risk)


lotIndex = 1
signalStarted = False
ord_numer = None

# Initialized Strategy Control Variables Globally to avoid reference errors
diffFlag = False
directionFlag = False
highest_high = None
lowest_low = None
difference = None
condition = None 
counter =0
IST = pytz.timezone('Asia/Kolkata')
print("⏳ Waiting for market open (9:15 AM IST)...")
if not signalStarted:
    logger.printD(f"🚀 Starting Advanced Anchor OHL Strategy for: {STOCK_NAME}")
    signalStarted = True
    choice = input("Do you want to give index value yes or no ? ").strip()
    if choice.lower() == "yes":
        lotIndex = int(input("Enter share size: ").strip())

while True:
    now = datetime.now(IST).time()
    print("⏳ Current IST Time:", now)
    if now >= time(9, 15):
        print("Reached 9:15 AM")
        break
    


def on_tick_multi_asset(price, volume, open_val, low_val, high_val, close_val):
    global  difference, diffFlag, highest_high, lowest_low, directionFlag, condition, ord_numer
    
    now_ist = datetime.now(IST).time()
    print("⏳ time:", now_ist, "Price:", price, "Volume:", volume, "Open:", open_val, "Low:", low_val, "High:", high_val, "Close:", close_val)
    
    # -----------------------------------------------------------------
    # STEP 1: Process Target Anchor Bars when they Close
    # -----------------------------------------------------------------
    if time(9, 15) <= now_ist <= time(9, 30) :
        # Build raw history for fallback searching
        # Initialize values on the very first candle
        if highest_high is None or lowest_low is None:
            highest_high = high_val
            lowest_low = low_val
        else:
            # Dynamically update the absolute highest high and lowest low
            highest_high = max(highest_high, high_val)
            lowest_low = min(lowest_low, low_val)  
        print(f"📈 Current Bounds -> Highest High: {highest_high} | Lowest Low: {lowest_low}")     
            


    # -----------------------------------------------------------------
    # STEP 2: Value Range Setup (9:27 AM - 9:30 AM)
    # -----------------------------------------------------------------
    if now_ist >= time(9, 31) and not diffFlag:
        print("⏳ Waiting for anchor candles to form (9:31 AM - 9:33 AM)...")   
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
    if diffFlag and now_ist >= time(9, 32):
        print(f"🎯 Breakout Confirmed: {STOCK_NAME} | Direction: {condition} at Price: {price}")   
        if price >= highest_high:
            directionFlag = True
            condition = "BUY"
            print(f"🎯 highest high candle closed  : {STOCK_NAME} | Direction: {condition} at Price: {price}")
        elif price <= lowest_low:
            directionFlag = True
            condition = "SELL"
            print(f"🎯  lowest low candle closed: {STOCK_NAME} | Direction: {condition} at Price: {price}")

    # -----------------------------------------------------------------
    # STEP 4: Hardstop Strategy Expiration
    # -----------------------------------------------------------------
    if now_ist >= time(10, 30):
        print("⏰ Time limit reached (10:30 AM). Shutting down engine pipeline.")
        exit(0)
    
    # -----------------------------------------------------------------
    # STEP 5: Order Execution Control Block
    # -----------------------------------------------------------------
    if directionFlag  and condition is not None:
        print("⏳ directionFlag is True and no active trade. Preparing to execute order...")   
        directionFlag = False  # Reset flag immediately to block micro-tick spam loops
        asset_state["trade_triggered"] = True
        
        print(f"🎯 Breakout Confirmed: {STOCK_NAME} | Direction: {condition} at Price: {price}")
        
        try:
            trade.session_token = broker.session
            ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex,STOCK_NAME,difference,STOCK_TOKEN)
            print("🚀 Execution Order Successfully Conveyed to Broker.")
            exit(0)
        except Exception as e:
            print(f"❌ Order execution failure: {e}")
            asset_state["trade_triggered"] = False  # Fallback to retry if order failed structurally
        finally:
            ord_numer = None


# --- WebSocket Connection Setup for Single Token ---
feed = MarketFeed(
    session_token=broker.session,
    symbol_token=STOCK_TOKEN,  
    callback=on_tick_multi_asset
)
feed.start()