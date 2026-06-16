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


builder = CandleBuilder(10)
strategy = strategy()
risk = RiskManager()
trade = TradeManager(broker, risk)
isTradeActive = False
lotIndex = 0
signalStarted = False
ord_numer = None
condition = None

if not signalStarted:
        logger.printD("🚀 Starting signal generation...")
        signalStarted = True
        choice = input("Do want to give index value ? ").strip()
        if choice.lower() == "yes":
            lotIndex = int(input("Enter lot index (0, 1, 2, ...): ").strip())
    ### end of max payout check


def on_tick(price, volume,open,low,high,close):
    global signalStarted, lotIndex, isTradeActive ,ord_numer,signal,checkLot
    signal=None
    checkLot=True

    logger.printD(f"price :{price} Volume: {volume} | O: {open} | H: {high} | L: {low} | C: {close}")
    candle = builder.update(price,1,open,low,high,close)
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
    
    
    
     
    if  lotIndex>5:
        checkLot=False 
        if  signal !=None and signal and signal.get("action") in ["BUY", "SELL"]  and not isTradeActive and current_time >= time(9, 30):
            checkLot=True
    
    if  checkLot and len(strategy.candles) >= 25  and not isTradeActive and current_time >= time(9, 30):
        first_candle = strategy.candles[-25]
        last_candle = strategy.candles[-1]
        last_candle_2 = strategy.candles[-2]
        last_candle_3 = strategy.candles[-3]
        last_candle_4 = strategy.candles[-4]
        last_candle_5 = strategy.candles[-5]
        print(f"First candle: {first_candle['close']}, Last candle: {last_candle['close']}")
        print(f"Last 5 candles: {[candle['close'] for candle in strategy.candles[-5:]]}")

        trade.session_token=broker.session
        print("current index value: "+ str(lotIndex))
        condition = None
        if  last_candle["close"] > first_candle["close"] and last_candle["close"] > last_candle_2["close"] and last_candle_2["close"] > last_candle_3["close"] and last_candle_3["close"] > last_candle_4["close"] and last_candle_4["close"] > last_candle_5["close"]:
            condition = "BUY"
        elif  last_candle["close"] < first_candle["close"] and last_candle["close"] < last_candle_2["close"] and last_candle_2["close"] < last_candle_3["close"] and last_candle_3["close"] < last_candle_4["close"] and last_candle_4["close"] < last_candle_5["close"]:
            condition = "SELL"
        if condition is None:
            return
        ord_numer,profitOrLoss=trade.on_signal(condition, price,lotIndex)
        if profitOrLoss in ["PROFIT", "LOSS"]:
            strategy.reset()
        if profitOrLoss == "PROFIT":
             lotIndex=0
        elif profitOrLoss == "LOSS":
             lotIndex=lotIndex+1
        if ord_numer is not None:
            isTradeActive = False
            ord_numer = None

           


            
       

feed = MarketFeed(
    session_token=broker.session,
    symbol_token=nifty_token,   # NIFTY
    callback=on_tick
)
feed.start()
