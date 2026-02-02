import os
import threading
import time
import subprocess
import logging
from collections import deque
from flask import Flask, jsonify, request
import pyperclip

# Configuration
PORT = 8000
HOST = '0.0.0.0'
MAX_CLIPBOARD_ITEMS = 5

app = Flask(__name__)
clipboard_history = deque(maxlen=MAX_CLIPBOARD_ITEMS)
last_clip = ""

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def clipboard_monitor():
    global last_clip
    logger.info("Clipboard monitor started")
    while True:
        try:
            current_clip = pyperclip.paste()
            if current_clip and current_clip != last_clip:
                last_clip = current_clip
                # Avoid duplicates at the top of the stack
                if not clipboard_history or clipboard_history[0] != current_clip:
                    clipboard_history.appendleft(current_clip)
                    logger.info(f"New clipboard item detected: {current_clip[:20]}...")
        except Exception as e:
            logger.error(f"Clipboard error: {e}")
        time.sleep(1)

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "online", "platform": os.name})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    logger.warning("Shutdown command received")
    # /s = shutdown, /t 5 = 5 seconds delay
    if os.name == 'nt':
        os.system('shutdown /s /t 5')
    else:
        # Fallback for linux/mac if ever needed
        os.system('shutdown -h now')
    return jsonify({"status": "shutting_down"})

@app.route('/clipboard', methods=['GET'])
def get_clipboard():
    return jsonify({"history": list(clipboard_history)})

if __name__ == '__main__':
    # Start clipboard monitor in background
    monitor_thread = threading.Thread(target=clipboard_monitor, daemon=True)
    monitor_thread.start()
    
    logger.info(f"Agent starting on port {PORT}...")
    app.run(host=HOST, port=PORT)
