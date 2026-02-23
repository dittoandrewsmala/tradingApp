import requests
import requests
import json
import config
from logger import Logger
logger = Logger()
class Position:
    """Helper to fetch positions and report whether the last trade was profitable.

    Usage:
        pos = Position()
        profitable = pos.get_positions(session_token)
    Returns True when the most-recent position's realized PnL is > 0, else False.
    """

    def get_positions(self, session_token):
        url = config.POSITION_URL
        headers = {
        "Content-Type": "application/x-www-form-urlencoded"
        }

        jdata = {
            "uid": config.USER_ID,
            "actid": config.USER_ID
        }
        
        # Properly format payload with JSON-encoded jData
        payload = f"jData={json.dumps(jdata)}&jKey={session_token}"
        
        logger.printD("Fetching positions with payload:"+ payload)

        try:
            res = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            logger.printR("❌ Request error while fetching positions:"+ str(e))
            return "ERROR"

        try:
            data = res.json()
        except ValueError:
            logger.printR("❌ Failed to decode JSON response:"+ res.text)
            return "ERROR"

        logger.printD(data)

        if data.get("stat") != "Ok":
            logger.printD("❌ API returned error for positions:"+ str(data))
            return "ERROR"

        positions = data.get("data", [])
        if not positions:
            logger.printD("ℹ️ No positions returned")
            return "ERROR"

        # Inspect the most-recent position (last in list)
        last = positions[-1]
        tsym = last.get("tsym")
        try:
            pnl = float(last.get("rpnl", 0))
        except (TypeError, ValueError):
            pnl = 0.0

        logger.printD(f"{tsym} -> Realized PnL = {pnl}")
        if pnl > 0:
            logger.printD("✅ Last trade PROFIT")
            return "PROFIT"
        else:
            logger.printD("❌ Last trade LOSS")
            return "LOSS"
            
