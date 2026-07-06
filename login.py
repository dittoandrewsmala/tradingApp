import requests
from Order import Order
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
# instantiate order helper class
order = Order()


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
    # 🟢 Fixed: turned off reloader and debug to avoid background threading issues
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)


def login():
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
            token_val = data["token"]
            logger.printD("\n✅ Login Successful")
            logger.printD("Token :" + token_val)
            logger.printD("Client :" + data["client"])
            
            # 🟢 NEW: Update config.py cleanly in-place
            try:
                token_variable_name = "SMART_TOKEN"
                new_line = f'{token_variable_name} = "{token_val}"\n'
                
                # 1. Read existing config
                with open("config.py", "r") as f:
                    lines = f.readlines()
                
                # 2. Check if variable exists and replace it
                variable_exists = False
                for i, line in enumerate(lines):
                    if line.strip().startswith(token_variable_name):
                        lines[i] = new_line
                        variable_exists = True
                        break
                
                # 3. Append if it wasn't found anywhere in the file
                if not variable_exists:
                    if lines and not lines[-1].endswith('\n'):
                        lines[-1] += '\n'
                    lines.append(new_line)
                
                # 4. Save updates back to config file
                with open("config.py", "w") as f:
                    f.writelines(lines)
                    
                logger.printD("✏️ config.py updated successfully (Token line modified/created).")
                
            except Exception as file_err:
                logger.printD(f"⚠️ Login worked, but failed to write to config.py: {file_err}")

            return token_val  # Return the token string directly for strategy use
            
        else:
            logger.printD("\n❌ Login Failed:" + data.get("emsg"))
            raise Exception("Login failed: " + data.get("emsg", "Unknown error"))

    except Exception as e:
         raise Exception("Login failed: " + str(e))

login()  # Call login function to initiate the process