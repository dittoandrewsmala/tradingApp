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
    ### end of max payout check


def on_tick(price):
    global signalStarted, lotIndex, isTradeActive ,ord_numer,start_Price,current_Price
    
    #logger.printR("LTP:"+ str(price))

    ## receving signal 
    signal = strategy.signal(price)
    #isProfitable = position.get_positions(broker.session)
    
    
    
    logger.printR("lot index: "+ str(lotIndex))
    current_time =  datetime.now(timezone.utc).astimezone().time()
    # 2:00 PM time object
    cutoff_time = time(config.CUT_OFF_TIME, 0)

    if current_time > cutoff_time and lotIndex==0:
        sys.exit(0)
    
    print("signal: "+ str(signal))
    print("isTradeActive: "+ str(isTradeActive))
    print("current time: "+ str(current_time))
    
    if signal and not isTradeActive and current_time >= time(9, 30):
        input("Do want to continue ? ").strip()
        print("index value: "+ str(lotIndex))
        ord_numer=trade.on_signal(signal, price,lotIndex)
        logger.printR("Order Number value: "+ str(ord_numer))
        if ord_numer is not None:
            isTradeActive = True
            while True:
                time.sleep(config.WAIT_MARKETFEED_TIME)
                if checkTradeActive():
                    logger.printR("⚠️ Trade exited."+ str(ord_numer))
                    isTradeActive = False
                    ord_numer = None
                    break

            

def checkTradeActive():
    current_Price=broker.get_max_payout()
    if current_Price > start_Price:
        strart_Price = current_Price
        logger.printR("✅ Profit: "+ str(current_Price))
        lotIndex=0
        return True
    elif current_Price < start_Price:
        strart_Price = current_Price
        logger.printR("❌ Loss: "+ str(current_Price))
        lotIndex+=1
        return True
    else:
        strart_Price = current_Price
        logger.printR("❌ No changes to: "+ str(current_Price))
        return False
            
       

feed = MarketFeed(
    session_token=broker.session,
    symbol_token=nifty_token,   # NIFTY
    callback=on_tick
)
feed.start()
