import config 
import json
import requests
from datetime import datetime, timedelta
from logger import Logger
logger = Logger()


class TradeManager:


    def __init__(self, broker, risk):
        self.broker = broker
        self.risk = risk
        self.position = False
        self.current_symbol = None

    def getStrike(self, price):
        strike = round(price / 50) * 50 
        return strike
        
    # ---------- Generate Option Symbol ----------
    def get_option_symbol(self, price, option_type,strike):


        today = datetime.today()

        # Tuesday = 1 (Monday=0)
        days_ahead = 1 - today.weekday()

        if days_ahead < 0:
            days_ahead += 7

        next_tuesday = today + timedelta(days=days_ahead)

        expiry = next_tuesday.strftime("%d%b%y").upper()
        
        
        # ATM strike
        atm = round(price / 50) * 50
        # choose far OTM strike
        if option_type == "CE":
            strike = atm + 100
        else:
            strike = atm - 100
        
        if option_type == "CE":
            return f"NIFTY{expiry}C{strike}"

        if option_type == "PE":
            return f"NIFTY{expiry}P{strike}"

    # ---------- Entry Logic ----------
    def on_signal(self, signal, price,lotIndex):

        #if self.position:
        #    return
        ordNum = None
       

        # BUY CALL OPTION
        if signal == "BUY":
            strike = self.getStrike(price)
            symbol = self.get_option_symbol(price, "CE", strike)
            #lp_value = self.get_quotes(search_scrips_token)
            
            ordNum,profitOrLoss=self.broker.place_order(
                side="B",
                lotIndex=lotIndex,
                symbol=symbol,
                ltp=price
            )

            self.current_symbol = symbol
            self.risk.new_trade(price)
            #self.position = True

        # BUY PUT OPTION
        if signal == "SELL":

            strike = self.getStrike(price)
            symbol = self.get_option_symbol(price, "PE", strike)
            
            ordNum,profitOrLoss=self.broker.place_order(
                side="B",
                lotIndex=lotIndex,
                symbol=symbol,
                ltp=price
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
        
     
