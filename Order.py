import requests
import json
import time
import config
from logger import Logger

logger = Logger()

class Order:
    """Encapsulates API interactions and order functions."""

    def __init__(self, session_token=None):
        self.session_token = session_token
        self.lotnumbers = [1,1,1,1,2,2,3,4,5,8,11,14,18,30]
        self.target_arr = [2,3,5,8,6,10.3,10.3,12,16,15,15,15,16,18]
        self.stop__loss = [1,1.5,3,5,4,5,5,7,8,5,5,5,8,9]

    def api(self, url, jdata):
        
        headers = {
            "Content-Type": "application/json"
        }
        payload = f"jData={json.dumps(jdata)}&jKey={self.session_token}"
        try:
            res = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            logger.printR("❌ Request error while SearchScrip:"+ str(e))
            raise Exception("Failed to SearchScrip: " + str(e))
    
        try:
            data = res.json()
        except ValueError:
            raise Exception("Failed to decode JSON response: " + res.text)
        
        return data
    
    
    def get_token_from_tsym(self, data, tsym):
        for item in data.get("values", []):
            #print("Checking tsym:", item.get("tsym"))
            if item.get("tsym") == tsym:
                return item.get("token")
        return None
   
    def SearchScrip(self, symbol):
        jdata = {"uid": config.USER_ID,"stext": symbol, "exch": "NFO" }
        data= self.api(config.SEARCH_SCRIP_URL, jdata)
        token = self.get_token_from_tsym(data, symbol)
        return  token



    def get_ltp(self, symbol):
        url = config.GET_QUOTES
        token= self.SearchScrip(symbol)
        jdata = {"uid": config.USER_ID, "exch": "NFO", "token": token}
        data= self.api(config.GET_QUOTES, jdata)      
        if data and "lp" in data:
            return float(data["lp"])
        return None

    def get_order_status(self, order_id):
        data = {"uid": config.USER_ID}
        res = self.api(config.ORDER_BOOK_URL, data)
        if not res:
            return None, None
        for order in res:
            if order["norenordno"] == order_id:
                status = order["status"]
                price = order.get("avgprc", "0")
                return status, float(price)
        return None, None

    def wait_for_fill(self, order_id):
        while True:
            status, price = self.get_order_status(order_id)
            if status == "COMPLETE":
                print("✅ Entry filled at:", price)
                return price
            elif status == "REJECTED":
                print("❌ Order rejected")
                return None
            elif status == "CANCELED":
                print("❌ Order cancelled")
                return None
            time.sleep(1)

    def place_order(self, jdata):
        
        res = self.api(config.PLACE_ORDER_URL, jdata)
        if not res or res.get("stat") != "Ok":
            logger.printR("❌ Order failed: " + str(res))
            return None
        return res.get("norenordno")

    def place_entry(self, side, symbol, qty):
        ltp = self.get_ltp(symbol)
        if side == "B":
            price = round(ltp + 0.3, 2)
        else:
            price = round(ltp - 0.3, 2)
        
        order = {
            "uid": config.USER_ID,
            "actid": config.USER_ID,
            "exch": "NFO",
            "tsym": symbol,
            "qty": str(qty),
            "prd": "I",
            "trantype": side,
            "prctyp": "LMT",
            "prc": str(price),
            "ret": "DAY"
        }
        
        return self.place_order(order)

    def exit_entry(self, side, symbol, qty):
        #print(f"Placing sfsf exit order for {qty} units of {symbol}")
        ltp = self.get_ltp(symbol)
        if side == "B":
            exit_side = "S"
            price = round(ltp - 0.5, 2)
        else:
            exit_side = "B"
            price = round(ltp + 0.5, 2)
        order = {
            "uid": config.USER_ID,
            "actid": config.USER_ID,
            "exch": "NFO",
            "tsym": symbol,
            "qty": str(qty),
            "prd": "I",
            "trantype": exit_side,
            "prctyp": "LMT",
            "prc": str(price),
            "ret": "DAY"
        }
        #print(f"Placing exit order: {exit_side} {qty} of {symbol} at {price}")
        return self.place_order(order)

    def submit_order(self, side, symbol, lotIndex):
        qty = self.lotnumbers[lotIndex] * config.LOT_SIZE
        print(f"Placing {side} order for {qty} units of {symbol}")
        entry_id = self.place_entry(side, symbol, qty)
        profitOrLoss=None
        if not entry_id:
            return None
        
        
        entry_price = self.wait_for_fill(entry_id)
        if not entry_price:
            return None
        
        if side == "B":
            target = entry_price + self.target_arr[lotIndex]
            stop_loss = entry_price - self.stop__loss[lotIndex]
        else:
            target = entry_price - self.target_arr[lotIndex]
            stop_loss = entry_price + self.stop__loss[lotIndex]
        
        print("Entry:", entry_price)
        print(side)
        print("==================================================================")
        while True:
            
            ltp = self.get_ltp(symbol)
            print("LTP VALUE checking:", ltp)
            print("Target:", target)
            print("SL:", stop_loss)
            
            if ltp is None:
                time.sleep(0.5)
                continue
              
            if side == "B":
                
                  
                if ltp >= target:
                    print("🎯 Target Hit buy")
                    self.exit_entry(side, symbol, qty)
                    profitOrLoss= "PROFIT"
                    break

                if ltp <= stop_loss:
                    print("🛑 Stoploss Hit buy")
                    self.exit_entry(side, symbol, qty)
                    profitOrLoss= "LOSS"
                    break

            else:
                
                
                if ltp <= target:
                    print("🎯 Target Hit sell ")
                    self.exit_entry(side, symbol, qty)
                    profitOrLoss= "PROFIT"
                    break

                if ltp >= stop_loss:
                    print("🛑 Stoploss Hit sell")
                    self.exit_entry(side, symbol, qty)
                    profitOrLoss= "LOSS"
                    break

            time.sleep(1)
        print("==================================================================")
        return entry_id,profitOrLoss