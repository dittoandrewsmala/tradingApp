import requests
import json
import time
import config
from logger import Logger
from strategy import Strategy

logger = Logger()
strategy = Strategy()

class Order:

    def __init__(self, session_token=None):
        self.session_token = session_token
        self.token_cache = {}
        self.total_pnl = 0
        self.max_loss = -1500
        self.lotnumbers = [1,1,1,2,3,9,12,20]  
        self.target_arr = [1,2,5,5,7,6,9,12]  
        self.stop_loss_arr = [1,2,5,5,7,6,9,12]

    # ---------------- API ----------------
    def api(self, url, jdata):
        headers = {"Content-Type": "application/json"}
        payload = f"jData={json.dumps(jdata)}&jKey={self.session_token}"

        try:
            res = requests.post(url, headers=headers, data=payload, timeout=10)
            return res.json()
        except Exception as e:
            logger.printR(f"❌ API error: {e}")
            return None

    # ---------------- CANCEL ORDER ----------------
    def cancel_order(self, order_id):
        jdata = {
            "uid": config.USER_ID,
            "norenordno": order_id
        }

        res = self.api(config.CANCEL_URL, jdata)
        print(f"⚠️ Cancel response for {order_id}: {res}")
        return res

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

        for _ in range(5):
            jdata = {"uid": config.USER_ID, "exch": "NFO", "token": token}
            data = self.api(config.GET_QUOTES, jdata)

            if data and "lp" in data:
                return float(data["lp"])

            time.sleep(1)

        return None

    # ---------------- ORDER STATUS ----------------
    def get_order_status(self, order_id):
        jdata = {"uid": config.USER_ID}
        res = self.api(config.ORDER_BOOK_URL, jdata)
        print(f"📋 Order book response: {res}")
        if not res:
            return None, None

        orders = res if isinstance(res, list) else res.get("orders", [])

        for order in orders:
            if order.get("norenordno") == order_id:
                return order.get("status"), float(order.get("avgprc", 0))

        return None, None

    # ---------------- WAIT FOR FILL ----------------
    def wait_for_fill(self, order_id, timeout=100):
        start = time.time()

        while time.time() - start < timeout:
            print("⏳ Waiting for order to fill...", order_id)

            status, price = self.get_order_status(order_id)

            if status == "COMPLETE":
                print("✅ Filled at:", price)
                return price

            if status in ["REJECTED", "CANCELED"]:
                print(f"❌ Order {status}")
                return None

            time.sleep(1)

        # ⛔ TIMEOUT → CANCEL
        print(f"⏳ Timeout → Cancelling order {order_id}")
        self.cancel_order(order_id)

        # 🔁 Re-check after cancel (race condition)
        time.sleep(1)
        status, price = self.get_order_status(order_id)

        if status == "COMPLETE":
            print("⚠️ Filled during cancel!")
            return price

        print("❌ Order cancelled safely")
        return None

    # ---------------- PLACE ORDER ----------------
    def place_order(self, jdata):
        res = self.api(config.PLACE_ORDER_URL, jdata)
        print("place order", res)

        if not res or res.get("stat") != "Ok":
            logger.printR(f"❌ Order failed: {res}")
            return None

        return res.get("norenordno")

    # ---------------- ENTRY ----------------
    def place_entry(self, side, symbol, qty):
        ltp = self.get_ltp(symbol)
        if ltp is None:
            return None

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
        print(f"🚀 Placing {order}")
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
        # ✅ BLOCK if max loss already hit
        if self.total_pnl <= self.max_loss:
            print("⛔ Trading blocked. Max loss reached.")
            return None, None
        

        qty = self.lotnumbers[lotIndex] * config.LOT_SIZE
        qty=65*(lotIndex+1)
        

        entry_id = self.place_entry(side, symbol, qty)
        if not entry_id:
            return None, None

        entry_price = self.wait_for_fill(entry_id)
        if not entry_price:
            return None, None

        original_entry_price = entry_price

        base_target = self.target_arr[lotIndex]
        base_target=5

        if side == "B":
            target = entry_price + base_target
            #stop_loss = entry_price - self.stop_loss_arr[lotIndex]
            stop_loss = entry_price - 5
        else:
            target = entry_price - base_target
            #stop_loss = entry_price + self.stop_loss_arr[lotIndex]
            stop_loss = entry_price + 5

        print(f"Entry: {entry_price}")

        try:
            while True:
                time.sleep(1)
                
                ltp = self.get_ltp(symbol)
                signal = strategy.signal(ltp)
                print(f"LTP: {ltp} | Target: {target} | SL: {stop_loss} | signal: {signal} |side: {side}")

                if ltp is None:
                    continue

                buffer = 0.5
                trail_step = base_target * 0.5

                if side == "B":

                    if ltp >= target :
                        stop_loss = max(stop_loss, ltp - trail_step)
                        continue

                    if (signal and signal in ["EXIT_LONG", "SELL"])  or ltp <= stop_loss:
                        exit_id = self.exit_entry(side, symbol, qty)
                        exit_price = self.wait_for_fill(exit_id)
                        if exit_price is None:
                            return entry_id, "LOSS"
                        print(f"exit_price: {exit_price} | entry_price: {entry_price} ")
                        profitOrLoss = "PROFIT" if exit_price > entry_price else "LOSS"
                        break

                else:

                    if ltp <= target :
                        stop_loss = min(stop_loss, ltp + trail_step)
                        continue

                    if (signal and signal in ["EXIT_SHORT", "BUY"]) or ltp >= stop_loss:
                        exit_id = self.exit_entry(side, symbol, qty)
                        exit_price = self.wait_for_fill(exit_id)
                        if exit_price is None:
                            return entry_id, "LOSS"
                        print(f"exit_price: {exit_price} | entry_price: {entry_price} ")
                        profitOrLoss = "PROFIT" if exit_price < entry_price else "LOSS"
                        break

        except Exception as e:
            print("🚨 Emergency exit:", e)

            exit_id = self.exit_entry(side, symbol, qty)
            if exit_id:
                self.wait_for_fill(exit_id)

            profitOrLoss = "LOSS"
        # ✅ PnL CALCULATION
        if side == "B":
            pnl = (exit_price - entry_price) * qty
        else:
            pnl = (entry_price - exit_price) * qty

        self.total_pnl += pnl

        print(f"exit_price: {exit_price} | entry_price: {entry_price}")
        print(f"💰 Trade PnL: {pnl:.2f}")
        print(f"📉 Total PnL: {self.total_pnl:.2f}")
        
        if self.total_pnl <0:
            profitOrLoss = "LOSS"
        else:            
            profitOrLoss = "PROFIT"
        
        print(f"📊 Trade Result: {profitOrLoss}")
        return entry_id, profitOrLoss