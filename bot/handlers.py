import asyncio
import html
import logging
import os
import platform
import subprocess
import tempfile

import httpx
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.ai import parse_intent
from bot.config import AGENT_PORT, AGENT_TIMEOUT, ALLOWED_USERS, TARGET_HOST, TARGET_MAC
from bot.voice import speech_to_text
from bot.wol import wake

logger = logging.getLogger(__name__)
AGENT_URL = f"http://{TARGET_HOST}:{AGENT_PORT}"
MAX_TEXT_BLOCK = 3500
WAKE_WAIT_TIMEOUT_SECONDS = 180
WAKE_WAIT_INTERVAL_SECONDS = 5


def is_allowed(user_id: int | None) -> bool:
    return user_id is not None and user_id in ALLOWED_USERS


def get_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🚀 Wake"), KeyboardButton("⏳ Wake&Wait"), KeyboardButton("🔍 Status")],
        [KeyboardButton("😴 Sleep"), KeyboardButton("💤 Hibernate"), KeyboardButton("🩺 Health")],
        [KeyboardButton("🧩 Tasks"), KeyboardButton("▶️ ComfyUI"), KeyboardButton("⏹️ ComfyUI")],
        [KeyboardButton("📸 Screen"), KeyboardButton("📋 Clipboard"), KeyboardButton("🧹 Clear Clip")],
        [KeyboardButton("📊 Stats"), KeyboardButton("📜 Logs"), KeyboardButton("🔊 Volume")],
        [KeyboardButton("🔉 -10%"), KeyboardButton("🔇 Mute"), KeyboardButton("🔊 +10%")],
        [KeyboardButton("🛑 Shutdown"), KeyboardButton("ℹ️ Help")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=False)


def _format_uptime(seconds: int) -> str:
    minutes, _ = divmod(max(seconds, 0), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _truncate_text(text: str, limit: int = MAX_TEXT_BLOCK) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit - 3]}..."


async def _agent_request(method: str, endpoint: str, timeout: float | None = None, **kwargs) -> httpx.Response:
    request_timeout = timeout if timeout is not None else AGENT_TIMEOUT
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        response = await client.request(method, f"{AGENT_URL}{endpoint}", **kwargs)
        response.raise_for_status()
        return response


async def _safe_reply(update: Update, text: str, *, parse_mode: str | None = "HTML") -> None:
    await update.effective_message.reply_text(text, parse_mode=parse_mode, reply_markup=get_keyboard())


def _agent_error_text(error: Exception, fallback_message: str = "Agent request failed.") -> str:
    if isinstance(error, httpx.HTTPStatusError):
        details = fallback_message
        if error.response.status_code == 404:
            return "❌ <b>Agent route not found.</b> Agent is outdated or was not restarted after the update."
        try:
            payload = error.response.json()
            details = payload.get("error") or payload.get("status") or details
        except Exception:
            response_text = (error.response.text or "").strip()
            if response_text:
                details = response_text
        return f"❌ <b>Agent error:</b> {_escape(details)}"

    if isinstance(error, httpx.RequestError):
        return "❌ <b>Failed:</b> Agent unreachable."

    return f"❌ <b>Failed:</b> {_escape(fallback_message)}"


def _format_task(task: dict) -> str:
    status = "🟢 running" if task.get("running") else "⚪ stopped"
    pid = task.get("pid") or "n/a"
    cwd = _escape(task.get("cwd", "n/a"))
    return f"• <b>{_escape(task.get('name', task.get('id', 'task')))}</b> - {status} (PID: {pid})\n<code>{cwd}</code>"


async def _agent_request_with_fallback(
    method: str,
    primary_endpoint: str,
    fallback_endpoint: str,
    timeout: float | None = None,
    **kwargs,
) -> httpx.Response:
    try:
        return await _agent_request(method, primary_endpoint, timeout=timeout, **kwargs)
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 404:
            raise
    return await _agent_request(method, fallback_endpoint, timeout=timeout, **kwargs)


async def check_permissions(update: Update) -> bool:
    if not is_allowed(update.effective_user.id if update.effective_user else None):
        await update.effective_message.reply_text("⛔ Access denied", reply_markup=get_keyboard())
        return False
    return True


async def _ping_host() -> bool:
    ping_param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", ping_param, "1", TARGET_HOST]

    def _run_ping() -> bool:
        try:
            return subprocess.call(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ) == 0
        except Exception:
            return False

    return await asyncio.to_thread(_run_ping)


async def _wait_for_agent_online(timeout_seconds: int = WAKE_WAIT_TIMEOUT_SECONDS) -> bool:
    attempts = max(1, timeout_seconds // WAKE_WAIT_INTERVAL_SECONDS)
    await asyncio.sleep(WAKE_WAIT_INTERVAL_SECONDS)

    for _ in range(attempts):
        try:
            response = await _agent_request("GET", "/ping", timeout=2.5)
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        await asyncio.sleep(WAKE_WAIT_INTERVAL_SECONDS)

    return False


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    text = (
        "🖥️ <b>Remote Control Center</b>\n\n"
        "Use the keyboard below or send a short text command.\n"
        "For sleep/resume flow, disable Windows sign-in requirement after wake."
    )
    await _safe_reply(update, text)


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, context)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    help_text = (
        "🤖 <b>Available commands</b>\n\n"
        "🚀 <b>Wake</b> - send Wake-on-LAN packet\n"
        "⏳ <b>Wake&Wait</b> - send Wake-on-LAN and wait until the agent is back online\n"
        "😴 <b>Sleep</b> - suspend the PC\n"
        "💤 <b>Hibernate</b> - hibernate and preserve session state on resume\n"
        "🩺 <b>Health</b> - show agent runtime info\n"
        "🧩 <b>Tasks</b> - list managed processes on the PC\n"
        "▶️ <b>ComfyUI</b> - start managed ComfyUI loop\n"
        "⏹️ <b>ComfyUI</b> - stop managed ComfyUI loop\n"
        "📸 <b>Screen</b> - capture desktop\n"
        "📋 <b>Clipboard</b> - show recent clipboard items\n"
        "📊 <b>Stats</b> - CPU, RAM and disk usage\n"
        "📜 <b>Logs</b> - last agent log lines\n"
        "🔊 <b>Volume</b> - current sound state\n"
        "🛑 <b>Shutdown</b> - power off the PC\n\n"
        "For auto-return to desktop after sleep/hibernate, Windows must be configured to not require sign-in on wake."
    )
    await _safe_reply(update, help_text)


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    await _safe_reply(update, "🔍 Checking connectivity...")
    host_online = await _ping_host()

    agent_text = "\n🤖 <b>Agent:</b> Unreachable ❌"
    if host_online:
        try:
            response = await _agent_request("GET", "/ping", timeout=2.5)
            payload = response.json()
            agent_uptime = _format_uptime(int(payload.get("uptime_seconds", 0)))
            hostname = _escape(payload.get("hostname", TARGET_HOST))
            agent_text = f"\n🤖 <b>Agent:</b> Connected ✅\n🏷️ <b>Host:</b> {hostname}\n⏱️ <b>Uptime:</b> {agent_uptime}"
        except httpx.HTTPError:
            agent_text = "\n🤖 <b>Agent:</b> Unreachable ❌"

    status_text = "🟢 <b>Online</b>" if host_online else "🔴 <b>Offline</b>"
    await _safe_reply(update, f"🖥️ <b>PC Status:</b> {status_text}{agent_text}")


async def health_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        response = await _agent_request("GET", "/health")
        data = response.json()
        tasks = data.get("tasks", [])
        tasks_text = "\n".join(_format_task(task) for task in tasks) if tasks else "• No managed tasks"
        text = (
            "🩺 <b>Agent Health</b>\n\n"
            f"🏷️ <b>Host:</b> {_escape(data.get('hostname', TARGET_HOST))}\n"
            f"🖥️ <b>Platform:</b> {_escape(data.get('system', 'Unknown'))}\n"
            f"⏱️ <b>Agent uptime:</b> {_format_uptime(int(data.get('uptime_seconds', 0)))}\n"
            f"📦 <b>PID:</b> {_escape(data.get('pid', 'n/a'))}\n"
            f"🧠 <b>CPU:</b> {_escape(data.get('cpu_percent', 'n/a'))}%\n"
            f"💾 <b>RAM:</b> {_escape(data.get('ram_percent', 'n/a'))}%\n"
            f"📋 <b>Clipboard items:</b> {_escape(data.get('clipboard_items', 0))}\n\n"
            f"🧩 <b>Tasks</b>\n{tasks_text}"
        )
        await _safe_reply(update, text)
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to read health status."))


async def wake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    if not TARGET_MAC:
        await _safe_reply(update, "⚠️ <b>Error:</b> TARGET_MAC is not configured.")
        return

    wake(TARGET_MAC)
    await _safe_reply(update, "🚀 <b>Magic Packet Sent</b>\nWaiting for PC to wake up...")


async def wake_wait_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    if not TARGET_MAC:
        await _safe_reply(update, "⚠️ <b>Error:</b> TARGET_MAC is not configured.")
        return

    wake(TARGET_MAC)
    await _safe_reply(
        update,
        "⏳ <b>Wake&Wait started.</b>\nMagic packet sent. Waiting for the agent to come back online...",
    )

    if await _wait_for_agent_online():
        await _safe_reply(
            update,
            "✅ <b>Agent is back online.</b>\nIf Windows sign-in on wake is disabled, your previous session should be restored.",
        )
        return

    await _safe_reply(update, "⚠️ <b>Wake timeout.</b>\nThe host did not come online within 3 minutes.")


async def shutdown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        await _agent_request("POST", "/shutdown", timeout=4.0)
        await _safe_reply(update, "🛑 <b>Shutdown initiated.</b>")
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Shutdown was rejected."))


async def sleep_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        await _agent_request("POST", "/sleep", timeout=6.0)
        await _safe_reply(update, "😴 <b>Sleep initiated.</b>")
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Sleep was rejected."))


async def hibernate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        await _agent_request("POST", "/hibernate", timeout=6.0)
        await _safe_reply(update, "💤 <b>Hibernate initiated.</b>")
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Hibernate was rejected."))


async def clipboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        response = await _agent_request("GET", "/clipboard")
        history = response.json().get("history", [])
        if not history:
            await _safe_reply(update, "📋 <b>Clipboard is empty.</b>")
            return

        items = []
        for index, item in enumerate(history, start=1):
            escaped_item = _escape(_truncate_text(str(item), 500))
            items.append(f"{index}. <code>{escaped_item}</code>")
        await _safe_reply(update, "📋 <b>Clipboard History</b>\n\n" + "\n\n".join(items))
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to read clipboard history."))


async def clear_clipboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        await _agent_request("DELETE", "/clipboard")
        await _safe_reply(update, "🧹 <b>Clipboard history cleared.</b>")
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to clear clipboard history."))


async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    await update.effective_message.reply_chat_action("upload_photo")
    try:
        response = await _agent_request("GET", "/screenshot", timeout=15.0)
        await update.effective_message.reply_photo(
            response.content,
            caption="📸 <b>Screenshot</b>",
            parse_mode="HTML",
            reply_markup=get_keyboard(),
        )
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to capture screenshot."))


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        response = await _agent_request("GET", "/stats")
        data = response.json()
        text = (
            "📊 <b>System Stats</b>\n\n"
            f"🧠 <b>CPU:</b> {_escape(data.get('cpu', 'n/a'))}%\n"
            f"💾 <b>RAM:</b> {_escape(data.get('ram_percent', 'n/a'))}% "
            f"({_escape(data.get('ram_used_gb', 'n/a'))} GB / {_escape(data.get('ram_total_gb', 'n/a'))} GB)\n"
            f"💿 <b>Disk:</b> {_escape(data.get('disk_percent', 'n/a'))}% "
            f"({_escape(data.get('disk_free_gb', 'n/a'))} GB free of {_escape(data.get('disk_total_gb', 'n/a'))} GB)\n"
            f"📁 <b>Path:</b> <code>{_escape(data.get('disk_path', 'n/a'))}</code>"
        )
        await _safe_reply(update, text)
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to read system stats."))


async def logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        response = await _agent_request("GET", "/logs", params={"lines": 20})
        log_lines = response.json().get("lines", [])
        if not log_lines:
            await _safe_reply(update, "📜 <b>No logs yet.</b>")
            return

        block = _escape(_truncate_text("\n".join(log_lines)))
        await _safe_reply(update, f"📜 <b>Last Agent Logs</b>\n\n<pre>{block}</pre>")
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to read agent logs."))


async def tasks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        response = await _agent_request("GET", "/tasks")
        tasks = response.json().get("tasks", [])
        if not tasks:
            await _safe_reply(update, "🧩 <b>No managed tasks configured.</b>")
            return

        text = "🧩 <b>Managed Tasks</b>\n\n" + "\n\n".join(_format_task(task) for task in tasks)
        await _safe_reply(update, text)
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to read task list."))


async def start_comfy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        response = await _agent_request_with_fallback(
            "POST",
            "/comfyui/start",
            "/tasks/comfyui/start",
            timeout=8.0,
        )
        task = response.json().get("task", {})
        text = (
            "▶️ <b>ComfyUI started.</b>\n"
            f"PID: {_escape(task.get('pid', 'n/a'))}\n"
            f"Log: <code>{_escape(task.get('log_file', 'n/a'))}</code>"
        )
        await _safe_reply(update, text)
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to start ComfyUI."))


async def stop_comfy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        await _agent_request_with_fallback(
            "POST",
            "/comfyui/stop",
            "/tasks/comfyui/stop",
            timeout=8.0,
        )
        await _safe_reply(update, "⏹️ <b>ComfyUI stopped.</b>")
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to stop ComfyUI."))


async def _volume_step(update: Update, delta: float) -> None:
    response = await _agent_request("POST", "/volume", json={"action": "step", "delta": delta})
    data = response.json()
    await _safe_reply(update, f"🔊 <b>Volume:</b> {_escape(data.get('level', 'n/a'))}%")


async def _volume_mute(update: Update) -> None:
    response = await _agent_request("POST", "/volume", json={"action": "mute"})
    data = response.json()
    await _safe_reply(update, f"🔊 <b>Volume:</b> {_escape(data.get('status', 'unknown'))}")


async def volume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    try:
        response = await _agent_request("POST", "/volume", json={"action": "get"})
        data = response.json()
        status = "🔇 Muted" if data.get("muted") else f"🔊 {data.get('level', 0)}%"
        text = (
            f"🔊 <b>Volume:</b> {status}\n\n"
            "Use the keyboard buttons <b>-10%</b>, <b>Mute</b> and <b>+10%</b>."
        )
        await _safe_reply(update, text)
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to read volume state."))


async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    await _safe_reply(update, "🏓 <b>Pong!</b> Bot is active.")


async def _dispatch_intent(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> bool:
    handlers = {
        "wake": wake_handler,
        "wake_wait": wake_wait_handler,
        "shutdown": shutdown_handler,
        "sleep": sleep_handler,
        "hibernate": hibernate_handler,
        "status": status_handler,
        "health": health_handler,
        "logs": logs_handler,
        "tasks": tasks_handler,
        "start_comfyui": start_comfy_handler,
        "stop_comfyui": stop_comfy_handler,
        "ping": ping_handler,
        "screenshot": screenshot_handler,
        "stats": stats_handler,
        "volume": volume_handler,
        "clipboard": clipboard_handler,
        "clear_clipboard": clear_clipboard_handler,
    }
    handler = handlers.get(action)
    if handler is None:
        return False
    await handler(update, context)
    return True


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    text = (update.effective_message.text or "").strip()

    button_actions = {
        "🚀 Wake": wake_handler,
        "⏳ Wake&Wait": wake_wait_handler,
        "😴 Sleep": sleep_handler,
        "💤 Hibernate": hibernate_handler,
        "🧩 Tasks": tasks_handler,
        "▶️ ComfyUI": start_comfy_handler,
        "⏹️ ComfyUI": stop_comfy_handler,
        "🛑 Shutdown": shutdown_handler,
        "📋 Clipboard": clipboard_handler,
        "🧹 Clear Clip": clear_clipboard_handler,
        "📸 Screen": screenshot_handler,
        "📊 Stats": stats_handler,
        "📜 Logs": logs_handler,
        "🔊 Volume": volume_handler,
        "🔍 Status": status_handler,
        "🩺 Health": health_handler,
        "ℹ️ Help": help_handler,
    }

    handler = button_actions.get(text)
    if handler is not None:
        await handler(update, context)
        return

    try:
        if text == "🔉 -10%":
            await _volume_step(update, -0.1)
            return
        if text == "🔇 Mute":
            await _volume_mute(update)
            return
        if text == "🔊 +10%":
            await _volume_step(update, 0.1)
            return
        if text in {"+", "-", "mute"}:
            if text == "+":
                await _volume_step(update, 0.1)
            elif text == "-":
                await _volume_step(update, -0.1)
            else:
                await _volume_mute(update)
            return
    except httpx.HTTPError as error:
        await _safe_reply(update, _agent_error_text(error, "Unable to change volume."))
        return

    intent = await parse_intent(text)
    if await _dispatch_intent(update, context, intent.get("action", "unknown")):
        return

    await _safe_reply(update, "❓ <b>Unknown command.</b>\nTry <code>wake and wait</code>, <code>tasks</code> or <code>help</code>.")


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    voice = update.message.voice
    temp_audio_path = None

    await _safe_reply(update, "🎧 Processing voice command...", parse_mode=None)

    try:
        telegram_file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_audio_path = temp_file.name

        await telegram_file.download_to_drive(temp_audio_path)
        text = await speech_to_text(temp_audio_path)
        if not text:
            await _safe_reply(update, "⚠️ <b>Voice command was empty or not recognized.</b>")
            return

        intent = await parse_intent(text)
        handled = await _dispatch_intent(update, context, intent.get("action", "unknown"))
        if not handled:
            await _safe_reply(
                update,
                f"❓ <b>Unknown voice command.</b>\n\n🗣 <b>You said:</b> <code>{_escape(text)}</code>",
            )
            return

        await _safe_reply(update, f"🗣 <b>You said:</b> <code>{_escape(text)}</code>")
    except FileNotFoundError as error:
        await _safe_reply(update, f"⚠️ <b>Voice unavailable:</b> {_escape(error)}")
    except subprocess.CalledProcessError:
        await _safe_reply(update, "⚠️ <b>Voice unavailable:</b> ffmpeg failed to decode the audio.")
    except Exception as error:
        logger.exception("Voice handler failed")
        await _safe_reply(update, f"❌ <b>Voice processing failed:</b> {_escape(error)}")
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
