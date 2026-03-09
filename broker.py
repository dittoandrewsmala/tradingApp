import requests
import config
import hashlib
import webbrowser
import json
from logger import Logger
import time
import threading
from flask import Flask, request

logger = Logger()

app = Flask(__name__)

# Thread-safe storage
auth_data = {}
auth_event = threading.Event()


# -------------------------------
# CALLBACK ROUTE (CRITICAL FIX)
# -------------------------------
@app.route("/callback")
def callback():
    code = request.args.get("code")

    if code:
        auth_data["request_code"] = code
        auth_event.set()  # notify waiting thread
        return "Authorization successful. You can close this window."

    return "No code received", 400


def start_flask():
    """Run Flask in background to receive request_code"""
    app.run(host="0.0.0.0", port=8080)



logger = Logger()

lotnumbers = [1,1,1,1,2,2,3,4,5,8,11,14,18,23,35]

target_arr =[2,3,5,8,6,10.3,10.3,12,16,15,15,15,16,18,18]

stop__loss =[1,1.5,3,5,4,5,5,7,8,5,5,5,8,9,9]


class Broker:

    def __init__(self):
        self.session = None

        
    def login(self):

        # Start Flask server in background
        flask_thread = threading.Thread(target=start_flask, daemon=True)
        flask_thread.start()

        logger.printD(f"Open this URL in browser to login:\n{config.AUTH_URL}")
        logger.printD("Waiting for request_code from Flattrade callback...")

        # Wait for callback (max 120 seconds)
        if not auth_event.wait(timeout=120):
            raise TimeoutError("Did not receive request_code within 120 seconds")

        request_code = auth_data.get("request_code")
        print("Received request_code:", request_code)
        

        hash_string = config.API_KEY + request_code + config.API_SECRET
        security_key = hashlib.sha256(hash_string.encode()).hexdigest()

        payload = {
            "api_key": config.API_KEY,
            "request_code": request_code,
            "api_secret": security_key
        }
        try:
            response = requests.post(config.TOKEN_URL, json=payload)
            data = response.json()

            
            print(data)

            if data.get("stat") == "Ok":
                logger.printD("\n✅ Login Successful")
                logger.printD("Token :"+ data["token"])
                logger.printD("Client :"+ data["client"])
            else:
                logger.printD("\n❌ Login Failed:"+ data.get("emsg"))
                raise Exception("Login failed: " + data.get("emsg", "Unknown error"))

        except Exception as e:
             raise Exception("Login failed: " + str(e))

        self.session = data["token"]
        print("Session token set:"+ self.session)
        return True
    
    def get_nifty_token(self):
        url = config.INDEX_LIST_URL
        headers = {
            "Content-Type": "application/json"
        }
        jdata = {
            "uid": config.USER_ID,
            "exch": config.EXCHANGE_NSE
        }
        # Properly format payload with JSON-encoded jData
        payload = f"jData={json.dumps(jdata)}&jKey={self.session}"
        try:
            res = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            logger.printR("❌ Request error while fetching positions:"+ str(e))
            raise Exception("Failed to fetch index list: " + str(e))
    
        try:
            data = res.json()
        except ValueError:
            raise Exception("Failed to decode JSON response: " + res.text)
        
        token = next(item["token"] for item in data["values"] if item["idxname"] == "Nifty 50")
        return  token

    def place_order(self, side, lotIndex,symbol):

        url = config.ORDER_URL
        headers = {
            "Content-Type": "application/json"
        }
        
        # Find year part
        year_full = symbol[10:14]   # 2026
        year_short = year_full[2:]  # 26

        symbol = symbol.replace(year_full, year_short)

        qty = lotnumbers[lotIndex] * config.LOT_SIZE
        target= target_arr[lotIndex]
        stop_loss = stop__loss[lotIndex]    

        jdata = {
            "uid": config.USER_ID,
            "actid": config.USER_ID ,
             "exch": config.EXC_NFO,
             "tsym": symbol,  # Extract base symbol (e.g., NIFTY24FEB)
             "qty": str(qty),
             "prc": str(0),
             "prd": "B",
             "trantype": side,
             "prctyp": "MKT",
             "ret": "DAY",
             "bpprc": str(target*config.stop_target_counter),
             "blprc": str(stop_loss*config.stop_target_counter)
        }
        
        # Properly format payload with JSON-encoded jData
        payload = f"jData={json.dumps(jdata)}&jKey={self.session}"
        
        print("Fetching positions with payload:"+ payload)

        try:
            res = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            print("❌ Request error while placing order:"+ str(e))
            raise Exception("Failed to place order: " + str(e))
        print("Order placement response:"+ res.text)
        input("Do want to continue ? ").strip()
        try:
            data = res.json()
        except ValueError:
            raise Exception("❌ Failed to decode JSON response:"+ res.text)
            return False

        logger.printD(data)
        order_no = data.get("norenordno")
        return order_no
    

    def get_max_payout(self):
        url = config.MAX_PAYOUT_URL
        headers = {
            "Content-Type": "application/json"
        }
        jdata = {
            "uid": config.USER_ID,
            "actid": config.USER_ID
        }
        # Properly format payload with JSON-encoded jData
        payload = f"jData={json.dumps(jdata)}&jKey={self.session}"
        try:
            res = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            raise Exception("Failed to fetch max payout: " + str(e))
    
        try:
            data = res.json()
        except ValueError:
            raise Exception("❌ Failed to decode JSON response:"+ res.text)
            return False
        payoutdata = data.get("payout")
        

        return  payoutdata

