import threading
from flask import Flask, request
import hashlib
import requests
from logger import Logger
import config
import time

logger = Logger()
app = Flask(__name__)
auth_data = {}

def start_flask():
        """Run Flask in background to receive request_code from redirect URL"""
        app.run(host="0.0.0.0", port=8080)

 # Start Flask in background thread
threading.Thread(target=start_flask, daemon=True).start()

# Provide user with the authorization URL
logger.printD(f"Please open this URL in a browser to login: {config.AUTH_URL}")

# Wait for callback to receive request_code
logger.printD("Waiting for request_code from Flattrade callback...")
while "request_code" not in auth_data:
    time.sleep(1)

request_code = auth_data["request_code"]
logger.printD(f"Received request_code: {request_code}")
