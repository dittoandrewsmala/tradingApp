from datetime import datetime, time, timedelta
import pytz
from broker import Broker
from logger import Logger
import time as tm
from risk_manager import RiskManager
from strategy import CandleBuilder
from trade_manager import TradeManager
from websocket_feed import MarketFeed
from OhOlScanner import OhOlScanner 
import config

logger = Logger()

# Initialize components
broker = Broker()
broker.setLogin()
OhOlScanner=OhOlScanner(config.USER_ID, config.SMART_TOKEN)

# --- Single Stock Configuration (Tata Power) ---
STOCK_NAME = 'TATAPOWER-EQ'
STOCK_TOKEN = '3426'  # Standard NSE token for Tata Power


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
breakoutValue=.92
IST = pytz.timezone('Asia/Kolkata')
if not signalStarted:
    logger.printD(f"🚀 Starting Advanced Anchor OHL Strategy for: {STOCK_NAME}")
    signalStarted = True
    choice = input("Do you want to give index value yes or no ? ").strip()
    if choice.lower() == "yes":
        lotIndex = int(input("Enter share size: ").strip())
    choice = input("Do you want to give Volatility range yes or no ? ").strip()
    if choice.lower() == "yes":
        breakoutValue = float(input("Enter breakout value: ").strip())

while True:
    now = datetime.now(IST).time()
    print("⏳ Current IST Time:", now)
    if now >= time(9, 31):
        print("Reached 9:31 AM")
        break
    tm.sleep(1)


def on_tick_multi_asset(price, volume, open_val, low_val, high_val, close_val):
    global  difference, diffFlag, highest_high, lowest_low, directionFlag, condition, ord_numer,breakoutValue
    
    now_ist = datetime.now(IST).time()
    print("⏳ time:", now_ist, "Price:", price, "Volume:", volume, "Open:", open_val, "Low:", low_val, "High:", high_val, "Close:", close_val)
      
    # -----------------------------------------------------------------
    # STEP 1: 
    # -----------------------------------------------------------------
    if now_ist >= time(9, 31) and not diffFlag:
        print("⏳ Waiting for 9:31 AM - 9:33 AM)...")   
        highest_candle, lowest_candle = OhOlScanner.get_highest_lowest_candles(STOCK_TOKEN)
        highest_high = float(highest_candle["inth"])
        lowest_low = float(lowest_candle["intl"])
        difference = highest_high - lowest_low 
        # Calculated as a ratio of the absolute trading range relative to the price
        percentage = (difference / price) * 100
        diffFlag = True    
        print(f"✅ Range Formed -> High: {highest_high} | Low: {lowest_low} | Diff: {difference}")
        print(f"📊 Range Percentage Size: {percentage:.3f}%")   
        if percentage >= breakoutValue:
            print(f"⚠️ Volatility range is too wide (>= {breakoutValue:.2f}%). Exiting strategy context for safety.")
            exit(0)

    # -----------------------------------------------------------------
    # STEP 2: Breakout Detection (9:31 AM - 10:00 AM)
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
    # STEP 3: Hardstop Strategy Expiration
    # -----------------------------------------------------------------
    if now_ist >= time(10, 30):
        print("⏰ Time limit reached (10:30 AM). Shutting down engine pipeline.")
        exit(0)
    
    # -----------------------------------------------------------------
    # STEP 4: Order Execution Control Block
    # -----------------------------------------------------------------
    if directionFlag  and condition is not None:
        print("⏳ directionFlag is True and no active trade. Preparing to execute order...")   
        directionFlag = False  # Reset flag immediately to block micro-tick spam loops
        
        try:
            trade.session_token = broker.session
            ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex,STOCK_NAME,difference,STOCK_TOKEN)
            print("🚀 Execution Order Successfully Conveyed to Broker.")
            exit(0)
        except Exception as e:
            print(f"❌ Order execution failure: {e}")
        finally:
            ord_numer = None


# --- WebSocket Connection Setup for Single Token ---
feed = MarketFeed(
    session_token=broker.session,
    symbol_token=STOCK_TOKEN,  
    callback=on_tick_multi_asset
)
feed.start()