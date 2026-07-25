import websocket
import json
import time as tm
from datetime import datetime
import pytz
import config
from logger import Logger

logger = Logger()

class MarketFeed:

    def __init__(self, session_token, symbol_token, callback, exchange):
        self.session_token = session_token
        self.symbol_token = symbol_token
        self.callback = callback
        self.ws = None
        self.exchange = exchange
        self.last_processed_time = 0  
        self.interval = 5  # Callback interval in seconds

    # ---------- MESSAGE ----------
    def on_message(self, ws, msg):
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
            if current_time - self.last_processed_time >= self.interval:
                ltp = float(data["lp"])
                volume = float(data.get("v", 0))
                open_price = float(data.get("o", ltp))
                high = float(data.get("h", ltp))
                low = float(data.get("l", ltp))
                close = float(data.get("c", ltp))

                if self.callback:
                    self.callback(ltp, volume, open_price, low, high, close)
                
                self.last_processed_time = current_time

        # ---- HEARTBEAT ACK FROM SERVER ----
        elif msg_type == "h":
            logger.printD("💓 Server Heartbeat Ack")

    # ---------- SUBSCRIBE ----------
    def subscribe(self):
        payload = {
            "t": "t",
            "k": f"{self.exchange}|{self.symbol_token}"
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
        logger.printR("❌ WebSocket Error: " + str(error))

    # ---------- CLOSE ----------
    def on_close(self, ws, code, msg):
        logger.printR(f"🔴 Connection Closed. Code: {code}, Message: {msg}")

    # ---------- START ----------
    def start(self):
        # Outer loop ensures clean reconnection without recursion
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    "wss://piconnect.flattrade.in/PiConnectWSAPI/",
                    on_message=self.on_message,
                    on_open=self.on_open,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                
                # ping_interval=30 sends an automatic ping every 30s to keep connection alive
                # ping_timeout=10 waits 10s for pong response before timing out
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
                
            except Exception as e:
                logger.printR(f"⚠️ Exception in WebSocket: {str(e)}")

            logger.printR(f"♻ Reconnecting in {config.timeInterval} sec...")
            tm.sleep(config.timeInterval)