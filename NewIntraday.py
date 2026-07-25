from broker import Broker
from logger import Logger
from risk_manager import RiskManager
from trade_manager import TradeManager
from websocket_feed import MarketFeed
import config
logger = Logger()

# Initialize components
broker = Broker()
broker.setLogin()


STOCK_NAME = input("Enter STOCK_NAME: ").strip()
STOCK_TOKEN = int(input("Enter STOCK_TOKEN: ").strip())
lotIndex = int(input("Enter share number: ").strip())
range = int(input("Enter range: ").strip())
condition = input("Enter condition: ").strip()
       
# Global Strategy Management Variables
risk = RiskManager()
trade = TradeManager(broker, risk)

def on_tick_multi_asset(price, volume, open_val, low_val, high_val, close_val):  
        try:
            trade.session_token = broker.session
            ord_numer, profitOrLoss = trade.on_signal(condition, price, lotIndex,STOCK_NAME,range,STOCK_TOKEN)
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
    callback=on_tick_multi_asset,
    exchange=config.EXCHANGE_NSE
)
feed.start()