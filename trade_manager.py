import config 
import json
import requests
from datetime import datetime, timedelta
from logger import Logger
logger = Logger()
from Order import Order

order = Order()

class TradeManager:


    def __init__(self, broker, risk):
        self.broker = broker
        self.risk = risk
        self.position = False
        self.current_symbol = None
        self.session_token =None

    def api(self, url, jdata):
        headers = {"Content-Type": "application/json"}
        payload = f"jData={json.dumps(jdata)}&jKey={self.session_token}"

        try:
            res = requests.post(url, headers=headers, data=payload, timeout=10)
            data = res.json()
            return data
        except Exception as e:
            logger.printR(f"❌ API error: {e}")
            return None

    def load_option_chain(self):

        jdata = {
            "uid": config.USER_ID,
            "stext": "NIFTY",
            "exch": "NFO"
        }

        data = self.api(config.SEARCH_SCRIP_URL, jdata)

        if not data or "values" not in data:
            print("❌ Failed to load option chain")
            return []
        print(data)
        # Filter only NIFTY OPTIONS
        options = [
            x for x in data["values"]
            if x.get("instname") == "OPTIDX" and x.get("symname") == "NIFTY"
        ]
        print("options::",options)
        return options
    

    def get_nearest_expiry(self, options):

        expiries = list(set(x["exd"] for x in options))

        expiry_dates = [
            datetime.strptime(e, "%d-%b-%Y") for e in expiries
        ]

        nearest = min(expiry_dates)

        return nearest.strftime("%d-%b-%Y")


    def extract_strike(self, tsym):
        if "C" in tsym:
            return int(tsym.split("C")[-1])
        elif "P" in tsym:
            return int(tsym.split("P")[-1])
        return None
        
    # ---------- Generate Option Symbol ----------
    def get_option_symbol(self, price, option_type,strike):

        options = self.load_option_chain()
        if not options:
            return None

        # ✅ Step 1: get nearest expiry
        expiry = self.get_nearest_expiry(options)
        print("expiry::",expiry)

        # ✅ Step 2: filter by expiry + type
        filtered = [
            x for x in options
            if x["exd"] == expiry and x["optt"] == option_type
        ]
        print("filtered::",filtered)
        if not filtered:
            print("❌ No options for expiry/type")
            return None

        # ✅ Step 3: extract strikes
        strikes = []
        for x in filtered:
            strike = self.extract_strike(x["tsym"])
            if strike:
                strikes.append((strike, x))

        if not strikes:
            print("❌ No strikes found")
            return None

        # ✅ Step 4: find closest strike to price
        closest = min(strikes, key=lambda x: abs(x[0] - price))

        selected = closest[1]

        print(f"✅ Selected: {selected['tsym']} | Token: {selected['token']}")

        return selected["tsym"]
        

    # ---------- Entry Logic ----------
    def on_signal(self, signal, price,lotIndex):

        #if self.position:
        #    return
        ordNum = None
       

        # BUY CALL OPTION
        if signal == "BUY":
            symbol = self.get_option_symbol(price, "CE", price)
            
            ordNum,profitOrLoss=self.broker.place_order(
                side="B",
                lotIndex=lotIndex,
                symbol=symbol
            )

            self.current_symbol = symbol
            self.risk.new_trade(price)
            #self.position = True

        # BUY PUT OPTION
        if signal == "SELL":

            symbol = self.get_option_symbol(price, "PE", price)
            ordNum,profitOrLoss=self.broker.place_order(
                side="B",
                lotIndex=lotIndex,
                symbol=symbol
            )
            

            self.current_symbol = symbol
            self.risk.new_trade(price)
            #self.position = True
        return ordNum,profitOrLoss

    # ---------- Exit Logic ----------
    def manage(self, price, ord_numer):
        
        if not (self.position and self.risk.should_exit(price)):
        
        
            # Cancel order if should exit
            url = config.CANCEL_URL
            headers = {
                "Content-Type": "application/json"
            }
            
            jdata = {
                "uid": config.USER_ID,
                "norenordno": ord_numer 
            }
        
            # Properly format payload with JSON-encoded jData
            payload = f"jData={json.dumps(jdata)}&jKey={self.broker.session}"
            
            logger.printR("Fetching positions with payload:" + str(payload))

            try:
                res = requests.post(url, headers=headers, data=payload)
            except Exception as e:
                logger.printR("❌ Request error while fetching positions:" + str(e))
                return False

            try:
                data = res.json()
            except ValueError:
                logger.printR("❌ Failed to decode JSON response:" + res.text)
                return False
            
            stat = data.get("stat")
            self.position = False
            self.current_symbol = None
            if stat == "Ok":
                return True
            return False
        
     
