import websocket
import json
import time
import config
from logger import Logger

logger = Logger()
class MarketFeed:

    def __init__(self, session_token, symbol_token, callback):
        self.session_token = session_token
        self.symbol_token = symbol_token
        self.callback = callback
        self.ws = None

    # ---------- MESSAGE ----------
    def on_message(self, ws, msg):

        logger.printD("📩 RAW:"+ msg)

        try:
            data = json.loads(msg)
        except:
            return

        msg_type = data.get("t")

        # ---- LOGIN ACK ----
        if msg_type in ["ck", "ak"]:

            if data.get("s") == "OK":
                logger.printD("✅ WebSocket Login Success")
                self.subscribe()

            else:
                logger.printR("❌ Login Failed:"+ str(data))

        # ---- MARKET DATA ----
        elif "lp" in data:

            ltp = float(data["lp"])
            logger.printD("📊 LTP:"+ str(ltp))

            if self.callback:
                self.callback(ltp)

        # ---- HEARTBEAT ----
        elif msg_type == "h":
            logger.printD("💓 Heartbeat")

    # ---------- SUBSCRIBE ----------
    def subscribe(self):

        payload = {
            "t": "t",
            "k": f"{config.EXCHANGE_NSE}|{self.symbol_token}"
        }

        logger.printD("📡 Subscribing:"+ json.dumps(payload))

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
        logger.printR("❌ WebSocket Error:"+ str(error))

    # ---------- CLOSE ----------
    def on_close(self, ws, code, msg):

        logger.printD("🔴 Connection Closed")

        logger.printD("♻ Reconnecting in 5 sec...")
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
