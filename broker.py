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
auth_data = {}

def start_flask():
        """Run Flask in background to receive request_code from redirect URL"""
        app.run(host="0.0.0.0", port=8080)



logger = Logger()

lotnumbers = [1,1,2,2,4,5,6,10,15,20]

target_arr =[2,5,3,5,4,5,5,5,5,5]

stop__loss =[1,2.5,1.5,2,2,2.5,2.5,2.5,2.5,2.5]


class Broker:

    def __init__(self):
        self.session = None

    def login1(self):
        self.session = "53e20e326361ff89783c3ed00f0554a44fe2e454ba0b1d3eeeadf3fef4aa012b"
        return True
    
    def login(self):

         # Start Flask in background thread
        threading.Thread(target=start_flask, daemon=True).start()

        # Provide user with the authorization URL
        logger.printD(f"Please open this URL in a browser to login: {config.AUTH_URL}")

        # Wait for callback to receive request_code
        logger.printD("Waiting for request_code from Flattrade callback...")
        print("Waiting for request_code from Flattrade callback...",auth_data)
        while "request_code" not in auth_data:
            time.sleep(1)

        request_code = auth_data["request_code"]
        logger.printD(f"Received request_code: {request_code}")

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

            logger.printD("\n===== API RESPONSE =====")
            logger.printD(data)

            if data.get("stat") == "Ok":
                logger.printD("\n✅ Login Successful")
                logger.printD("Token :"+ data["token"])
                logger.printD("Client :"+ data["client"])
            else:
                logger.printD("\n❌ Login Failed:"+ data.get("emsg"))

        except Exception as e:
             logger.printR("Error:", str(e))

        self.session = data["token"]
        logger.printR("Session token set:"+ self.session)
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
            return False
    
        try:
            data = res.json()
        except ValueError:
            logger.printR("❌ Failed to decode JSON response:"+ res.text)
            return False
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
        
        logger.printR("Fetching positions with payload:"+ payload)

        try:
            res = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            logger.printR("❌ Request error while fetching positions:"+ str(e))
            return False

        try:
            data = res.json()
        except ValueError:
            logger.printR("❌ Failed to decode JSON response:"+ res.text)
            return False

        logger.printD(data)
        order_no = data.get("norenordno")
        return order_no
    

    def get_max_payout(self):
        url = config.MAX_PAYOUT_URL
        time.sleep(60)
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
            logger.printR("❌ Request error while fetching positions:"+ str(e))
            return False
    
        try:
            data = res.json()
        except ValueError:
            logger.printR("❌ Failed to decode JSON response:"+ res.text)
            return False
        payoutdata = data.get("payout")
        

        return  payoutdata

