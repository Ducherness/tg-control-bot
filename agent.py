import os
import threading
import time
import subprocess
import logging
from collections import deque
from flask import Flask, jsonify, request
import pyperclip
import io
import base64
import psutil
from PIL import ImageGrab
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

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

@app.route('/sleep', methods=['POST'])
def sleep_pc():
    logger.warning("Sleep command received")
    if os.name == 'nt':
        # Windows: rundll32.exe powrprof.dll,SetSuspendState 0,1,0
        os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
    else:
        os.system('systemctl suspend')
    return jsonify({"status": "sleeping"})

@app.route('/clipboard', methods=['GET'])
def get_clipboard():
    return jsonify({"history": list(clipboard_history)})

@app.route('/screenshot', methods=['GET'])
def screenshot():
    try:
        # Capture screen
        img = ImageGrab.grab()
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=85)
        img_byte_arr.seek(0)
        
        # Encode to base64 to send via JSON (or send raw bytes?)
        # Better to send raw bytes for a file download-like experience or base64 if JSON
        # Flask allow sending file directly
        from flask import send_file
        return send_file(img_byte_arr, mimetype='image/jpeg')
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/stats', methods=['GET'])
def stats():
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\\\')
        
        data = {
            "cpu": cpu_percent,
            "ram_percent": mem.percent,
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1)
        }
        return jsonify(data)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/volume', methods=['POST'])
def volume():
    try:
        data = request.json
        action = data.get('action')
        
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol_ctrl = interface.QueryInterface(IAudioEndpointVolume)
        
        current_vol = vol_ctrl.GetMasterVolumeLevelScalar()
        
        if action == 'set':
            level = float(data.get('level', 0.5))
            # Clamp between 0.0 and 1.0
            level = max(0.0, min(1.0, level))
            vol_ctrl.SetMasterVolumeLevelScalar(level, None)
            return jsonify({"status": "set", "level": level})
            
        elif action == 'mute':
            mute_status = not vol_ctrl.GetMute() # Toggle
            vol_ctrl.SetMute(mute_status, None)
            return jsonify({"status": "muted" if mute_status else "unmuted"})
            
        elif action == 'get':
            pass # Just return status
            
        return jsonify({
            "level": round(current_vol * 100),
            "muted": vol_ctrl.GetMute() == 1
        })
        
    except Exception as e:
        logger.error(f"Volume error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start clipboard monitor in background
    monitor_thread = threading.Thread(target=clipboard_monitor, daemon=True)
    monitor_thread.start()
    
    logger.info(f"Agent starting on port {PORT}...")
    app.run(host=HOST, port=PORT)
