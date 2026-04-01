import requests
import json
import time
import config
from logger import Logger

logger = Logger()

class Order:

    def __init__(self, session_token=None):
        self.session_token = session_token
        self.token_cache = {}

        self.lotnumbers =    [1,1,1,1,2,3,7,14,12,18] 
        self.target_arr =    [.5,1,2,5,5,7,6,6,15,16]   
        self.stop_loss_arr = [.5,1,2,5,5,7,6,6,10,8]  

    # ---------------- API ----------------
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

    # ---------------- TOKEN CACHE ----------------
    def get_token(self, symbol):
        if symbol not in self.token_cache:
            jdata = {"uid": config.USER_ID, "stext": symbol, "exch": "NFO"}
            data = self.api(config.SEARCH_SCRIP_URL, jdata)
            if not data:
                return None

            for item in data.get("values", []):
                if item.get("tsym") == symbol:
                    self.token_cache[symbol] = item.get("token")
                    break

        return self.token_cache.get(symbol)

    # ---------------- LTP ----------------
    def get_ltp(self, symbol):
        token = self.get_token(symbol)
        if not token:
            return None

        for attempt in range(5):
            jdata = {"uid": config.USER_ID, "exch": "NFO", "token": token}
            data = self.api(config.GET_QUOTES, jdata)
            
            if data and "lp" in data:
                return float(data["lp"])

            time.sleep(1)  # Wait before retry

        return None

    # ---------------- ORDER STATUS ----------------
    def get_order_status(self, order_id):
        jdata = {"uid": config.USER_ID}
        res = self.api(config.ORDER_BOOK_URL, jdata)

        if not res:
            return None, None

        orders = res if isinstance(res, list) else res.get("orders", [])

        for order in orders:
            if order.get("norenordno") == order_id:
                return order.get("status"), float(order.get("avgprc", 0))

        return None, None

    # ---------------- WAIT FOR FILL ----------------
    def wait_for_fill(self, order_id, timeout=2000):
        start = time.time()

        while time.time() - start < timeout:
            status, price = self.get_order_status(order_id)

            if status == "COMPLETE":
                print("✅ Filled at:", price)
                return price

            if status in ["REJECTED", "CANCELED"]:
                print(f"❌ Order {status}")
                return None

            time.sleep(1)

        print("⏳ Timeout waiting for fill")
        return None

    # ---------------- PLACE ORDER ----------------
    def place_order(self, jdata):
        res = self.api(config.PLACE_ORDER_URL, jdata)

        if not res or res.get("stat") != "Ok":
            logger.printR(f"❌ Order failed: {res}")
            return None

        return res.get("norenordno")

    # ---------------- ENTRY ----------------
    def place_entry(self, side, symbol, qty, ltp):

        price = round(ltp + 0.3, 2) if side == "B" else round(ltp - 0.3, 2)

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

    # ---------------- EXIT ----------------
    def exit_entry(self, side, symbol, qty):
        ltp = self.get_ltp(symbol)

        if ltp is None:
            return None

        exit_side = "S" if side == "B" else "B"
        price = round(ltp - 0.5, 2) if side == "B" else round(ltp + 0.5, 2)

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

        return self.place_order(order)

    # ---------------- MAIN EXECUTION ----------------
    def submit_order(self, side, symbol, lotIndex, ltp):
        
        qty = self.lotnumbers[lotIndex] * config.LOT_SIZE
        print(f"🚀 Placing {side} order for {qty} qty")

        entry_id = self.place_entry(side, symbol, qty,ltp)
        if not entry_id:
            return None, "LOSS"

        entry_price = self.wait_for_fill(entry_id)
        if not entry_price:
            return None, "LOSS"

        base_target = self.target_arr[lotIndex]

        if side == "B":
            target = entry_price + base_target
            stop_loss = entry_price - self.stop_loss_arr[lotIndex]
        else:
            target = entry_price - base_target
            stop_loss = entry_price + self.stop_loss_arr[lotIndex]

        print(f"Entry: {entry_price} | Target: {target} | SL: {stop_loss}")
        checkFlag=None
        
        try:
            # ---------------- TRADE LOOP ----------------
            while True:
                time.sleep(1)
                ltp = self.get_ltp(symbol)
                print(f"Current LTP: {ltp} | Target: {target} | SL: {stop_loss} | index: {lotIndex}")

                if ltp is None:
                    print("❌ LTP not available, retrying...")
                    continue

                

                if side == "B":
                    if ltp >= target:
                        print("🎯 Target Hit buy - adjusting targets")
                        target = ltp + 2
                        stop_loss = ltp
                        checkFlag=True
                        continue

                    if ltp <= stop_loss:
                        print("🛑 Stoploss Hit buy")
                        exit_id = self.exit_entry(side, symbol, qty)
                        self.wait_for_fill(exit_id)
                        profitOrLoss = "LOSS"
                        if(checkFlag):
                          profitOrLoss = "PROFIT"  
                        break
                        
                    
                    

                else:
                    if ltp <= target:
                        print("🎯 Target Hit sell ")
                        target = ltp - 2
                        stop_loss = ltp
                        checkFlag=True
                        continue

                    if ltp >= stop_loss:
                        print("🛑 Stoploss Hit sell")
                        exit_id = self.exit_entry(side, symbol, qty)
                        self.wait_for_fill(exit_id)
                        profitOrLoss = "LOSS"
                        if(checkFlag):
                          profitOrLoss = "PROFIT" 
                        break
        except Exception as e:
            # ---------------- EMERGENCY EXIT ----------------
            try:
                print("🚨 Attempting emergency exit...")

                exit_id = self.exit_entry(side, symbol, qty)
                if exit_id:
                    self.wait_for_fill(exit_id)
                    print("✅ Emergency exit executed")

                profitOrLoss = "LOSS"

            except Exception as exit_error:
                print(f"💀 CRITICAL: Exit also failed: {exit_error}")
                profitOrLoss = "LOSS"

        finally:
            print(f"📊 Trade Result: {profitOrLoss}")

        return entry_id, profitOrLoss