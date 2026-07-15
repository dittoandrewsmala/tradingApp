from datetime import datetime, timedelta
import json
import requests


class OhOlScanner:

    def __init__(self, uid: str, session_token: str):
        self.uid = uid
        self.session_token = session_token
        self.base_url = "https://piconnect.flattrade.in/PiConnectAPI/TPSeries"
        self.headers = {"Content-Type": "application/x-www-form-urlencoded"}

    def get_highest_lowest_candles(self, token: str, interval: str = "5"):
        """Fetches historical data for the current day between 09:15 and 09:30

        and returns the highest high and lowest low candles.
        """
        today = datetime.now()

        # 1. Define time ranges for the current day's market window
        start = datetime(today.year, today.month, today.day, 9, 15, 0)
        end = datetime(today.year, today.month, today.day, 9, 30, 0)

        st = int(start.timestamp())
        et = int(end.timestamp())


        # 2. Build the API payload parameters
        jdata = {
            "uid": self.uid,
            "exch": "NSE",
            "token": token,
            "st": str(st),
            "et": str(et),
            "intrv": interval,
        }
        payload = f"jData={json.dumps(jdata)}&jKey={self.session_token}"
        print(f"Sending request with payload: {payload}")   
        try:
            # 3. Execute the POST request
            response = requests.post(
                self.base_url, headers=self.headers, data=payload
            )
            print(f"Received response: {response.status_code} | Content: {response.text}")  # Debugging line
            response.raise_for_status()
            response_data = response.json()

            # Handle structural anomalies (ensure it evaluates a list)
            if isinstance(response_data, dict):
                # Fallback check if Flattrade wraps the array inside a key
                candles = response_data.get(
                    "timePriceSeries", response_data.get("data", [])
                )
            elif isinstance(response_data, list):
                candles = response_data
            else:
                candles = []

            # API Error handling fallback if status isn't "Ok" or list is empty
            if not candles or (
                isinstance(candles, list)
                and len(candles) > 0
                and candles[0].get("stat") != "Ok"
            ):
                print(f"Error or empty response from API: {response_data}")
                return None, None

            # 4. Extract highest high and lowest low candle dictionaries
            highest_candle = max(candles, key=lambda x: float(x["inth"]))
            lowest_candle = min(candles, key=lambda x: float(x["intl"]))

            return highest_candle, lowest_candle

        except requests.exceptions.RequestException as req_err:
            print(f"HTTP Request failed: {req_err}")
            return None, None
        except Exception as e:
            print(f"An unexpected error occurred parsing the candles: {e}")
            return None, None


# ==========================================
# Example Usage:
# ==========================================
if __name__ == "__main__":
    USER_ID = "FZ34840"
    SESSION_TOKEN = (
        "49b069b0e2436af41657cec43d474f23e7bf02de8d51e65bf69b199042dfc63f"
    )
    NIFTY_TOKEN = "3426"  # Input token parameter

    # Initialize the scanner class object
    scanner = OhOlScanner(uid=USER_ID, session_token=SESSION_TOKEN)

    # Call the method passing the desired token
    hi_candle, lo_candle = scanner.get_highest_lowest_candles(token=NIFTY_TOKEN)

    # Print out results if successfully retrieved
    if hi_candle and lo_candle:
        print(f"Highest High: {hi_candle['inth']} (at {hi_candle['time']})")
        print(f"Lowest Low:   {lo_candle['intl']} (at {lo_candle['time']})")