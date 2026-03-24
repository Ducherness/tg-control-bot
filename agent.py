import io
import logging
import os
import socket
import subprocess
import threading
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path

import psutil
import pyperclip
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize
from flask import Flask, jsonify, request, send_file
from PIL import ImageGrab
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

PORT = 8000
HOST = "0.0.0.0"
MAX_CLIPBOARD_ITEMS = 5
MAX_LOG_LINES = 200
DEFAULT_LOG_LINES = 40
SYSTEM_DRIVE = f"{os.environ.get('SystemDrive', 'C:')}\\"
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "agent.log"
STARTED_AT = time.time()

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
clipboard_history = deque(maxlen=MAX_CLIPBOARD_ITEMS)
last_clipboard_value = ""


def _run_system_command(command: list[str]) -> None:
    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )


def _audio_endpoint():
    device = AudioUtilities.GetSpeakers()
    volume_control = getattr(device, "EndpointVolume", None)
    if volume_control is None:
        raise RuntimeError("Default audio endpoint is unavailable")
    return volume_control


@contextmanager
def _com_context():
    CoInitialize()
    try:
        yield
    finally:
        CoUninitialize()


def _get_volume_state(volume_control) -> dict:
    return {
        "level": round(volume_control.GetMasterVolumeLevelScalar() * 100),
        "muted": volume_control.GetMute() == 1,
    }


def _tail_log_file(lines: int) -> list[str]:
    if not LOG_FILE.exists():
        return []

    with LOG_FILE.open("r", encoding="utf-8") as log_file:
        content = [line.rstrip() for line in log_file.readlines()]
    return content[-lines:]


def clipboard_monitor() -> None:
    global last_clipboard_value

    logger.info("Clipboard monitor started")
    while True:
        try:
            current_clip = pyperclip.paste()
            if current_clip and current_clip != last_clipboard_value:
                last_clipboard_value = current_clip
                if not clipboard_history or clipboard_history[0] != current_clip:
                    clipboard_history.appendleft(current_clip)
                    logger.info("New clipboard item detected")
        except Exception as error:
            logger.error("Clipboard error: %s", error)
        time.sleep(1)


@app.get("/ping")
def ping():
    return jsonify(
        {
            "status": "online",
            "platform": os.name,
            "hostname": socket.gethostname(),
            "uptime_seconds": int(time.time() - STARTED_AT),
        }
    )


@app.get("/health")
def health():
    try:
        boot_time = int(psutil.boot_time())
        payload = {
            "status": "ok",
            "hostname": socket.gethostname(),
            "platform": os.name,
            "system": os.environ.get("OS", "Windows"),
            "uptime_seconds": int(time.time() - STARTED_AT),
            "boot_time": boot_time,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "ram_percent": psutil.virtual_memory().percent,
            "clipboard_items": len(clipboard_history),
            "pid": os.getpid(),
        }
        return jsonify(payload)
    except Exception as error:
        logger.error("Health error: %s", error)
        return jsonify({"error": str(error)}), 500


@app.post("/shutdown")
def shutdown():
    logger.warning("Shutdown command received")
    try:
        if os.name == "nt":
            _run_system_command(["shutdown", "/s", "/t", "5"])
        else:
            _run_system_command(["shutdown", "-h", "now"])
        return jsonify({"status": "shutting_down"})
    except Exception as error:
        logger.error("Shutdown error: %s", error)
        return jsonify({"error": str(error)}), 500


@app.post("/sleep")
def sleep_pc():
    logger.warning("Sleep command received")
    try:
        if os.name == "nt":
            _run_system_command(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        else:
            _run_system_command(["systemctl", "suspend"])
        return jsonify({"status": "sleeping"})
    except Exception as error:
        logger.error("Sleep error: %s", error)
        return jsonify({"error": str(error)}), 500


@app.get("/clipboard")
def get_clipboard():
    return jsonify({"history": list(clipboard_history)})


@app.delete("/clipboard")
def clear_clipboard():
    clipboard_history.clear()
    logger.info("Clipboard history cleared")
    return jsonify({"status": "cleared"})


@app.get("/screenshot")
def screenshot():
    try:
        image = ImageGrab.grab(all_screens=True)
        if image.mode != "RGB":
            image = image.convert("RGB")

        image_bytes = io.BytesIO()
        image.save(image_bytes, format="JPEG", quality=88)
        image_bytes.seek(0)
        return send_file(image_bytes, mimetype="image/jpeg", download_name="screenshot.jpg")
    except Exception as error:
        logger.error("Screenshot error: %s", error)
        return jsonify({"error": str(error)}), 500


@app.get("/stats")
def stats():
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(SYSTEM_DRIVE)
        payload = {
            "cpu": psutil.cpu_percent(interval=0.1),
            "ram_percent": memory.percent,
            "ram_total_gb": round(memory.total / (1024**3), 1),
            "ram_used_gb": round(memory.used / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_path": SYSTEM_DRIVE,
        }
        return jsonify(payload)
    except Exception as error:
        logger.error("Stats error: %s", error)
        return jsonify({"error": str(error)}), 500


@app.post("/volume")
def volume():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action", "get")

    try:
        with _com_context():
            volume_control = _audio_endpoint()

            if action == "set":
                raw_level = payload.get("level", 0.5)
                level = max(0.0, min(1.0, float(raw_level)))
                volume_control.SetMasterVolumeLevelScalar(level, None)
                return jsonify({"status": "set", **_get_volume_state(volume_control)})

            if action == "step":
                raw_delta = payload.get("delta", 0.0)
                delta = float(raw_delta)
                current_level = volume_control.GetMasterVolumeLevelScalar()
                target_level = max(0.0, min(1.0, current_level + delta))
                volume_control.SetMasterVolumeLevelScalar(target_level, None)
                return jsonify({"status": "set", **_get_volume_state(volume_control)})

            if action == "mute":
                mute_status = not volume_control.GetMute()
                volume_control.SetMute(mute_status, None)
                return jsonify(
                    {"status": "muted" if mute_status else "unmuted", **_get_volume_state(volume_control)}
                )

            if action != "get":
                return jsonify({"error": f"Unsupported action: {action}"}), 400

            return jsonify({"status": "ok", **_get_volume_state(volume_control)})
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid volume payload"}), 400
    except Exception as error:
        logger.error("Volume error: %s", error)
        return jsonify({"error": str(error)}), 500


@app.get("/logs")
def logs():
    try:
        requested_lines = int(request.args.get("lines", DEFAULT_LOG_LINES))
        lines = max(1, min(requested_lines, MAX_LOG_LINES))
        return jsonify({"lines": _tail_log_file(lines)})
    except ValueError:
        return jsonify({"error": "Invalid lines value"}), 400
    except Exception as error:
        logger.error("Logs error: %s", error)
        return jsonify({"error": str(error)}), 500


if __name__ == "__main__":
    monitor_thread = threading.Thread(target=clipboard_monitor, daemon=True)
    monitor_thread.start()

    logger.info("Agent starting on %s:%s", HOST, PORT)
    app.run(host=HOST, port=PORT)
