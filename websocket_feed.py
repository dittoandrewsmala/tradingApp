import websocket
import json
import time
import config
from logger import Logger
from datetime import datetime, time
import time as tm

import pytz
logger = Logger()

class MarketFeed:

    def __init__(self, session_token, symbol_token, callback):
        self.session_token = session_token
        self.symbol_token = symbol_token
        self.callback = callback
        self.ws = None
        # --- ADDED: Track the last time data was forwarded ---
        self.last_processed_time = 0  
        self.interval = 5  # Interval in seconds

    # ---------- MESSAGE ----------
    def on_message(self, ws, msg):
        # Optional: You can comment this out if it floods your log file/console
        logger.printD("📩 RAW:" + msg)

        try:
            data = json.loads(msg)
        except Exception:
            return

        msg_type = data.get("t")

        # ---- LOGIN ACK ----
        if msg_type in ["ck", "ak"]:
            if data.get("s") == "OK":
                logger.printD("✅ WebSocket Login Success")
                self.subscribe()
            else:
                logger.printR("❌ Login Failed:" + str(data))

        # ---- MARKET DATA ----
        elif "lp" in data:
            current_time = tm.time()
            IST = pytz.timezone('Asia/Kolkata')
            now = datetime.now(IST).time()  
            # Check if 5 seconds have passed since the last callback trigger
            if current_time - self.last_processed_time >= self.interval:
                ltp = float(data["lp"])
                volume = float(data.get("v", 0))
                open_price = float(data.get("o", ltp))
                high = float(data.get("h", ltp))
                low = float(data.get("l", ltp))
                close = float(data.get("c", ltp))

                if self.callback:
                    self.callback(ltp, volume, open_price, low, high, close)
                
                # Update the timestamp checkpoint
                self.last_processed_time = current_time

        # ---- HEARTBEAT ----
        elif msg_type == "h":
            logger.printD("💓 Heartbeat")

    # ---------- SUBSCRIBE ----------
    def subscribe(self):
        payload = {
            "t": "t",
            "k": f"{config.EXCHANGE_NSE}|{self.symbol_token}"
        }
        logger.printD("📡 Subscribing:" + json.dumps(payload))
        self.ws.send(json.dumps(payload))

    # ---------- OPEN ----------
    def on_open(self, ws):
        logger.printD("✅ WebSocket Connected")
        login_payload = {
            "t": "a",
            "uid": config.USER_ID,
            "actid": config.USER_ID,
            "source": "API",
            "accesstoken": self.session_token
        }
        ws.send(json.dumps(login_payload))
        logger.printD("🔐 Login Sent")

    # ---------- ERROR ----------
    def on_error(self, ws, error):
        logger.printR("❌ WebSocket Error:" + str(error))

    # ---------- CLOSE ----------
    def on_close(self, ws, code, msg):
        logger.printD("🔴 Connection Closed")
        logger.printD(f"♻ Reconnecting in {config.timeInterval} sec...")
        time.sleep(config.timeInterval)
        self.start()

    # ---------- START ----------
    def start(self):
        self.ws = websocket.WebSocketApp(
            "wss://piconnect.flattrade.in/PiConnectWSAPI/",
            on_message=self.on_message,
            on_open=self.on_open,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()