from broker import Broker
from strategy import Strategy
from risk_manager import RiskManager
from trade_manager import TradeManager
from websocket_feed import MarketFeed
from Postion import Position 
from datetime import datetime, time, timezone
from logger import Logger
import config
import sys
import pytz


logger = Logger()
broker = Broker()
broker.login()  
position = Position()
nifty_token =broker.get_nifty_token()



strategy = Strategy()
risk = RiskManager()
trade = TradeManager(broker, risk)
isTradeActive = False
lotIndex = 0
signalStarted = False
ord_numer = None
start_Price = None
current_Price = None


## initalize signal generation and max payout check
if not signalStarted:
        logger.printD("🚀 Starting signal generation...")
        signalStarted = True
        start_Price=broker.get_max_payout()
        print("start_Price: "+ str(start_Price))
        choice = input("Do want to give index value ? ").strip()
        if choice.lower() == "yes":
            lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())
    ### end of max payout check


def on_tick(price):
    global signalStarted, lotIndex, isTradeActive ,ord_numer,start_Price,current_Price
    
   
    
    ## receving signal 
    signal = strategy.signal(price)
    print("signal: "+ str(signal))
    #isProfitable = position.get_positions(broker.session)
    
    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).time()
    
    logger.printR("lot index: "+ str(lotIndex))
    
    # 2:00 PM time object
    cutoff_time = time(config.CUT_OFF_TIME, 0)

    if current_time > cutoff_time and lotIndex==0:
        sys.exit(0)
    
    if checkTradeActive():
        logger.printR("⚠️ Trade exited."+ str(ord_numer))
        isTradeActive = False
        ord_numer = None
    print("Signal: "+ str(signal))
    print("isTradeActive: "+ str(isTradeActive))
    print("Current Time: "+ str(current_time))
    print("Cutoff Time: "+ str(current_time >= time(9, 30)))
    print("Flag Signal : "+ str(signal and not isTradeActive and current_time >= time(9, 30)))
    

    
    if signal and not isTradeActive and current_time >= time(9, 30):
        ord_numer=trade.on_signal(signal, price,lotIndex)
        input("Do want to continue ? ").strip()
        print("index value: "+ str(lotIndex))
        if ord_numer is not None:
            isTradeActive = True
            

            

def checkTradeActive():
    global start_Price, lotIndex
    current_Price=broker.get_max_payout()
    print("current_Price: "+ str(current_Price))
    if current_Price > start_Price:
        start_Price = current_Price
        lotIndex=0
        return True
    elif current_Price < start_Price:
        start_Price = current_Price
        lotIndex+=1
        return True
    else:
        start_Price = current_Price
        return False
            
       

feed = MarketFeed(
    session_token=broker.session,
    symbol_token=nifty_token,   # NIFTY
    callback=on_tick
)
feed.start()
