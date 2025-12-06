import requests
import time
import threading

RENDER_URL = "https://your-bot-name.onrender.com"

def ping():
    while True:
        try:
            requests.get(RENDER_URL)
            print("✅ Pinged server")
        except:
            print("❌ Ping failed")
        time.sleep(300)  # Ping every 5 minutes

# Run in separate thread
threading.Thread(target=ping, daemon=True).start()