import os
import subprocess
import platform
import httpx
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from bot.config import ALLOWED_USERS, TARGET_MAC, TARGET_HOST, AGENT_PORT
from bot.wol import wake
from bot.voice import speech_to_text
from bot.ai import parse_intent
from telegram.ext import MessageHandler, filters

AGENT_URL = f"http://{TARGET_HOST}:{AGENT_PORT}"

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def get_keyboard():
    keyboard = [
        [KeyboardButton("🚀 Wake"), KeyboardButton("🛑 Shutdown")],
        [KeyboardButton("📸 Screen"), KeyboardButton("📋 Clipboard")],
        [KeyboardButton("📊 Stats"), KeyboardButton("🔊 Volume")],
        [KeyboardButton("🔍 Status"), KeyboardButton("ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def check_permissions(update: Update) -> bool:
    if not is_allowed(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Access denied")
        return False
    return True

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    await update.effective_message.reply_text(
        "👋 <b>Control Center Online</b>\n\nI can help you manage your PC remotely.",
        parse_mode="HTML",
        reply_markup=get_keyboard()
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    help_text = (
        "🤖 <b>Control Panel Commands:</b>\n\n"
        "🚀 <b>Wake</b> - Send Wake-on-LAN packet\n"
        "🛑 <b>Shutdown</b> - Remote system shutdown\n"
        "😴 <b>Sleep</b> - Put PC to sleep\n"
        "📸 <b>Screen</b> - Capture remote screen\n"
        "📋 <b>Clipboard</b> - View last 5 copied items\n"
        "📊 <b>Stats</b> - View system CPU/RAM usage\n"
        "🔊 <b>Volume</b> - Control system volume\n"
        "🔍 <b>Status</b> - Check network connectivity"
    )
    await update.effective_message.reply_text(help_text, parse_mode="HTML", reply_markup=get_keyboard())

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.effective_message.reply_text("🔍 Checking connectivity...")
    
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', TARGET_HOST]
    try:
        response = subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        is_online = response == 0
    except Exception:
        is_online = False

    status_msg = "🟢 <b>Online</b>" if is_online else "🔴 <b>Offline</b>"
    
    agent_msg = ""
    if is_online:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{AGENT_URL}/ping")
                if r.status_code == 200:
                    agent_msg = "\n🤖 <b>Agent:</b> Connected ✅"
                else:
                    agent_msg = "\n🤖 <b>Agent:</b> Error ⚠️"
        except Exception:
            agent_msg = "\n🤖 <b>Agent:</b> Unreachable ❌"

    await update.effective_message.reply_text(
        f"🖥️ <b>PC Status:</b> {status_msg}{agent_msg}", 
        parse_mode="HTML",
        reply_markup=get_keyboard()
    )

async def wake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    wake(TARGET_MAC)
    await update.effective_message.reply_text("🚀 <b>Magic Packet Sent!</b>\nWaiting for PC to wake up...", parse_mode="HTML", reply_markup=get_keyboard())

async def shutdown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.effective_message.reply_text("🛑 Sending shutdown command...", reply_markup=get_keyboard())
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{AGENT_URL}/shutdown")
            if r.status_code == 200:
                await update.effective_message.reply_text("✅ <b>Shutdown Initiated</b>\nSystem is powering off.", parse_mode="HTML")
            else:
                await update.effective_message.reply_text(f"⚠️ <b>Error:</b> Agent returned {r.status_code}", parse_mode="HTML")
    except Exception:
        await update.effective_message.reply_text("❌ <b>Failed:</b> Agent unreachable.\nIs the PC on and Agent running?", parse_mode="HTML")

async def sleep_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.effective_message.reply_text("😴 Sending sleep command...", reply_markup=get_keyboard())
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{AGENT_URL}/sleep")
            if r.status_code == 200:
                await update.effective_message.reply_text("✅ <b>Sleep Initiated</b>\nSystem is going to sleep.", parse_mode="HTML")
            else:
                await update.effective_message.reply_text(f"⚠️ <b>Error:</b> Agent returned {r.status_code}", parse_mode="HTML")
    except Exception:
        await update.effective_message.reply_text("❌ <b>Failed:</b> Agent unreachable.", parse_mode="HTML")

async def clipboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{AGENT_URL}/clipboard")
            if r.status_code == 200:
                history = r.json().get("history", [])
                if not history:
                    content = "📋 <b>Clipboard is empty</b>"
                else:
                    items = "\n\n".join([f"🔹 <code>{item}</code>" for item in history])
                    content = f"📋 <b>Clipboard History:</b>\n\n{items}"
                await update.effective_message.reply_text(content, parse_mode="HTML", reply_markup=get_keyboard())
            else:
                await update.effective_message.reply_text(f"⚠️ <b>Error:</b> Agent returned {r.status_code}", parse_mode="HTML")
    except Exception:
        await update.effective_message.reply_text("❌ <b>Failed:</b> Agent unreachable.", parse_mode="HTML")

async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    await update.effective_message.reply_chat_action("upload_photo")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{AGENT_URL}/screenshot")
            if r.status_code == 200:
                await update.effective_message.reply_photo(r.content, caption="📸 <b>Screenshot</b>", parse_mode="HTML", reply_markup=get_keyboard())
            else:
                await update.effective_message.reply_text(f"⚠️ <b>Error:</b> Agent returned {r.status_code}", parse_mode="HTML")
    except Exception:
        await update.effective_message.reply_text("❌ <b>Failed:</b> Agent unreachable.", parse_mode="HTML")

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{AGENT_URL}/stats")
            if r.status_code == 200:
                data = r.json()
                msg = (
                    f"📊 <b>System Stats</b>\n\n"
                    f"🧠 <b>CPU:</b> {data['cpu']}%\n"
                    f"💾 <b>RAM:</b> {data['ram_percent']}% ({data['ram_used_gb']}GB / {data['ram_total_gb']}GB)\n"
                    f"💿 <b>Disk:</b> {data['disk_percent']}% (Free: {data['disk_free_gb']}GB)"
                )
                await update.effective_message.reply_text(msg, parse_mode="HTML", reply_markup=get_keyboard())
            else:
                await update.effective_message.reply_text(f"⚠️ <b>Error:</b> Agent returned {r.status_code}", parse_mode="HTML")
    except Exception:
        await update.effective_message.reply_text("❌ <b>Failed:</b> Agent unreachable.", parse_mode="HTML")

async def volume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{AGENT_URL}/volume", json={"action": "get"})
            if r.status_code == 200:
                data = r.json()
                vol_status = "🔇 Muted" if data['muted'] else f"🔊 {data['level']}%"
                
                await update.effective_message.reply_text(
                    f"🔊 <b>Volume:</b> {vol_status}\n\n"
                    "Reply with <code>+</code> to increase, <code>-</code> to decrease, or <code>mute</code> to toggle.", 
                    parse_mode="HTML",
                    reply_markup=get_keyboard()
                )
            else:
                await update.effective_message.reply_text(f"⚠️ <b>Error:</b> Agent returned {r.status_code}", parse_mode="HTML")
    except Exception:
        await update.effective_message.reply_text("❌ <b>Failed:</b> Agent unreachable.", parse_mode="HTML")

async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return
    await update.effective_message.reply_text("🏓 <b>Pong!</b> Bot is active.", parse_mode="HTML", reply_markup=get_keyboard())

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text

    if text == "🚀 Wake":
        await wake_handler(update, context)
    elif text == "🛑 Shutdown":
        await shutdown_handler(update, context)
    elif text == "📋 Clipboard":
        await clipboard_handler(update, context)
    elif text == "📸 Screen":
        await screenshot_handler(update, context)
    elif text == "📊 Stats":
        await stats_handler(update, context)
    elif text == "🔊 Volume":
        await volume_handler(update, context)
    elif text == "🔍 Status":
        await status_handler(update, context)
    elif text == "🏓 Ping":
        await ping_handler(update, context)
    elif text == "ℹ️ Help":
        await help_handler(update, context)
    elif text in ["+", "-", "mute"]:
        action = "get"
        level_change = 0.0
        
        if text == "mute":
            action = "mute"
        elif text == "+":
            action = "set"
            level_change = 0.1
        elif text == "-":
            action = "set"
            level_change = -0.1
            
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.post(f"{AGENT_URL}/volume", json={"action": "get"})
                if r.status_code == 200:
                    current_data = r.json()
                    current_level = float(current_data['level']) / 100.0
                    
                    if action == "mute":
                        r2 = await client.post(f"{AGENT_URL}/volume", json={"action": "mute"})
                        new_status = r2.json()
                        await update.effective_message.reply_text(f"🔊 <b>Volume:</b> {new_status['status']}", parse_mode="HTML")
                    elif action == "set":
                        new_level = current_level + level_change
                        r2 = await client.post(f"{AGENT_URL}/volume", json={"action": "set", "level": new_level})
                        new_data = r2.json()
                        await update.effective_message.reply_text(f"🔊 <b>Volume:</b> {int(new_data['level'] * 100)}%", parse_mode="HTML")
        except Exception:
            await update.effective_message.reply_text("❌ <b>Failed:</b> Agent unreachable.", parse_mode="HTML")
        return
    else:
        await update.effective_message.reply_text(
            "❓ Unknown command",
            reply_markup=get_keyboard()
        )

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permissions(update):
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    audio_path = f"/tmp/{voice.file_id}.ogg"
    await file.download_to_drive(audio_path)

    await update.effective_message.reply_text("🎧 Processing voice command...")

    try:
        text = await speech_to_text(audio_path)
        intent = await parse_intent(text)

        action = intent.get("action", "unknown")

        if action == "wake":
            await wake_handler(update, context)
            msg = "🧠 <b>Action:</b> Wake PC"

        elif action == "shutdown":
            await shutdown_handler(update, context)
            msg = "🧠 <b>Action:</b> Shutdown PC"

        elif action == "sleep":
            await sleep_handler(update, context)
            msg = "🧠 <b>Action:</b> Sleep PC"

        elif action == "screenshot":
            await screenshot_handler(update, context)
            msg = "🧠 <b>Action:</b> Screenshot"

        elif action == "stats":
            await stats_handler(update, context)
            msg = "🧠 <b>Action:</b> System Stats"

        elif action == "clipboard":
            await clipboard_handler(update, context)
            msg = "🧠 <b>Action:</b> Clipboard"

        elif action == "volume":
            await volume_handler(update, context)
            msg = "🧠 <b>Action:</b> Volume"

        elif action == "status":
            await status_handler(update, context)
            return

        elif action == "ping":
            await ping_handler(update, context)
            return

        else:
            msg = "❓ <b>Unknown command</b>"

        await update.effective_message.reply_text(
            f"{msg}\n\n🗣 <b>You said:</b> <code>{text}</code>",
            parse_mode="HTML",
            reply_markup=get_keyboard()
        )

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
