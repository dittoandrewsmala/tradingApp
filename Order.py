import requests
import json
import time
import config
from logger import Logger

lotnumbers = [1,1,1,1,2,2,3,4,5,8,11,14,18,23,35]

target_arr =[2,3,5,8,6,10.3,10.3,12,16,15,15,15,16,18,18]

stop__loss =[1,1.5,3,5,4,5,5,7,8,5,5,5,8,9,9]

logger = Logger()

# ---------------- API WRAPPER ---------------- #

def api(url, data):

    headers = {"Content-Type": "application/json"}

    payload = f"jData={json.dumps(data)}&jKey={config.SESSION_TOKEN}"

    try:
        res = requests.post(config.BASE + url, headers=headers, data=payload)
        return res.json()
    except Exception as e:
        logger.printR("❌ API Error: " + str(e))
        return None


# ---------------- MARKET DATA ---------------- #

def get_ltp(symbol):

    data = {
        "uid": config.USER_ID,
        "exch": "NFO",
        "tsym": symbol
    }

    res = api("/GetQuotes", data)

    if res and "lp" in res:
        return float(res["lp"])

    return None


# ---------------- ORDER PLACEMENT ---------------- #

def place_order(order):

    res = api("/PlaceOrder", order)

    if not res or res["stat"] != "Ok":
        logger.printR("❌ Order failed: " + str(res))
        return None

    return res["norenordno"]


# ---------------- ENTRY ---------------- #

def place_entry(side, symbol, qty):

    ltp = get_ltp(symbol)

    if side == "B":
        price = round(ltp + 0.3,2)
    else:
        price = round(ltp - 0.3,2)

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

    order_id = place_order(order)

    return order_id, price


# ---------------- EXIT ---------------- #

def exit_entry(side, symbol, qty):

    ltp = get_ltp(symbol)

    if side == "B":
        exit_side = "S"
        price = round(ltp - 0.5,2)   # sell below market
    else:
        exit_side = "B"
        price = round(ltp + 0.5,2)   # buy above market

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

    order_id = place_order(order)

    return order_id


# ---------------- MAIN TRADE FUNCTION ---------------- #

def submit_order(side, symbol, lotIndex):

    qty = lotnumbers[lotIndex] * config.LOT_SIZE

    entry_id, entry_price = place_entry(side, symbol, qty)

    if not entry_id:
        return None

    print("Entry placed:", entry_id)

    # Calculate target and stoploss based on side
    if side == "B":
        target = entry_price + target_arr[lotIndex]
        stop_loss = entry_price - stop__loss[lotIndex]
    else:
        target = entry_price - target_arr[lotIndex]
        stop_loss = entry_price + stop__loss[lotIndex]

    print("Entry:", entry_price)
    print("Target:", target)
    print("SL:", stop_loss)

    time.sleep(2)

    while True:

        ltp = get_ltp(symbol)

        if not ltp:
            continue

        print("LTP:", ltp)

        if side == "B":

            if ltp >= target:
                print("🎯 Target Hit")
                exit_entry(side, symbol, qty)
                break

            if ltp <= stop_loss:
                print("🛑 Stoploss Hit")
                exit_entry(side, symbol, qty)
                break

        else:

            if ltp <= target:
                print("🎯 Target Hit")
                exit_entry(side, symbol, qty)
                break

            if ltp >= stop_loss:
                print("🛑 Stoploss Hit")
                exit_entry(side, symbol, qty)
                break

        time.sleep(1)

    return entry_id