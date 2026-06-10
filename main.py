from broker import Broker
from strategy import strategy,CandleBuilder
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


builder = CandleBuilder(30)
strategy = strategy()
risk = RiskManager()
trade = TradeManager(broker, risk)
isTradeActive = False
lotIndex = 0
signalStarted = False
ord_numer = None



## initalize signal generation and max payout check

if not signalStarted:
        logger.printD("🚀 Starting signal generation...")
        signalStarted = True
        choice = input("Do want to give index value ? ").strip()
        if choice.lower() == "yes":
            lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())
    ### end of max payout check


def on_tick(price):
    global signalStarted, lotIndex, isTradeActive ,ord_numer,signal
    signal=None
    candle = builder.update(price)
    if candle:
        signal=strategy.on_candle(candle, datetime.now(pytz.timezone("Asia/Kolkata")))
    
        
    ## receving signal 
    
    
    
    #isProfitable = position.get_positions(broker.session)
    
    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).time()
    
    #logger.printR("lot index: "+ str(lotIndex))
    
    # 2:00 PM time object
    cutoff_time = time(config.CUT_OFF_TIME, 0)

    #if current_time > cutoff_time and lotIndex==0:
        #sys.exit(0)
    
    
    
     
    if  signal !=None and ("SELL" in signal or "BUY" in signal) and not isTradeActive and current_time >= time(9, 30):
        trade.session_token=broker.session
        print("current index value: "+ str(lotIndex))
        if "BUY" in signal:
            condition = "BUY"
        elif "SELL" in signal:
            condition = "SELL"
        ord_numer,profitOrLoss=trade.on_signal(condition, price,lotIndex)
        if profitOrLoss == "PROFIT":
             lotIndex=0
        elif profitOrLoss == "LOSS":
             lotIndex=lotIndex+1

        strategy.reset_position()
        
        
        
            
        if ord_numer is not None:
            isTradeActive = False
            ord_numer = None
            


            
       

feed = MarketFeed(
    session_token=broker.session,
    symbol_token=nifty_token,   # NIFTY
    callback=on_tick
)
feed.start()
