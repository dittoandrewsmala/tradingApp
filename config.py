# ===== USER SETTINGS =====

API_KEY = "b86624198f744b6d96eb9901c4883be0"
API_SECRET = "2026.f9556d48fde44afea5f91a6563cfa1fad5d4c0e2ed2d8be1"
REDIRECT_URL = "http://127.0.0.1:8080/callback?"   # Only for reference

AUTH_URL = f"https://auth.flattrade.in/?app_key={API_KEY}"
TOKEN_URL = "https://authapi.flattrade.in/trade/apitoken"

POSITION_URL = "https://piconnect.flattrade.in/PiConnectAPI/PositionBook"

ORDER_URL = "https://piconnect.flattrade.in/PiConnectAPI/PlaceOrder"

INDEX_LIST_URL = "https://piconnect.flattrade.in/PiConnectAPI/GetIndexList"

CANCEL_URL = "https://piconnect.flattrade.in/PiConnectAPI/CancelOrder"

MAX_PAYOUT_URL = "https://piconnect.flattrade.in/PiConnectAPI/GetMaxPayoutAmount"


SEARCH_SCRIP_URL = "https://piconnect.flattrade.in/PiConnectAPI/SearchScrip"
BASE = "https://piconnect.flattrade.in/PiConnectTP"

GET_QUOTES="https://piconnect.flattrade.in/PiConnectAPI/GetQuotes"
PLACE_ORDER_URL = "https://piconnect.flattrade.in/PiConnectAPI/PlaceOrder"

ORDER_BOOK_URL = "https://piconnect.flattrade.in/PiConnectAPI/OrderBook"

SINGLE_ORDER_URL = "https://piconnect.flattrade.in/PiConnectAPI/SingleOrdHist"


SEGMENT="NIFTY 50"
EXCHANGE_NSE = "NSE"
EXC_NFO = "NFO"
USER_ID = "FZ34840"   # Your user ID for API calls

PAPER_MODE = False

CAPITAL = 20000
RISK_PERCENT = 1
CANDLE_DIFF= 6

stop_target_counter=1

CUT_OFF_TIME = 14

# increse yime for stop loss and target hit check value incress to avoid mising target hit and stop loss hit
WAIT_MARKETFEED_TIME = 30

timeInterval = 4  # in seconds
LOT_SIZE = 65   # NIFTY lot size
MIN_CANDLES = 10  # Minimum candles required for indicators
# R or D
trade_log ="R"

# ===== RISK MANAGEMENT =====
STOP_LOSS = 5      # Stop loss points
TARGET = 10        # Target profit points
TRAIL = 3         # Trailing stop points

EXPIRY="21APR26"





