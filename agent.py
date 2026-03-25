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
from comtypes import CoInitialize, CoUninitialize
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from PIL import ImageGrab
from pycaw.pycaw import AudioUtilities

load_dotenv()

PORT = int(os.getenv("AGENT_PORT", "8000"))
HOST = os.getenv("AGENT_HOST", "0.0.0.0")
MAX_CLIPBOARD_ITEMS = 5
MAX_LOG_LINES = 200
DEFAULT_LOG_LINES = 40
SYSTEM_DRIVE = f"{os.environ.get('SystemDrive', 'C:')}\\"
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "agent.log"
STARTED_AT = time.time()
DEFAULT_TASK_RESTART_DELAY = 5
TASK_STARTUP_GRACE_SECONDS = 2

COMFYUI_DIR = Path(os.getenv("COMFYUI_DIR", r"C:\Users\user\ComfyUI"))
COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))

TASK_DEFINITIONS = {
    "comfyui": {
        "name": "ComfyUI",
        "cwd": COMFYUI_DIR,
        "python": COMFYUI_DIR / "venv" / "Scripts" / "python.exe",
        "args": ["main.py", "--listen", "0.0.0.0", "--port", str(COMFYUI_PORT)],
        "restart_delay": DEFAULT_TASK_RESTART_DELAY,
    }
}

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
managed_tasks: dict[str, dict] = {}


def _run_system_command(command: list[str]) -> None:
    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
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


def _task_log_path(task_key: str) -> Path:
    return LOG_DIR / f"{task_key}.log"


def _task_creation_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _task_runtime_info(task_key: str) -> dict:
    definition = TASK_DEFINITIONS[task_key]
    runtime = managed_tasks.get(task_key)

    pid = None
    running = False
    started_at = None
    status = "stopped"
    error = None

    if runtime:
        process = runtime.get("process")
        if process and process.poll() is None:
            pid = process.pid
            running = True
            started_at = runtime.get("started_at")
        status = runtime.get("status", "stopped")
        error = runtime.get("startup_error")

    return {
        "id": task_key,
        "name": definition["name"],
        "cwd": str(definition["cwd"]),
        "running": running,
        "status": status,
        "pid": pid,
        "started_at": started_at,
        "log_file": str(_task_log_path(task_key)),
        "error": error,
    }


def _write_task_log(log_handle, message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_handle.write(f"[{timestamp}] {message}\n")
    log_handle.flush()


def _task_supervisor(task_key: str) -> None:
    definition = TASK_DEFINITIONS[task_key]
    runtime = managed_tasks[task_key]
    stop_event = runtime["stop_event"]
    ready_event = runtime["ready_event"]
    log_handle = runtime["log_handle"]

    command = [str(definition["python"]), *definition["args"]]
    cwd = str(definition["cwd"])
    restart_delay = int(definition["restart_delay"])

    while not stop_event.is_set():
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=log_handle,
                stderr=log_handle,
                stdin=subprocess.DEVNULL,
                creationflags=_task_creation_flags(),
            )
        except Exception as error:
            runtime["process"] = None
            runtime["started_at"] = None
            runtime["startup_error"] = str(error)
            runtime["status"] = "error"
            _write_task_log(log_handle, f"Failed to start {definition['name']}: {error}")
            ready_event.set()
            return

        runtime["process"] = process
        runtime["started_at"] = int(time.time())
        runtime["startup_error"] = None
        runtime["status"] = "running"
        _write_task_log(log_handle, f"Started {definition['name']} with PID {process.pid}")
        ready_event.set()

        exit_code = process.wait()
        runtime["process"] = None
        runtime["started_at"] = None

        if stop_event.is_set():
            runtime["status"] = "stopped"
            _write_task_log(log_handle, f"Stopped {definition['name']}.")
            return

        runtime["status"] = "restarting"
        _write_task_log(
            log_handle,
            f"{definition['name']} exited with code {exit_code}. Restarting in {restart_delay} seconds...",
        )
        if stop_event.wait(restart_delay):
            runtime["status"] = "stopped"
            _write_task_log(log_handle, f"Stopped {definition['name']}.")
            return


def _start_task(task_key: str) -> dict:
    definition = TASK_DEFINITIONS[task_key]
    runtime_info = _task_runtime_info(task_key)
    if runtime_info["running"]:
        return runtime_info

    cwd = Path(definition["cwd"])
    python_executable = Path(definition["python"])

    if not cwd.exists():
        raise FileNotFoundError(f"Task directory does not exist: {cwd}")
    if not python_executable.exists():
        raise FileNotFoundError(f"Task Python executable does not exist: {python_executable}")

    log_path = _task_log_path(task_key)
    log_handle = log_path.open("a", encoding="utf-8")
    try:
        stop_event = threading.Event()
        ready_event = threading.Event()
        supervisor = threading.Thread(target=_task_supervisor, args=(task_key,), daemon=True)
        managed_tasks[task_key] = {
            "process": None,
            "thread": supervisor,
            "stop_event": stop_event,
            "ready_event": ready_event,
            "started_at": None,
            "startup_error": None,
            "status": "starting",
            "log_handle": log_handle,
        }
        supervisor.start()
        ready_event.wait(timeout=TASK_STARTUP_GRACE_SECONDS)
        if not ready_event.is_set():
            raise RuntimeError(f"{definition['name']} did not start within {TASK_STARTUP_GRACE_SECONDS} seconds")
        time.sleep(TASK_STARTUP_GRACE_SECONDS)
        runtime_info = _task_runtime_info(task_key)
        if runtime_info["status"] in {"error", "restarting", "stopped"} or not runtime_info["running"]:
            raise RuntimeError(
                f"{definition['name']} exited immediately. Check log: {runtime_info['log_file']}"
            )
    except Exception:
        runtime = managed_tasks.pop(task_key, None)
        if runtime:
            runtime["stop_event"].set()
        log_handle.close()
        raise

    logger.info("Started task %s with PID %s", task_key, runtime_info["pid"])
    return runtime_info


def _stop_task(task_key: str) -> dict:
    runtime = managed_tasks.get(task_key)
    if not runtime:
        return _task_runtime_info(task_key)

    runtime["stop_event"].set()
    process = runtime.get("process")
    if process and process.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.terminate()

    thread = runtime.get("thread")
    if thread and thread.is_alive():
        thread.join(timeout=10)

    log_handle = runtime.get("log_handle")
    if log_handle and not log_handle.closed:
        log_handle.close()

    managed_tasks.pop(task_key, None)
    logger.info("Stopped task %s", task_key)
    return _task_runtime_info(task_key)


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
            "tasks": [_task_runtime_info(task_key) for task_key in TASK_DEFINITIONS],
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
            _run_system_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
                ]
            )
        else:
            _run_system_command(["systemctl", "suspend"])
        return jsonify({"status": "sleeping"})
    except Exception as error:
        logger.error("Sleep error: %s", error)
        return jsonify({"error": str(error)}), 500


@app.post("/hibernate")
def hibernate_pc():
    logger.warning("Hibernate command received")
    try:
        if os.name == "nt":
            _run_system_command(["shutdown", "/h"])
        else:
            _run_system_command(["systemctl", "hibernate"])
        return jsonify({"status": "hibernating"})
    except Exception as error:
        logger.error("Hibernate error: %s", error)
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


@app.get("/tasks")
def tasks():
    return jsonify({"tasks": [_task_runtime_info(task_key) for task_key in TASK_DEFINITIONS]})


@app.post("/tasks/<task_key>/start")
def start_task(task_key: str):
    if task_key not in TASK_DEFINITIONS:
        return jsonify({"error": f"Unknown task: {task_key}"}), 404

    try:
        task_info = _start_task(task_key)
        return jsonify({"status": "started" if task_info["running"] else "failed", "task": task_info})
    except Exception as error:
        logger.error("Task start error for %s: %s", task_key, error)
        return jsonify({"error": str(error)}), 500


@app.post("/comfyui/start")
def start_comfyui():
    return start_task("comfyui")


@app.post("/tasks/<task_key>/stop")
def stop_task(task_key: str):
    if task_key not in TASK_DEFINITIONS:
        return jsonify({"error": f"Unknown task: {task_key}"}), 404

    try:
        task_info = _stop_task(task_key)
        return jsonify({"status": "stopped", "task": task_info})
    except Exception as error:
        logger.error("Task stop error for %s: %s", task_key, error)
        return jsonify({"error": str(error)}), 500


@app.post("/comfyui/stop")
def stop_comfyui():
    return stop_task("comfyui")


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
