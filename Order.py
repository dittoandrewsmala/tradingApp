import requests
import json
import time
from requests import api
import config
from logger import Logger

lotnumbers = [1,1,1,1,2,2,3,4,5,8,11,14,18,23,35]

target_arr =[2,3,5,8,6,10.3,10.3,12,16,15,15,15,16,18,18]

stop__loss =[1,1.5,3,5,4,5,5,7,8,5,5,5,8,9,9]


logger = Logger()

class Order:
    def api(self, url, data, jkey):

        headers = {
            "Content-Type": "application/json"
            }
    
        payload = f"jData={json.dumps(data)}&jKey={jkey}"

        try:
            res = requests.post(config.BASE+url, headers=headers, data=payload)
        except Exception as e:
            logger.printR("❌ Request error while placing order:"+ str(e))
            raise Exception("Failed to place order: " + str(e))

        return res.json()

def get_ltp(symbol):
    data = {
        "uid": config.USER_ID,
        "exch": "NFO",
        "tsym": symbol
    }
    res = api("/GetQuotes", data)
    return float(res["lp"])

def place_order(order):

    res = api("/PlaceOrder", order)
    if res["stat"] != "Ok":
        logger.printR("❌ Order failed:" + str(res))
        return None
    return res["norenordno"]

def place_entry(side,symbol, qty):

    ltp = get_ltp(symbol)
    if side == "B":
        price = ltp + 0.3
    else:
        price = ltp - 0.3

    order = {
        "uid": config.USER_ID,
        "actid": config.USER_ID,
        "exch": "NFO",
        "tsym": symbol,
        "qty": qty,
        "prd": "I",
        "trantype": side,
        "prctyp": "LMT",
        "prc": str(price),
        "ret": "DAY"
    }

    order_id = place_order(order)
    return order_id, price

def place_sl(price,symbol, qty):
    order = {
        "uid": config.USER_ID,
        "actid": config.USER_ID,
        "exch": "NFO",
        "tsym": symbol,
        "qty": qty,
        "prd": "I",
        "trantype": "S",
        "prctyp": "SL-MKT",
        "trgprc": str(price),
        "ret": "DAY"
    }
    return place_order(order)


def place_target(price,symbol, qty):
    order = {
        "uid": config.USER_ID,
        "actid": config.USER_ID,
        "exch": "NFO",
        "tsym": symbol,
        "qty": qty,
        "prd": "I",
        "trantype": "S",
        "prctyp": "LMT",
        "prc": str(price),
        "ret": "DAY"
    }
    return place_order(order)

def cancel_order(orderno):
    data = {
        "uid": config.USER_ID,
        "norenordno": orderno
    }
    return api("/CancelOrder", data)

def check_order_status(orderno):
    orders = api("/OrderBook", {"uid": config.USER_ID})
    for o in orders:
        if o["norenordno"] == orderno:
            return o["status"]

    return None

def sumbit_order(side, symbol,lotIndex):
    qty = lotnumbers[lotIndex] * config.LOT_SIZE
    target= target_arr[lotIndex]
    stop_loss = stop__loss[lotIndex]
    
    entry_id, entry_price = place_entry(side, symbol, qty)
    print("Entry placed:", entry_id)
    time.sleep(3)
    

    sl_id = place_sl(stop_loss, symbol, qty)
    target_id = place_target(target, symbol, qty)
    logger.printR("SL:", sl_id)
    logger.printR("Target:", target_id)

    while True:

        sl_status = check_order_status(sl_id)
        target_status = check_order_status(target_id)

        if target_status == "COMPLETE":
            logger.printR("Target Hit")
            cancel_order(sl_id)
            break

        if sl_status == "COMPLETE":
            logger.printR("Stop Loss Hit")
            cancel_order(target_id)
            break

        time.sleep(1)
    return entry_id


